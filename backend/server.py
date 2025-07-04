from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
import os
from typing import List, Dict, Any, Optional
import httpx
import asyncio
from datetime import datetime
import uuid
from bs4 import BeautifulSoup
import re
import json
import google.generativeai as genai
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Zark AI Knowledge Assistant API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URL)
db = client['knowledge_bot']
knowledge_collection = db['knowledge']
conversations_collection = db['conversations']

# Initialize API Keys
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

# Pydantic models
class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None

class UrlIngestRequest(BaseModel):
    url: str
    depth: int = 1

class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []
    conversation_id: str

class KnowledgeEntry(BaseModel):
    title: str
    content: str
    url: str
    summary: str
    entities: List[str] = []
    tags: List[str] = []

@app.get("/api/")
async def root():
    return {"message": "Zark AI Knowledge Assistant API is running"}

@app.get("/api/health")
async def health_check():
    try:
        # Check MongoDB connection
        db.command('ping')
        
        # Check Groq API
        if not GROQ_API_KEY:
            return {"status": "error", "message": "Groq API key not configured"}
        
        return {"status": "healthy", "mongodb": "connected", "groq": "configured"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_query(request: QueryRequest):
    try:
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Search knowledge base
        relevant_knowledge = await search_knowledge(request.query)
        
        # Prepare context for Gemini
        context = prepare_context(relevant_knowledge, request.query)
        
        # Generate response using Groq
        response = await generate_ai_response(context, request.query)
        
        # Store conversation
        conversation_entry = {
            "id": conversation_id,
            "query": request.query,
            "response": response,
            "sources": [k.get("url", "") for k in relevant_knowledge],
            "timestamp": datetime.utcnow()
        }
        conversations_collection.insert_one(conversation_entry)
        
        return ChatResponse(
            response=response,
            sources=[k.get("url", "") for k in relevant_knowledge],
            conversation_id=conversation_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/api/ingest")
async def ingest_content(request: UrlIngestRequest):
    try:
        ingested_count = await ingest_from_url(request.url, request.depth)
        return {"message": f"Successfully ingested {ingested_count} pages", "url": request.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting content: {str(e)}")

@app.get("/api/knowledge")
async def get_knowledge():
    try:
        knowledge = list(knowledge_collection.find({}, {"_id": 0}).limit(50))
        return {"knowledge": knowledge, "total": len(knowledge)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving knowledge: {str(e)}")

@app.delete("/api/knowledge")
async def clear_knowledge():
    try:
        result = knowledge_collection.delete_many({})
        return {"message": f"Cleared {result.deleted_count} knowledge entries"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing knowledge: {str(e)}")

async def search_knowledge(query: str, limit: int = 5) -> List[Dict]:
    """Search knowledge base using text search and relevance scoring"""
    try:
        # Simple text search - in production, use vector search
        search_results = knowledge_collection.find(
            {"$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"content": {"$regex": query, "$options": "i"}},
                {"summary": {"$regex": query, "$options": "i"}},
                {"tags": {"$in": [query.lower()]}}
            ]},
            {"_id": 0}
        ).limit(limit)
        
        return list(search_results)
    except Exception as e:
        print(f"Search error: {e}")
        return []

def prepare_context(knowledge: List[Dict], query: str) -> str:
    """Prepare context from knowledge base for AI response"""
    if not knowledge:
        return f"Query: {query}\nNo relevant knowledge found in the database. Please provide a concise response in 5 lines or less based on your training data."
    
    context = f"Query: {query}\n\nRelevant Knowledge:\n"
    for i, item in enumerate(knowledge, 1):
        context += f"\n{i}. Title: {item.get('title', 'Unknown')}\n"
        context += f"   Content: {item.get('content', '')[:500]}...\n"
        context += f"   Source: {item.get('url', 'Unknown')}\n"
    
    context += "\nPlease provide a concise response in 5 lines or less based on the above knowledge and your training data. If the user asks for more details, then provide a comprehensive explanation."
    return context

async def generate_ai_response(context: str, query: str) -> str:
    """Generate AI response using Google Gemini"""
    try:
        if not GEMINI_API_KEY:
            return "AI service is not configured. Please set up the Gemini API key."
        
        # Check if user is asking for more details
        is_detailed_request = any(phrase in query.lower() for phrase in [
            "more details", "more information", "explain further", "tell me more", 
            "elaborate", "expand", "comprehensive", "detailed", "in depth"
        ])
        
        if is_detailed_request:
            prompt = f"""You are Zark, a helpful AI knowledge assistant. Answer the user's question comprehensively using the provided context and your knowledge.

{context}

Please provide a detailed, accurate, and helpful response. If you use information from the provided sources, acknowledge them naturally in your response."""
        else:
            prompt = f"""You are Zark, a helpful AI knowledge assistant. Answer the user's question concisely using the provided context and your knowledge.

{context}

Please provide a concise response in 5 lines or less. Be accurate and helpful, but keep it brief unless the user specifically asks for more details."""

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating AI response: {str(e)}"

async def ingest_from_url(url: str, depth: int = 1) -> int:
    """Ingest content from URL with specified depth"""
    ingested_count = 0
    visited_urls = set()
    
    async def scrape_page(page_url: str, current_depth: int):
        nonlocal ingested_count
        
        if current_depth > depth or page_url in visited_urls:
            return
        
        visited_urls.add(page_url)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(page_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract content
                title = soup.find('title')
                title_text = title.get_text().strip() if title else urlparse(page_url).path
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Extract text content
                content = soup.get_text()
                content = re.sub(r'\s+', ' ', content).strip()
                
                if len(content) > 100:  # Only store meaningful content
                    # Generate summary using Gemini
                    summary = await generate_summary(content[:1000])
                    
                    # Extract entities and tags
                    entities = extract_entities(content)
                    tags = extract_tags(title_text, content)
                    
                    # Store in knowledge base
                    knowledge_entry = {
                        "id": str(uuid.uuid4()),
                        "title": title_text,
                        "content": content[:5000],  # Limit content size
                        "url": page_url,
                        "summary": summary,
                        "entities": entities,
                        "tags": tags,
                        "ingested_at": datetime.utcnow()
                    }
                    
                    # Check if already exists
                    existing = knowledge_collection.find_one({"url": page_url})
                    if existing:
                        knowledge_collection.update_one(
                            {"url": page_url},
                            {"$set": knowledge_entry}
                        )
                    else:
                        knowledge_collection.insert_one(knowledge_entry)
                    
                    ingested_count += 1
                    
                    # Extract links for deeper crawling
                    if current_depth < depth:
                        links = soup.find_all('a', href=True)
                        for link in links[:10]:  # Limit links to prevent explosion
                            href = link['href']
                            full_url = urljoin(page_url, href)
                            
                            # Only follow HTTP/HTTPS links on same domain
                            if full_url.startswith(('http://', 'https://')):
                                parsed_original = urlparse(page_url)
                                parsed_new = urlparse(full_url)
                                
                                if parsed_original.netloc == parsed_new.netloc:
                                    await scrape_page(full_url, current_depth + 1)
                
        except Exception as e:
            print(f"Error scraping {page_url}: {e}")
    
    await scrape_page(url, 1)
    return ingested_count

async def generate_summary(content: str) -> str:
    """Generate summary using Gemini"""
    try:
        if not GEMINI_API_KEY:
            return content[:200] + "..."
        
        prompt = f"Summarize the following content in 2-3 sentences:\n\n{content}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return content[:200] + "..."

def extract_entities(content: str) -> List[str]:
    """Extract basic entities from content"""
    # Simple entity extraction - in production, use NLP libraries
    entities = []
    
    # Extract capitalized words (potential proper nouns)
    words = re.findall(r'\b[A-Z][a-z]+\b', content)
    entities.extend(list(set(words))[:10])  # Limit to 10 entities
    
    return entities

def extract_tags(title: str, content: str) -> List[str]:
    """Extract tags from title and content"""
    tags = []
    
    # Extract keywords from title
    title_words = re.findall(r'\b\w+\b', title.lower())
    tags.extend([word for word in title_words if len(word) > 3])
    
    # Extract common technical terms
    tech_terms = ['api', 'database', 'server', 'client', 'web', 'mobile', 'app', 'software', 'hardware']
    for term in tech_terms:
        if term in content.lower():
            tags.append(term)
    
    return list(set(tags))[:10]  # Limit to 10 tags

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)