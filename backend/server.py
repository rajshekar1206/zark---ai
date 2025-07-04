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
from groq import Groq
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv

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
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
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
        print(f"Starting ingestion for URL: {request.url}")
        ingested_count = await ingest_from_url(request.url, request.depth)
        
        # Verify the content was actually stored
        total_entries = knowledge_collection.count_documents({})
        print(f"Total entries in knowledge base after ingestion: {total_entries}")
        
        return {
            "message": f"Successfully ingested {ingested_count} pages from {request.url}",
            "url": request.url,
            "total_entries": total_entries
        }
    except Exception as e:
        print(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Error ingesting content: {str(e)}")

@app.get("/api/knowledge")
async def get_knowledge():
    try:
        # Get total count
        total_count = knowledge_collection.count_documents({})
        
        # Get recent entries with more details
        knowledge = list(knowledge_collection.find(
            {},
            {"_id": 0, "content": 0}  # Exclude large content field for overview
        ).sort("ingested_at", -1).limit(10))
        
        return {
            "knowledge": knowledge,
            "total": total_count,
            "recent_count": len(knowledge)
        }
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
        # Get total count first
        total_count = knowledge_collection.count_documents({})
        print(f"Total knowledge entries: {total_count}")
        
        # Split query into words for better matching
        query_words = query.lower().split()
        
        # Create search conditions
        search_conditions = []
        
        # Add regex search for each word
        for word in query_words:
            if len(word) > 2:  # Only search for words longer than 2 characters
                search_conditions.extend([
                    {"title": {"$regex": word, "$options": "i"}},
                    {"content": {"$regex": word, "$options": "i"}},
                    {"summary": {"$regex": word, "$options": "i"}},
                    {"tags": {"$in": [word]}}
                ])
        
        # Add original query search
        search_conditions.extend([
            {"title": {"$regex": query, "$options": "i"}},
            {"content": {"$regex": query, "$options": "i"}},
            {"summary": {"$regex": query, "$options": "i"}},
            {"tags": {"$in": [query.lower()]}}
        ])
        
        # If no specific matches, return recent entries
        if not search_conditions:
            search_results = knowledge_collection.find(
                {},
                {"_id": 0}
            ).sort("ingested_at", -1).limit(limit)
        else:
            search_results = knowledge_collection.find(
                {"$or": search_conditions},
                {"_id": 0}
            ).limit(limit)
        
        results = list(search_results)
        print(f"Search for '{query}' returned {len(results)} results")
        
        # If no results from query, return some recent entries
        if not results and total_count > 0:
            print("No specific matches found, returning recent entries")
            search_results = knowledge_collection.find(
                {},
                {"_id": 0}
            ).sort("ingested_at", -1).limit(limit)
            results = list(search_results)
            print(f"Returning {len(results)} recent entries")
        
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

def prepare_context(knowledge: List[Dict], query: str) -> str:
    """Prepare context from knowledge base for AI response"""
    # Get total knowledge count
    total_count = knowledge_collection.count_documents({})
    
    if not knowledge:
        if total_count > 0:
            return f"Query: {query}\n\nI have access to {total_count} knowledge entries, but none directly match your query. Let me provide a response based on my training data and general knowledge."
        else:
            return f"Query: {query}\n\nNo knowledge entries found in the database. Please provide a concise response based on your training data."
    
    context = f"Query: {query}\n\nI have access to {total_count} total knowledge entries. Here are the most relevant ones:\n"
    for i, item in enumerate(knowledge, 1):
        context += f"\n{i}. Title: {item.get('title', 'Unknown')}\n"
        context += f"   Content: {item.get('content', '')[:500]}...\n"
        context += f"   Source: {item.get('url', 'Unknown')}\n"
    
    context += "\nPlease provide a helpful response based on the above knowledge and your training data. Be informative and accurate."
    return context

async def generate_ai_response(context: str, query: str) -> str:
    """Generate AI response using Groq"""
    try:
        if not GROQ_API_KEY:
            return "AI service is not configured. Please set up the Groq API key."
        
        # Check if user is asking for more details
        is_detailed_request = any(phrase in query.lower() for phrase in [
            "more details", "more information", "explain further", "tell me more", 
            "elaborate", "expand", "comprehensive", "detailed", "in depth"
        ])
        
        if is_detailed_request:
            prompt = f"""You are Zark, an AI assistant. Answer comprehensively using the provided context.

{context}

Provide a detailed, accurate response. If you use information from sources, acknowledge them naturally."""
        else:
            prompt = f"""You are Zark, an AI assistant. Answer concisely using the provided context.

{context}

Provide a brief response in 5 lines or less. Be accurate and helpful."""

        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are Zark, a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            model="llama3-70b-8192",
            max_tokens=1024,
            temperature=0.7
        )
        
        return response.choices[0].message.content
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
                    # Generate enhanced summary
                    summary = await generate_enhanced_summary(content[:1000], title_text)
                    
                    # Extract enhanced entities and tags
                    entities = extract_enhanced_entities(content)
                    tags = extract_enhanced_tags(title_text, content)
                    keywords = extract_keywords(title_text, content)
                    
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




async def generate_enhanced_summary(content: str, title: str) -> str:
    """Generate enhanced summary using Groq with title context"""
    try:
        if not GROQ_API_KEY:
            return content[:300] + "..."
        
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant that creates concise, informative summaries."},
                {"role": "user", "content": f"Create a comprehensive summary of this content about '{title}':\n\n{content}"}
            ],
            model="llama3-70b-8192",
            max_tokens=200,
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"Enhanced summary generation error: {e}")
        return content[:300] + "..."

def extract_enhanced_entities(content: str) -> List[str]:
    """Extract enhanced entities from content"""
    entities = []
    
    # Extract capitalized words (potential proper nouns)
    words = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', content)
    entities.extend(list(set(words))[:15])
    
    # Extract dates
    dates = re.findall(r'\b\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{1,2}\s\w+\s\d{4}\b', content)
    entities.extend(dates[:5])
    
    # Extract numbers with units
    numbers = re.findall(r'\b\d+(?:\.\d+)?\s*(?:percent|%|million|billion|thousand|km|miles|years?|days?)\b', content, re.IGNORECASE)
    entities.extend(numbers[:5])
    
    return list(set(entities))[:20]

def extract_enhanced_tags(title: str, content: str) -> List[str]:
    """Extract enhanced tags from title and content"""
    tags = []
    
    # Extract keywords from title
    title_words = re.findall(r'\b\w+\b', title.lower())
    tags.extend([word for word in title_words if len(word) > 3])
    
    # Common topic categories
    categories = {
        'technology': ['technology', 'software', 'computer', 'digital', 'internet', 'ai', 'artificial intelligence', 'machine learning'],
        'science': ['science', 'research', 'study', 'experiment', 'discovery', 'theory'],
        'history': ['history', 'historical', 'ancient', 'century', 'war', 'empire'],
        'geography': ['country', 'city', 'region', 'continent', 'ocean', 'mountain'],
        'business': ['company', 'business', 'economy', 'market', 'industry', 'financial'],
        'health': ['health', 'medical', 'disease', 'treatment', 'medicine', 'hospital']
    }
    
    content_lower = content.lower()
    for category, keywords in categories.items():
        if any(keyword in content_lower for keyword in keywords):
            tags.append(category)
    
    # Extract frequent meaningful words
    words = re.findall(r'\b[a-zA-Z]{4,}\b', content.lower())
    word_freq = {}
    for word in words:
        word_freq[word] = word_freq.get(word, 0) + 1
    
    frequent_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    tags.extend([word for word, freq in frequent_words[:10] if freq > 2])
    
    return list(set(tags))[:15]

def extract_keywords(title: str, content: str) -> List[str]:
    """Extract searchable keywords from content"""
    keywords = []
    
    # Title words
    title_words = re.findall(r'\b\w+\b', title.lower())
    keywords.extend([word for word in title_words if len(word) > 2])
    
    # Important phrases (quoted text, bold text indicators)
    phrases = re.findall(r'"([^"]+)"', content)
    for phrase in phrases:
        keywords.extend(phrase.lower().split())
    
    # Words that appear multiple times
    words = re.findall(r'\b[a-zA-Z]{3,}\b', content.lower())
    word_count = {}
    for word in words:
        word_count[word] = word_count.get(word, 0) + 1
    
    # Add words that appear 3+ times
    frequent_keywords = [word for word, count in word_count.items() if count >= 3]
    keywords.extend(frequent_keywords[:20])
    
    return list(set(keywords))[:25]
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