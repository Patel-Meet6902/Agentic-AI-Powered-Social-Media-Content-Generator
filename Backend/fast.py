from fastapi import FastAPI, HTTPException,UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from typing import Annotated,Dict,Any

from MongoData import(
    create_new_chat,get_all_chats,get_chat_messages,chats_collection,save_message,messages_collection,
)

from Workflow import(
    generate_medium_blog,generate_linkedin_post, process_user_message_with_context,extract_pdf_content,
)

from datetime import datetime

app = FastAPI()

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For learning only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NewChatRequest(BaseModel):
    chat_name: str
    platform: str = "LinkedIn"

class chatmessagerequest(BaseModel):
    message : str



@app.post("/api/chats")
def new_chat(body: NewChatRequest):
    print("chat created succesfully")
    if( not body.chat_name):
        raise HTTPException(status_code=400,detail='chat name can not be empty')
    chat_id = create_new_chat(body.chat_name,body.platform)
    return {"chat_id":chat_id,'chat_name':body.chat_name,'platform':body.platform}


@app.get("/api/chats")
def list_chats():
    chats = get_all_chats()
    print(type(chats))
    result = []
    for c in chats:
        result.append({
            'id':c['_id'],
            'chat_name':c["chat_name"],
            'platform':c["platform"],
            "updated_at": c.get("updated_at", datetime.utcnow()).strftime("%b %d, %I:%M %p"),
        })
    return result


@app.get("/api/chats/{chat_id}/messages")
def get_messages(chat_id:int):
    msgs = get_chat_messages(chat_id)
    msgs_result = []
    for m in msgs:
        msgs_result.append(
            {
                "id" : str(m['_id']),
                "chat_id":m['chat_id'],
                'role' : m['role'],
                'content' : m['content'],
                'timestamp' : m.get("timestamp", datetime.utcnow()).strftime("%I:%M %p"),
                'platform' : m.get('platform',""),
                'source' : m.get('source',""),
            }
        )
    return msgs_result



@app.post("/api/chats/{chat_id}/message")
def get_messages(chat_id:int, body:chatmessagerequest):
    prompt = body.message.strip()
    if not prompt:
        raise HTTPException(status_code=400,detail='Input can not be empty')
    
    chat_doc = chats_collection.find_one({'_id':chat_id})
    if chat_doc:
        platform = chat_doc.get('platform','general')
        print(platform)
    
    save_message(chat_id,"user",prompt,platform)

    generate_keywords = ["generate", "create", "write", "make", "blog", "post", "content", "draft"]
    is_generation = False
    for word in generate_keywords:
        if word in prompt.lower():
            is_generation=True
            break

    extracted_content = None
    recent = list(messages_collection.find({'chat_id':chat_id, "extracted_content":{"$exists": True}}).sort("timestamp",-1).limit(1))


    for m in recent:
        extracted_content = m.get('extracted_content')
        break
    
    print(extracted_content)
    print(is_generation)

    if is_generation and extracted_content:
        if platform == "Medium":
            print("generating a medium blog")
            result = generate_medium_blog(
                chat_id=chat_id,
                raw_content=extracted_content,
                user_request=prompt,
                platform=platform,
            )

            if result["success"]:
                final = f"## 🎉 Your Medium Blog is Ready!\n\n {result['final_blog']}"
            else:
                final = f"❌ Error: {result['error']}"
        elif platform == "LinkedIn":
            result = generate_linkedin_post(
                chat_id=chat_id,
                raw_content=extracted_content,
                user_request=prompt,
                platform=platform,
            )

            if result["success"]:
                final = f"## 🎉 Your LinkedIN Post is Ready!\n\n {result['final_post']}"
            else:
                final = f"❌ Error: {result['error']}"
        
        else:
            final = f"🚧 Generation for {platform} is coming soon! Supported: Medium, LinkedIn."
    
    else:
        final = process_user_message_with_context(
            chat_id = chat_id,
            user_message=prompt,
            extracted_content=extracted_content,
        )

    save_message(chat_id,'assistant',final,platform=platform)
    return {'responses':[final]}

@app.post("/api/chats/{chat_id}/uploadpdf")
def uploadpdf(chat_id:int, file: Annotated[UploadFile,File(...)]):
    print('i am here')

    chat_doc = chats_collection.find_one({'_id':chat_id})
    if chat_doc:
        platform = chat_doc.get('platform','general')
        print(platform)

    extracted_text = extract_pdf_content(file.file)

    file_info = f"📎 Uploaded file: **{file.filename}** ({file.size / 1024:.1f} KB)" if hasattr(file, "size") else f"📎 Uploaded file: **{file.filename}**"

    save_message(chat_id,'user',file_info,platform=platform,source=file.filename,extracted_content=extracted_text,)

    assistant_reply = (
        f"I've received your file **{file.filename}**.\n\n"
        f"📄 **Content Preview:**\n{extracted_text[:500]}...\n\n"
        f"**What would you like me to do with this content?**\n"
        f"- Generate a {platform} ready post\n"
        f"- Summarize key points\n"
        f"- Something else?\n\nJust tell me! 💡"
    )
    save_message(chat_id, "assistant", assistant_reply, platform=platform)
 
    return {
        "user_message":      file_info,
        "assistant_message": assistant_reply,
    }


