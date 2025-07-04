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
    show_sources: bool = False  # New field to control source display

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

@app.get("/api/help")
async def get_help():
    """Get help information about how Zark-AI works"""
    try:
        total_entries = knowledge_collection.count_documents({})
        api_status = "configured" if GROQ_API_KEY else "not_configured"
        
        return {
            "bot_name": "Zark-AI",
            "version": "2.0",
            "api_status": api_status,
            "knowledge_entries": total_entries,
            "capabilities": {
                "online_mode": {
                    "description": "Full AI capabilities with Groq API",
                    "features": [
                        "Advanced natural language understanding",
                        "Contextual responses based on website content",
                        "Intelligent content analysis",
                        "Complex question answering",
                        "Website content ingestion and understanding"
                    ],
                    "enabled": bool(GROQ_API_KEY)
                },
                "offline_mode": {
                    "description": "Limited functionality without API",
                    "features": [
                        "Basic responses only",
                        "Simple pattern matching",
                        "Limited content understanding"
                    ],
                    "enabled": not bool(GROQ_API_KEY)
                }
            },
            "how_to_use": {
                "add_content": "Go to 'Manage' tab and paste any website URL to add it to my knowledge base",
                "ask_questions": "Ask me anything about the content you've added or general questions",
                "best_practices": [
                    "Add relevant websites before asking specific questions",
                    "Ask specific questions about the content",
                    "Use 'New Chat' to start fresh conversations"
                ]
            },
            "setup_instructions": {
                "for_online_mode": [
                    "Get a Groq API key from https://groq.com/",
                    "Add GROQ_API_KEY to your environment variables",
                    "Restart the backend service",
                    "Bot status will show 'Online' when properly configured"
                ]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting help: {str(e)}")

@app.get("/api/status")
async def get_detailed_status():
    """Get detailed status information"""
    try:
        total_entries = knowledge_collection.count_documents({})
        recent_entries = list(knowledge_collection.find(
            {}, 
            {"title": 1, "url": 1, "ingested_at": 1, "_id": 0}
        ).sort("ingested_at", -1).limit(5))
        
        return {
            "status": "healthy" if GROQ_API_KEY else "limited",
            "api_configured": bool(GROQ_API_KEY),
            "mongodb_connected": True,
            "knowledge_base": {
                "total_entries": total_entries,
                "recent_entries": recent_entries
            },
            "capabilities": "full" if GROQ_API_KEY else "limited"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "api_configured": bool(GROQ_API_KEY),
            "mongodb_connected": False
        }

@app.post("/api/chat", response_model=ChatResponse)
async def chat_query(request: QueryRequest):
    try:
        print(f"Chat request: query='{request.query}', show_sources={request.show_sources}")
        
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Search knowledge base
        relevant_knowledge = await search_knowledge(request.query)
        print(f"Found {len(relevant_knowledge)} relevant knowledge entries")
        
        # Prepare context for AI response
        context = prepare_context(relevant_knowledge, request.query)
        
        # Generate response using Groq
        response = await generate_ai_response(context, request.query, request.show_sources)
        
        # Extract sources from relevant knowledge
        sources = []
        if request.show_sources and relevant_knowledge:
            for k in relevant_knowledge:
                url = k.get("url", "")
                title = k.get("title", "Unknown Source")
                if url:
                    sources.append(f"{title}: {url}")
        
        print(f"Returning {len(sources)} sources")
        
        # Store conversation
        conversation_entry = {
            "id": conversation_id,
            "query": request.query,
            "response": response,
            "sources": sources,
            "timestamp": datetime.utcnow()
        }
        conversations_collection.insert_one(conversation_entry)
        
        return ChatResponse(
            response=response,
            sources=sources,
            conversation_id=conversation_id
        )
    except Exception as e:
        print(f"Chat error: {e}")
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
    """Enhanced search knowledge base using multiple search strategies"""
    try:
        # Get total count first
        total_count = knowledge_collection.count_documents({})
        print(f"Total knowledge entries: {total_count}")
        
        # Split query into words for better matching
        query_words = [word.lower() for word in query.split() if len(word) > 2]
        
        # Create multiple search strategies
        search_conditions = []
        
        # Strategy 1: Exact phrase search
        search_conditions.extend([
            {"title": {"$regex": query, "$options": "i"}},
            {"content": {"$regex": query, "$options": "i"}},
            {"summary": {"$regex": query, "$options": "i"}}
        ])
        
        # Strategy 2: Individual word search with higher priority on title/summary
        for word in query_words:
            search_conditions.extend([
                {"title": {"$regex": word, "$options": "i"}},
                {"summary": {"$regex": word, "$options": "i"}},
                {"keywords": {"$in": [word]}},
                {"tags": {"$in": [word]}},
                {"entities": {"$in": [word.title()]}},
                {"content": {"$regex": word, "$options": "i"}}
            ])
        
        # Strategy 3: Domain-specific search
        if "what is" in query.lower() or "tell me about" in query.lower():
            # Extract the main topic
            topic_match = re.search(r'(?:what is|tell me about|explain)\s+(.+?)(?:\?|$)', query.lower())
            if topic_match:
                topic = topic_match.group(1).strip()
                search_conditions.extend([
                    {"title": {"$regex": topic, "$options": "i"}},
                    {"tags": {"$in": [topic]}},
                    {"keywords": {"$in": [topic]}}
                ])
        
        # Perform search with different strategies
        results = []
        
        if search_conditions:
            # Primary search
            search_results = knowledge_collection.find(
                {"$or": search_conditions},
                {"_id": 0}
            ).sort("ingested_at", -1).limit(limit)
            results = list(search_results)
        
        print(f"Primary search for '{query}' returned {len(results)} results")
        
        # If no results, try fallback searches
        if not results and total_count > 0:
            print("No primary matches found, trying fallback searches...")
            
            # Fallback 1: Partial word matching
            fallback_conditions = []
            for word in query_words:
                if len(word) > 3:
                    fallback_conditions.extend([
                        {"title": {"$regex": f".*{word}.*", "$options": "i"}},
                        {"content": {"$regex": f".*{word}.*", "$options": "i"}}
                    ])
            
            if fallback_conditions:
                search_results = knowledge_collection.find(
                    {"$or": fallback_conditions},
                    {"_id": 0}
                ).limit(limit)
                results = list(search_results)
                print(f"Fallback search returned {len(results)} results")
        
        # If still no results, return recent entries
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
    """Prepare enhanced context from knowledge base for AI response"""
    # Get total knowledge count
    total_count = knowledge_collection.count_documents({})
    
    if not knowledge:
        if total_count > 0:
            return f"Query: {query}\n\nI have access to {total_count} knowledge entries in my database, but none directly match your specific query. I'll provide a response based on my general knowledge and training data."
        else:
            return f"Query: {query}\n\nNo knowledge entries found in the database. I'll provide a response based on my general knowledge and training data."
    
    # Check if we have relevant knowledge
    context = f"Query: {query}\n\n"
    context += f"I have access to {total_count} total knowledge entries. Here are the most relevant ones for your question:\n"
    
    for i, item in enumerate(knowledge, 1):
        context += f"\n--- Source {i}: {item.get('title', 'Unknown')} ---\n"
        context += f"URL: {item.get('url', 'Unknown')}\n"
        
        # Include summary if available
        if item.get('summary'):
            context += f"Summary: {item.get('summary', '')}\n"
        
        # Include relevant content sections
        content = item.get('content', '')
        if content:
            # Try to find the most relevant part of the content for the query
            query_words = query.lower().split()
            content_lower = content.lower()
            
            # Find sentences that contain query words
            sentences = content.split('. ')
            relevant_sentences = []
            for sentence in sentences:
                if any(word in sentence.lower() for word in query_words if len(word) > 2):
                    relevant_sentences.append(sentence.strip())
                    if len(relevant_sentences) >= 3:  # Limit to 3 most relevant sentences
                        break
            
            if relevant_sentences:
                context += f"Relevant Content: {'. '.join(relevant_sentences)}\n"
            else:
                context += f"Content: {content[:800]}...\n"
        
        # Include tags if available
        if item.get('tags'):
            context += f"Tags: {', '.join(item.get('tags', [])[:5])}\n"
    
    context += "\nBased on the above information from my knowledge base, please provide a comprehensive and accurate answer to the user's question. If the information directly answers their question, prioritize that content. If they're asking for specific details about the website content, reference the relevant sections."
    
    return context

async def generate_ai_response(context: str, query: str, show_sources: bool = False) -> str:
    """Generate AI response using Groq with enhanced error handling"""
    try:
        if not GROQ_API_KEY:
            return """🔴 **OFFLINE MODE**: I'm currently running in offline mode because the Groq API key is not configured. 
            
**How Zark-AI Works:**

🟢 **ONLINE MODE** (When API key is configured):
- I can access advanced AI capabilities through Groq's llama3-70b-8192 model
- I can provide detailed, contextual responses
- I can analyze and understand website content you add
- I can answer complex questions with nuanced understanding

🔴 **OFFLINE MODE** (Current state):
- Basic responses only
- Limited to simple pattern matching
- Cannot generate intelligent responses
- Cannot properly analyze website content

**To Enable Online Mode:**
1. Get a Groq API key from https://groq.com/
2. Add it to your environment variables as GROQ_API_KEY
3. Restart the backend service

**Current Query**: I cannot properly answer your question about: "{query}" in offline mode."""
        
        # Check if user is asking for sources
        wants_sources = show_sources or any(phrase in query.lower() for phrase in [
            "source", "sources", "where did you get", "reference", "link", "url", "website", "citation", "cite"
        ])
        
        # Check if user is asking for more details
        is_detailed_request = any(phrase in query.lower() for phrase in [
            "more details", "more information", "explain further", "tell me more", 
            "elaborate", "expand", "comprehensive", "detailed", "in depth"
        ])
        
        # Enhanced system prompt to make Zark more conversational and helpful
        system_prompt = """You are Zark, a friendly and intelligent AI assistant. You have access to a comprehensive knowledge database and can answer questions on a wide variety of topics.

Your personality:
- Friendly, approachable, and helpful
- Always eager to assist and provide valuable information
- Enthusiastic about learning and sharing knowledge
- Clear and concise in your responses
- Able to understand context and provide relevant answers

Your capabilities:
- Answer questions on any topic with accuracy
- Understand context and provide relevant information
- Analyze and explain complex topics in simple terms
- Help with research, explanations, and problem-solving
- Provide comprehensive answers when requested

Instructions:
- Always be helpful and try to answer every question to the best of your ability
- Use the provided context from your knowledge database when relevant
- If you don't have specific information, use your general knowledge to provide a helpful response
- Be conversational and engaging in your responses
- Don't mention technical details about your knowledge database unless specifically asked"""

        if wants_sources:
            if is_detailed_request:
                prompt = f"""{system_prompt}

{context}

The user is asking for detailed information and wants to know about sources. Provide a comprehensive, accurate response using the provided context. When you have information from the knowledge database, mention where it came from naturally in your response."""
            else:
                prompt = f"""{system_prompt}

{context}

The user wants to know about sources. Provide a clear, informative response using the provided context. When you reference information from the knowledge database, acknowledge where it came from."""
        else:
            if is_detailed_request:
                prompt = f"""{system_prompt}

{context}

The user is asking for detailed information. Provide a comprehensive, accurate response using the provided context. Focus on being thorough and informative."""
            else:
                prompt = f"""{system_prompt}

{context}

Provide a clear, helpful, and engaging response. Use the provided context when relevant, but focus on being conversational and informative."""

        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model="llama3-70b-8192",
            max_tokens=1024,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        error_message = str(e)
        if "api" in error_message.lower() or "key" in error_message.lower():
            return f"""🔴 **API ERROR**: There's an issue with the AI service connection. 

**Error Details**: {error_message}

**What this means:**
- The Groq API key might be invalid or expired
- There might be network connectivity issues
- The API service might be temporarily unavailable

**Troubleshooting:**
1. Check if your Groq API key is valid
2. Verify internet connectivity
3. Try again in a few moments

**Your Question**: "{query}"
I cannot provide a proper AI-generated response due to the API issue above."""
        else:
            return f"⚠️ **Processing Error**: I encountered an error while processing your question: {error_message}. Please try rephrasing your question or try again later."

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
                    summary = await generate_enhanced_summary(content[:2000], title_text)
                    
                    # Extract enhanced entities and tags
                    entities = extract_enhanced_entities(content)
                    tags = extract_enhanced_tags(title_text, content)
                    keywords = extract_keywords(title_text, content)
                    
                    # Store in knowledge base with enhanced metadata
                    knowledge_entry = {
                        "id": str(uuid.uuid4()),
                        "title": title_text,
                        "content": content[:8000],  # Increased content size
                        "url": page_url,
                        "summary": summary,
                        "entities": entities,
                        "tags": tags,
                        "keywords": keywords,
                        "content_type": "webpage",
                        "domain": urlparse(page_url).netloc,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)