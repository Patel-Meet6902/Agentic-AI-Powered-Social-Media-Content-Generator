import PyPDF2
from io import BytesIO
from youtube_transcript_api import YouTubeTranscriptApi
import re
from typing import List, Dict, Any, TypedDict, Annotated
from datetime import datetime

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from MongoData import vector_store, get_or_load_chat_context


def extract_pdf_content(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_file.read()))
        
        text_content = ""
        for page in pdf_reader.pages:
            text_content += page.extract_text() + "\n"
        
        return text_content.strip()
    
    except Exception as e:
        return f"Error extracting PDF content: {str(e)}"


def extract_youtube_transcript(url):
    try:
        video_id = None
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
            r'youtube\.com\/embed\/([^&\n?#]+)',
            r'youtube\.com\/v\/([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break
        
        if not video_id:
            return "Error: Invalid YouTube URL"

        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

        transcript_text = " ".join([segment['text'] for segment in transcript_list])
        
        return transcript_text
    
    except Exception as e:
        return f"Error extracting YouTube transcript: {str(e)}"

class BlogState(TypedDict):
    messages: Annotated[List, "The conversation messages"]
    raw_content: str
    platform: str
    user_request: str
    outline: str
    draft_blog: str
    final_blog: str
    chat_id: int
    chat_context: str

def create_medium_blog_workflow():
    
    llm = ChatOllama(
        model="llama3.2", 
        temperature=0.7,
        base_url="http://localhost:11434"  
    )
    def analyze_and_outline(state: BlogState) -> BlogState:
        relevant_context = vector_store.get_relevant_context(
            chat_id=state["chat_id"],
            query=state["user_request"],
            n_results=3
        )


        context_str = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in relevant_context
        ]) if relevant_context else "No previous context available"
        
        prompt = f"""You are an expert content strategist and Medium blog writer.

Previous conversation context:
{context_str}

User's request: {state['user_request']}

Raw content to analyze:
{state['raw_content'][:3000]}...

Create a detailed outline for a Medium blog post that:
1. Has an engaging, SEO-friendly title
2. Includes 5-7 main sections with subpoints
3. Considers readability and Medium's best practices
4. Addresses the user's specific requirements
5. Makes the content engaging and valuable

Provide the outline in a clear, structured format with markdown headers."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        state["outline"] = response.content
        state["messages"].append(AIMessage(content=f"📋 **Outline Created**\n\n{response.content[:200]}..."))
        
        return state
    
    def generate_draft(state: BlogState) -> BlogState:
        
        prompt = f"""You are an expert Medium blog writer with years of experience.

Based on this outline:
{state['outline']}

And this raw content:
{state['raw_content'][:4000]}...

Write a complete Medium blog post that:
1. Has an attention-grabbing introduction with a hook
2. Follows the outline structure perfectly
3. Includes relevant examples, insights, and stories
4. Uses Medium-style formatting:
   - # for main title
   - ## for section headers
   - ### for subheaders
   - **bold** for emphasis
   - *italics* for quotes or subtle emphasis
   - > for blockquotes
   - Code blocks where appropriate
5. Has smooth transitions between sections
6. Includes a strong conclusion with clear takeaways
7. Is between 1200-1800 words
8. Written in a conversational yet professional tone

Write the complete blog post in Markdown format."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        state["draft_blog"] = response.content
        state["messages"].append(AIMessage(content="✍️ **Draft Blog Generated**"))
        
        return state
    
    def refine_blog(state: BlogState) -> BlogState:
        
        prompt = f"""You are an expert editor specializing in Medium blog posts.

Review and refine this draft blog post:

{state['draft_blog']}

User's original request: {state['user_request']}

Improve it by:
1. Enhancing readability and flow
2. Adding compelling subheadings where needed
3. Ensuring proper markdown formatting for Medium
4. Checking grammar, punctuation, and style
5. Adding relevant emojis strategically (not too many!)
6. Strengthening the introduction and conclusion
7. Making sure it addresses the user's request perfectly
8. Adding a clear call-to-action at the end

Provide the final, polished, publication-ready version in Markdown format.
Make it shine! ✨"""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        state["final_blog"] = response.content
        state["messages"].append(AIMessage(content="✨ **Final Blog Post Ready!**"))
        
        return state
    
    workflow = StateGraph(BlogState)
    
    workflow.add_node("analyze_outline", analyze_and_outline)
    workflow.add_node("generate_draft", generate_draft)
    workflow.add_node("refine_polish", refine_blog)
    
    workflow.set_entry_point("analyze_outline")
    workflow.add_edge("analyze_outline", "generate_draft")
    workflow.add_edge("generate_draft", "refine_polish")
    workflow.add_edge("refine_polish", END)
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app


def generate_medium_blog(
    chat_id: int,
    raw_content: str,
    user_request: str,
    platform: str = "Medium"
) -> Dict[str, Any]:
    
    try:
        chat_context = get_or_load_chat_context(chat_id)
        workflow = create_medium_blog_workflow()

        initial_state = {
            "messages": [],
            "raw_content": raw_content,
            "platform": platform,
            "user_request": user_request,
            "outline": "",
            "draft_blog": "",
            "final_blog": "",
            "chat_id": chat_id,
            "chat_context": chat_context
        }
        
        config = {"configurable": {"thread_id": f"chat_{chat_id}"}}
        final_state = workflow.invoke(initial_state, config)
        
        return {
            "success": True,
            "outline": final_state["outline"],
            "draft": final_state["draft_blog"],
            "final_blog": final_state["final_blog"],
            "workflow_messages": final_state["messages"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating blog: {str(e)}"
        }


def process_user_message_with_context(
    chat_id: int,
    user_message: str,
    extracted_content: str = None
) -> str:
    
    try:
        
        relevant_context = vector_store.get_relevant_context(
            chat_id=chat_id,
            query=user_message,
            n_results=5
        )
        
        context_str = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in relevant_context
        ]) if relevant_context else "No previous context"
    
        llm = ChatOllama(
            model="llama3.2",
            temperature=0.7,
            base_url="http://localhost:11434"
        )
        
        prompt = f"""You are a helpful AI assistant specializing in content creation for social media.

Previous conversation context:
{context_str}

{"Extracted content available: " + extracted_content[:500] + "..." if extracted_content else ""}

User's message: {user_message}

Provide a helpful, contextual response. If the user is asking to generate content, guide them on what information you need."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
        
    except Exception as e:
        return f"Error processing message: {str(e)}"


class LinkedInState(TypedDict):
    """State for LinkedIn post generation workflow."""
    messages: Annotated[List, "The conversation messages"]
    raw_content: str
    platform: str
    user_request: str
    key_insights: str
    post_draft: str
    final_post: str
    chat_id: int
    chat_context: str


def create_linkedin_post_workflow():
    
    llm = ChatOllama(
        model="llama3.2",
        temperature=0.7,
        base_url="http://localhost:11434"
    )
    
    def extract_insights(state: LinkedInState) -> LinkedInState:
        """Extract key professional insights from raw content."""
        
        relevant_context = vector_store.get_relevant_context(
            chat_id=state["chat_id"],
            query=state["user_request"],
            n_results=3
        )
        
        context_str = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in relevant_context
        ]) if relevant_context else "No previous context available"
        
        prompt = f"""You are a LinkedIn content strategist expert.

Previous conversation context:
{context_str}

User's request: {state['user_request']}

Raw content to analyze:
{state['raw_content'][:3000]}...

Extract 3-5 key professional insights from this content that would resonate with a LinkedIn audience.
Focus on:
- Actionable takeaways
- Professional lessons
- Industry trends
- Career advice
- Business insights

List the insights clearly and concisely."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        state["key_insights"] = response.content
        state["messages"].append(AIMessage(content=f"💡 **Key Insights Extracted**\n\n{response.content[:150]}..."))
        
        return state
    
    def create_post_draft(state: LinkedInState) -> LinkedInState:
        """Create engaging LinkedIn post draft."""
        
        prompt = f"""You are an expert LinkedIn content creator known for viral posts.

Key insights to work with:
{state['key_insights']}

Original content:
{state['raw_content'][:2000]}...

User's request: {state['user_request']}

Create a compelling LinkedIn post that:
1. Starts with a HOOK - an attention-grabbing first line (max 150 chars)
2. Has 3-4 short paragraphs with line breaks for readability
3. Includes 1-2 key insights with context
4. Uses storytelling or personal angle when appropriate
5. Ends with a question or call-to-action to drive engagement
6. Is between 150-300 words (LinkedIn optimal length)
7. Professional yet conversational tone
8. NO hashtags yet (will be added in refinement)

Write the post in plain text format."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        state["post_draft"] = response.content
        state["messages"].append(AIMessage(content="✍️ **LinkedIn Post Draft Created**"))
        
        return state
    
    def refine_linkedin_post(state: LinkedInState) -> LinkedInState:
        """Refine post and add hashtags, formatting."""
        
        prompt = f"""You are a LinkedIn engagement specialist.

Review this LinkedIn post draft:

{state['post_draft']}

User's request: {state['user_request']}

Refine it by:
1. Ensuring the hook is powerful and scroll-stopping
2. Adding strategic emoji (2-3 max, placed thoughtfully)
3. Improving readability with proper spacing
4. Adding 3-5 relevant hashtags at the end
5. Ensuring proper line breaks between paragraphs
6. Making the CTA more compelling
7. Checking it sounds authentic and conversational

Provide the final, polished LinkedIn post ready to publish.
Format with proper spacing and line breaks."""
        
        response = llm.invoke([HumanMessage(content=prompt)])
        state["final_post"] = response.content
        state["messages"].append(AIMessage(content="✨ **LinkedIn Post Ready!**"))
        
        return state
    
    workflow = StateGraph(LinkedInState)
    
    workflow.add_node("extract_insights", extract_insights)
    workflow.add_node("create_draft", create_post_draft)
    workflow.add_node("refine_post", refine_linkedin_post)
    
    workflow.set_entry_point("extract_insights")
    workflow.add_edge("extract_insights", "create_draft")
    workflow.add_edge("create_draft", "refine_post")
    workflow.add_edge("refine_post", END)
    
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app


def generate_linkedin_post(
    chat_id: int,
    raw_content: str,
    user_request: str,
    platform: str = "LinkedIn"
) -> Dict[str, Any]:
    
    try:
        chat_context = get_or_load_chat_context(chat_id)
        
        workflow = create_linkedin_post_workflow()
        
        initial_state = {
            "messages": [],
            "raw_content": raw_content,
            "platform": platform,
            "user_request": user_request,
            "key_insights": "",
            "post_draft": "",
            "final_post": "",
            "chat_id": chat_id,
            "chat_context": chat_context
        }
        
        config = {"configurable": {"thread_id": f"chat_{chat_id}_linkedin"}}
        final_state = workflow.invoke(initial_state, config)
        
        return {
            "success": True,
            "insights": final_state["key_insights"],
            "draft": final_state["post_draft"],
            "final_post": final_state["final_post"],
            "workflow_messages": final_state["messages"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating LinkedIn post: {str(e)}"
        }
