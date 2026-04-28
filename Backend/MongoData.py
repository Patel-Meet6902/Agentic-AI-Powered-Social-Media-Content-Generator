from pymongo import MongoClient
from datetime import datetime
import os
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
DB_name = "socialmedia_app"
db = client[DB_name]
chats_collection = db["chats"]
messages_collection = db["messages"]


def get_next_chat_id():
    count = chats_collection.count_documents({})
    return count + 1

def create_new_chat(chat_name, platform="LinkedIn"):
    chat_id = get_next_chat_id()
    chat_data = {
        "_id": chat_id,
        "chat_name": chat_name,
        "platform": platform,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    chats_collection.insert_one(chat_data)
    return chat_id

def save_message(chat_id, role, content, platform=None, source=None, extracted_content=None):
    message_data = {
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow()
    }
    if platform:
        message_data["platform"] = platform
    if source:
        message_data["source"] = source
        message_data["extracted_content"] = extracted_content
    
    result = messages_collection.insert_one(message_data)
    
    vector_store.add_message_to_store(
        chat_id=chat_id,
        message_id=str(result.inserted_id),
        role=role,
        content=content
    )
  
    chats_collection.update_one(
        {"_id": chat_id}, 
        {"$set": {"updated_at": datetime.utcnow()}}
    )

def get_all_chats():
    return list(chats_collection.find(
        {}, 
        {"_id": 1, "chat_name": 1, "platform": 1, "updated_at": 1}
    ).sort("updated_at", -1))

def get_chat_messages(chat_id):
    return list(messages_collection.find(
        {"chat_id": chat_id}
    ).sort("timestamp", 1))

def delete_chat(chat_id):

    messages_collection.delete_many({"chat_id": chat_id})
    chats_collection.delete_one({"_id": chat_id})

    vector_store.delete_chat_from_store(chat_id)

def get_chat_info(chat_id):
    return chats_collection.find_one({"_id": chat_id})




class ChromaVectorStore:
    
    def __init__(self, persist_directory="./chroma_db"):
        
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.collection = self.client.get_or_create_collection(
            name="chat_messages",
            metadata={"description": "Chat history for context retrieval"}
        )
    
    def _generate_embedding(self, text: str) -> List[float]:
        return self.embedding_model.encode(text).tolist()
    
    def add_message_to_store(
        self, 
        chat_id: int, 
        message_id: str, 
        role: str, 
        content: str
    ):

        try:
            embedding = self._generate_embedding(content)
            
            self.collection.add(
                embeddings=[embedding],
                documents=[content],
                metadatas=[{
                    "chat_id": str(chat_id),
                    "role": role,
                    "message_id": message_id,
                    "timestamp": datetime.utcnow().isoformat()
                }],
                ids=[f"chat_{chat_id}_msg_{message_id}"]
            )
        except Exception as e:
            print(f"Error adding to vector store: {e}")
    
    def get_relevant_context(
        self, 
        chat_id: int, 
        query: str, 
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
    
        try:
            query_embedding = self._generate_embedding(query)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where={"chat_id": str(chat_id)}
            )
            
            relevant_messages = []
            if results['documents'] and len(results['documents'][0]) > 0:
                for i in range(len(results['documents'][0])):
                    relevant_messages.append({
                        "content": results['documents'][0][i],
                        "role": results['metadatas'][0][i]['role'],
                        "timestamp": results['metadatas'][0][i]['timestamp']
                    })
            
            return relevant_messages
            
        except Exception as e:
            print(f"Error querying vector store: {e}")
            return []
    
    def load_chat_history_to_store(self, chat_id: int):
        
        try:
    
            messages = get_chat_messages(chat_id)
            
            for msg in messages:
                message_id = str(msg['_id'])
                
            
                try:
                    existing = self.collection.get(
                        ids=[f"chat_{chat_id}_msg_{message_id}"]
                    )
                    if existing['ids']:
                        continue 
                except:
                    pass
                
                self.add_message_to_store(
                    chat_id=chat_id,
                    message_id=message_id,
                    role=msg['role'],
                    content=msg['content']
                )
            
            print(f"Loaded {len(messages)} messages to vector store for chat {chat_id}")
            
        except Exception as e:
            print(f"Error loading chat history: {e}")
    
    def delete_chat_from_store(self, chat_id: int):
        
        try:
            results = self.collection.get(
                where={"chat_id": str(chat_id)}
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                print(f"Deleted {len(results['ids'])} messages from vector store")
        
        except Exception as e:
            print(f"Error deleting from vector store: {e}")
    
    def get_full_chat_context(self, chat_id: int) -> str:
        
        messages = get_chat_messages(chat_id)
        
        context_lines = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)


vector_store = ChromaVectorStore()


def get_or_load_chat_context(chat_id: int) -> str:
    
    vector_store.load_chat_history_to_store(chat_id)
    return vector_store.get_full_chat_context(chat_id)