import streamlit as st
from datetime import datetime
from Workflow import (extract_pdf_content, extract_youtube_transcript,generate_medium_blog,
    generate_linkedin_post,
    process_user_message_with_context
)
from MongoData import (create_new_chat, 
    save_message, 
    get_all_chats, 
    get_chat_messages, delete_chat, 
    chats_collection, 
    messages_collection,vector_store,
    get_or_load_chat_context
)

st.set_page_config(
    page_title="AI Powered Content creation Automation", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_new_chat_dialog" not in st.session_state:
    st.session_state.show_new_chat_dialog = False
if "show_upload_dialog" not in st.session_state:
    st.session_state.show_upload_dialog = False

st.markdown("""
<style>
    /* Main container adjustments */
    .main .block-container {
        padding-top: 5rem;
        padding-bottom: 8rem;
        max-width: 100%;
    }
    
    /* Fixed header */
    .fixed-header {
        position: fixed;
        top: 0;
        left: 16rem;
        right: 0;
        z-index: 999;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2.5rem 2rem;
        height: 7rem;
        box-shadow: 0 2px 20px rgba(0,0,0,0.15);
    }
    
    .fixed-header h1 {
        color: white;
        margin: 0;
        text-align: center;
        font-size: 2rem;
        font-weight: 600;
    }
    
    /* Chat messages area */
    .stChatMessage {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    [data-testid="stChatMessageContent"] {
        color: #2c3e50;
        font-size: 1rem;
        line-height: 1.6;
    }
    
    /* User messages */
    .stChatMessage[data-testid*="user"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        margin-left: 15%;
    }
    
    .stChatMessage[data-testid*="user"] [data-testid="stChatMessageContent"] {
        color: white !important;
    }
    
    .stChatMessage[data-testid*="user"] p {
        color: white !important;
    }
    
    /* Assistant messages */
    .stChatMessage[data-testid*="assistant"] {
        background: white;
        border: 1px solid #e1e4e8;
        margin-right: 15%;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="fixed-header">
    <h1>🤖 AI Social Media Content Generator</h1>
</div>
""", unsafe_allow_html=True)


def load_chat_with_context(chat_id):
    db_messages = get_chat_messages(chat_id)
    vector_store.load_chat_history_to_store(chat_id)
    return db_messages

@st.dialog("Create New Chat")
def new_chat_dialog():
    st.write("Please provide details for your new chat:")
    chat_name = st.text_input(
        "Chat Name", 
        placeholder="e.g., Marketing Campaign Ideas", 
        key="chat_name_input"
    )
    platform = st.selectbox(
        "Select Platform", 
        ["LinkedIn", "Medium"], 
        key="platform_input"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create", use_container_width=True, type="primary"):
            if chat_name.strip():
                new_chat_id = create_new_chat(chat_name.strip(), platform)

                st.session_state.current_chat_id = new_chat_id
                st.session_state.messages = []

                st.session_state.show_new_chat_dialog = False
                st.rerun()
            else:
                st.error("Please enter a chat name")
    
    with col2:

        if st.button("Cancel", use_container_width=True):

            st.session_state.show_new_chat_dialog = False
            st.rerun()


@st.dialog("Upload Document or URL")
def upload_dialog():
    st.write("Upload a document or enter a URL to extract content:")
    tab1, tab2 = st.tabs(["📄 Upload File", "🔗 Enter URL"])
    with tab1:
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['pdf'],
            key="file_uploader"

        )
        
        if uploaded_file:

            st.success(f"File selected: {uploaded_file.name}")
            st.info(f"Size: {uploaded_file.size / 1024:.2f} KB")
        
        if st.button("Upload File", use_container_width=True, type="primary", disabled=uploaded_file is None):
            if uploaded_file:

                with st.spinner("Extracting content from PDF..."):
                    current_time = datetime.utcnow()
                    extracted_text = extract_pdf_content(uploaded_file)
                    current_chat = chats_collection.find_one({"_id": st.session_state.current_chat_id})
                    platform = current_chat.get("platform", "General") if current_chat else "General"
                    file_info = f"📎 Uploaded file: **{uploaded_file.name}** ({uploaded_file.size / 1024:.2f} KB)"
                    save_message(
                        st.session_state.current_chat_id,
                        "user",
                        file_info,
                        platform=platform,
                        source=uploaded_file.name,
                        extracted_content=extracted_text
                    )
                    user_msg = {
                        "role": "user",
                        "content": file_info,
                        "timestamp": current_time,
                        "chat_id": st.session_state.current_chat_id,
                        "source": uploaded_file.name,
                        "file_type": uploaded_file.type
                    }
                    st.session_state.messages.append(user_msg)
                
                
                    assistant_response = f"""I've received your file **{uploaded_file.name}**. 

📄 **Content Preview:**
{extracted_text[:500]}...

**What would you like me to do with this content?**
- Generate a {platform} ready post
- Create social media posts
- Summarize key points
- Something else?

Just tell me what you need! 💡"""
                    
                    save_message(st.session_state.current_chat_id, "assistant", assistant_response, platform=platform)
                    
                    assistant_msg = {
                        "role": "assistant",
                        "content": assistant_response,
                        "timestamp": current_time,
                        "chat_id": st.session_state.current_chat_id
                    }
                    st.session_state.messages.append(assistant_msg)
                    
                    st.session_state.show_upload_dialog = False
                    st.rerun()
    
    with tab2:
        url_input = st.text_input(
            "Enter URL",
            placeholder="https://youtube.com/watch?v=...",
            key="url_input"
        )
        
        if url_input:
            st.info(f"URL: {url_input}")
        
        if st.button("Submit URL", use_container_width=True, type="primary", disabled=not url_input):
            if url_input:
                with st.spinner("📺 Extracting transcript from YouTube..."):
                    current_time = datetime.utcnow()
                    extracted_text = extract_youtube_transcript(url_input)
                    
                    current_chat = chats_collection.find_one({"_id": st.session_state.current_chat_id})
                    platform = current_chat.get("platform", "General") if current_chat else "General"
                    
                    url_info = f"🔗 URL submitted: [{url_input}]({url_input})"
                    
                    save_message(
                        st.session_state.current_chat_id,
                        "user",
                        url_info,
                        platform=platform,
                        source=url_input,
                        extracted_content=extracted_text
                    )
                    
                    user_msg = {
                        "role": "user",
                        "content": url_info,
                        "timestamp": current_time,
                        "chat_id": st.session_state.current_chat_id,
                        "source": url_input,
                        "source_type": "url"
                    }
                    st.session_state.messages.append(user_msg)
                    
                    assistant_response = f"""✅ I've received your YouTube video!

📺 **Transcript Preview:**
{extracted_text[:500]}...

**What would you like me to create from this video?**

Let me know how you'd like to use this content! 🎬"""
                    
                    save_message(st.session_state.current_chat_id, "assistant", assistant_response, platform=platform)
                    
                    assistant_msg = {
                        "role": "assistant",
                        "content": assistant_response,
                        "timestamp": current_time,
                        "chat_id": st.session_state.current_chat_id
                    }
                    st.session_state.messages.append(assistant_msg)
                    
                    st.session_state.show_upload_dialog = False
                    st.rerun()
    
    if st.button("Cancel", use_container_width=True):
        st.session_state.show_upload_dialog = False
        st.rerun()


with st.sidebar:
    st.title("💬 Chats")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary", key="new_chat_btn"):
        st.session_state.show_new_chat_dialog = True
        st.rerun()
    
    if st.button("📤 Upload Document", use_container_width=True, type="secondary", key="upload_btn"):
        if st.session_state.current_chat_id is None:
            st.warning("Please create or select a chat first!")
        else:
            st.session_state.show_upload_dialog = True
            st.rerun()
    
    st.divider()
 
    all_chats = get_all_chats()
    
    if len(all_chats) == 0:
        st.caption("No chats yet. Create one to start!")
    else:
        for chat in all_chats:
            chat_id = chat["_id"]
            chat_name = chat.get("chat_name", f"Chat {chat_id}")
            platform = chat.get("platform", "General")
            

            col1, col2 = st.columns([6,2])
            
            with col1:
                is_active = st.session_state.current_chat_id == chat_id
                button_type = "primary" if is_active else "secondary"
                
                button_label = f"{chat_name}"
                
                if st.button(
                    button_label,
                    key=f"chat_{chat_id}",
                    use_container_width=True,
                    type=button_type,
                    help=f"Platform: {platform}"
                ):
                    st.session_state.current_chat_id = chat_id
    
                    db_messages = load_chat_with_context(chat_id)
                    st.session_state.messages = db_messages
                    st.rerun()
            
            with col2:
                if st.button("🗑️", key=f"del_{chat_id}", help="Delete chat"):
                    delete_chat(chat_id)
                    if st.session_state.current_chat_id == chat_id:
                        st.session_state.current_chat_id = None
                        st.session_state.messages = []
                    st.rerun()

if st.session_state.show_new_chat_dialog:
    new_chat_dialog()

if st.session_state.show_upload_dialog:
    upload_dialog()


if st.session_state.current_chat_id is None:
    st.info("👋 Welcome! Create a new chat or select an existing one to start chatting.")
else:

    current_chat = chats_collection.find_one({"_id": st.session_state.current_chat_id})
    if current_chat:
        chat_name = current_chat.get("chat_name", f"Chat {st.session_state.current_chat_id}")
        platform = current_chat.get("platform", "General")
        st.caption(f"💬 **{chat_name}** | 📱 {platform}")
 
    for message in st.session_state.messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        timestamp = message.get("timestamp", datetime.utcnow())
        
        with st.chat_message(role):
            st.markdown(content)
            
        
            if message.get("source"):
                st.caption(f"📎 {message['source']}")
            
            st.caption(f"🕐 {timestamp.strftime('%I:%M %p')}")


prompt = st.chat_input("Type your message here...", disabled=st.session_state.current_chat_id is None)

if prompt:
    current_time = datetime.utcnow()
    
    current_chat = chats_collection.find_one({"_id": st.session_state.current_chat_id})
    platform = current_chat.get("platform", "General") if current_chat else "General"
   
    save_message(st.session_state.current_chat_id, "user", prompt, platform=platform)
    
    user_msg = {
        "role": "user",
        "content": prompt,
        "timestamp": current_time,
        "chat_id": st.session_state.current_chat_id
    }
    st.session_state.messages.append(user_msg)
    
    is_generation_request = any(keyword in prompt.lower() for keyword in [
        'generate', 'create', 'write', 'make', 'blog', 'post', 'content', 'draft'
    ])
    
    extracted_content = None
    recent_msgs = messages_collection.find({
        "chat_id": st.session_state.current_chat_id,
        "extracted_content": {"$exists": True}
    }).sort("timestamp", -1).limit(1)
    
    for msg in recent_msgs:
        if msg.get("extracted_content"):
            extracted_content = msg["extracted_content"]
            break

    with st.spinner("🤔 Thinking..."):
        if is_generation_request and extracted_content:
            if platform == "Medium":

                result = generate_medium_blog(
                    chat_id=st.session_state.current_chat_id,
                    raw_content=extracted_content,
                    user_request=prompt,
                    platform=platform
                )
                
                if result["success"]:
                    for workflow_msg in result["workflow_messages"]:
                        assistant_response = workflow_msg.content
                        
                        save_message(
                            st.session_state.current_chat_id, 
                            "assistant", 
                            assistant_response, 
                            platform=platform
                        )
                        
                        assistant_msg = {
                            "role": "assistant",
                            "content": assistant_response,
                            "timestamp": datetime.utcnow(),
                            "chat_id": st.session_state.current_chat_id
                        }
                        st.session_state.messages.append(assistant_msg)
                    
                    final_response = f"## 🎉 Your Medium Blog is Ready!\n\n{result['final_blog']}"
                    
                else:
                    final_response = f"❌ Error: {result['error']}"
            
            elif platform == "LinkedIn":
                result = generate_linkedin_post(
                    chat_id=st.session_state.current_chat_id,
                    raw_content=extracted_content,
                    user_request=prompt,
                    platform=platform
                )
                
                if result["success"]:
                    for workflow_msg in result["workflow_messages"]:
                        assistant_response = workflow_msg.content
                        
                        save_message(
                            st.session_state.current_chat_id, 
                            "assistant", 
                            assistant_response, 
                            platform=platform
                        )
                        
                        assistant_msg = {
                            "role": "assistant",
                            "content": assistant_response,
                            "timestamp": datetime.utcnow(),
                            "chat_id": st.session_state.current_chat_id
                        }
                        st.session_state.messages.append(assistant_msg)
                    
                    final_response = f"## 🎉 Your LinkedIn Post is Ready!\n\n{result['final_post']}\n\n---\n\n**📊 Character Count:** {len(result['final_post'])} characters"
                    
                else:
                    final_response = f"❌ Error: {result['error']}"
            
            else:
                final_response = f"🚧 Content generation for {platform} is coming soon! Currently supported: Medium, LinkedIn."
            
        else:
            assistant_response = process_user_message_with_context(
                chat_id=st.session_state.current_chat_id,
                user_message=prompt,
                extracted_content=extracted_content[:1000] if extracted_content else None
            )
            final_response = assistant_response

    save_message(st.session_state.current_chat_id, "assistant", final_response, platform=platform)
    
    assistant_msg = {
        "role": "assistant",
        "content": final_response,
        "timestamp": datetime.utcnow(),
        "chat_id": st.session_state.current_chat_id
    }
    st.session_state.messages.append(assistant_msg)
    
    st.rerun()
