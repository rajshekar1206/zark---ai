import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [ingestUrl, setIngestUrl] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [knowledgeCount, setKnowledgeCount] = useState(0);
  const [apiHealth, setApiHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('chat');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    checkApiHealth();
    getKnowledgeCount();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const checkApiHealth = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/health`);
      const data = await response.json();
      setApiHealth(data);
    } catch (error) {
      setApiHealth({ status: 'error', message: 'Cannot connect to server' });
    }
  };

  const getKnowledgeCount = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/knowledge`);
      const data = await response.json();
      setKnowledgeCount(data.total);
    } catch (error) {
      console.error('Error fetching knowledge count:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: inputMessage,
          conversation_id: conversationId
        })
      });

      const data = await response.json();

      if (response.ok) {
        const botMessage = {
          id: Date.now() + 1,
          type: 'bot',
          content: data.response,
          sources: data.sources,
          timestamp: new Date().toLocaleTimeString()
        };

        setMessages(prev => [...prev, botMessage]);
        setConversationId(data.conversation_id);
      } else {
        throw new Error(data.detail || 'Error processing message');
      }
    } catch (error) {
      const errorMessage = {
        id: Date.now() + 1,
        type: 'error',
        content: `Error: ${error.message}`,
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleIngestUrl = async () => {
    if (!ingestUrl.trim()) return;

    setIsIngesting(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: ingestUrl,
          depth: 2
        })
      });

      const data = await response.json();

      if (response.ok) {
        alert(`Successfully ingested content: ${data.message}`);
        setIngestUrl('');
        getKnowledgeCount();
      } else {
        throw new Error(data.detail || 'Error ingesting content');
      }
    } catch (error) {
      alert(`Error ingesting content: ${error.message}`);
    } finally {
      setIsIngesting(false);
    }
  };

  const clearKnowledge = async () => {
    if (window.confirm('Are you sure you want to clear all knowledge?')) {
      try {
        const response = await fetch(`${BACKEND_URL}/api/knowledge`, {
          method: 'DELETE'
        });
        const data = await response.json();
        alert(data.message);
        getKnowledgeCount();
      } catch (error) {
        alert(`Error clearing knowledge: ${error.message}`);
      }
    }
  };

  const clearChat = () => {
    setMessages([]);
    setConversationId(null);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="app">
      <div className="app-header">
        <div className="header-content">
          <h1>🤖 Universal Knowledge Bot</h1>
          <p>Ask me anything - I'm powered by the world's knowledge!</p>
          <div className="status-indicators">
            <div className={`status-indicator ${apiHealth?.status === 'healthy' ? 'healthy' : 'error'}`}>
              {apiHealth?.status === 'healthy' ? '🟢' : '🔴'} API Status
            </div>
            <div className="knowledge-count">
              📚 Knowledge Base: {knowledgeCount} entries
            </div>
          </div>
        </div>
      </div>

      <div className="app-body">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            💬 Chat
          </button>
          <button 
            className={`tab ${activeTab === 'manage' ? 'active' : ''}`}
            onClick={() => setActiveTab('manage')}
          >
            ⚙️ Manage Knowledge
          </button>
        </div>

        {activeTab === 'chat' ? (
          <div className="chat-container">
            <div className="chat-header">
              <h3>Chat with Universal Bot</h3>
              <button onClick={clearChat} className="clear-button">
                🗑️ Clear Chat
              </button>
            </div>
            
            <div className="messages-container">
              {messages.length === 0 ? (
                <div className="welcome-message">
                  <div className="welcome-content">
                    <h3>👋 Welcome to Universal Knowledge Bot!</h3>
                    <p>I can help you with questions about any topic. Try asking me:</p>
                    <ul>
                      <li>📚 "What is quantum computing?"</li>
                      <li>🌍 "Tell me about climate change"</li>
                      <li>💻 "How does machine learning work?"</li>
                      <li>🔬 "Explain photosynthesis"</li>
                    </ul>
                    <p>Or ingest some web content first and ask specific questions about it!</p>
                  </div>
                </div>
              ) : (
                messages.map((message) => (
                  <div key={message.id} className={`message ${message.type}`}>
                    <div className="message-content">
                      <div className="message-text">{message.content}</div>
                      {message.sources && message.sources.length > 0 && (
                        <div className="message-sources">
                          <strong>Sources:</strong>
                          {message.sources.map((source, index) => (
                            <a key={index} href={source} target="_blank" rel="noopener noreferrer">
                              {source}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="message-timestamp">{message.timestamp}</div>
                  </div>
                ))
              )}
              
              {isLoading && (
                <div className="message bot loading">
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything..."
                disabled={isLoading}
                rows={3}
              />
              <button 
                onClick={handleSendMessage} 
                disabled={isLoading || !inputMessage.trim()}
                className="send-button"
              >
                {isLoading ? '⏳' : '🚀'} Send
              </button>
            </div>
          </div>
        ) : (
          <div className="manage-container">
            <div className="manage-section">
              <h3>🌐 Ingest Web Content</h3>
              <p>Add knowledge from any website to expand my capabilities!</p>
              <div className="ingest-form">
                <input
                  type="url"
                  value={ingestUrl}
                  onChange={(e) => setIngestUrl(e.target.value)}
                  placeholder="Enter URL (e.g., https://example.com)"
                  disabled={isIngesting}
                />
                <button 
                  onClick={handleIngestUrl} 
                  disabled={isIngesting || !ingestUrl.trim()}
                  className="ingest-button"
                >
                  {isIngesting ? '⏳ Ingesting...' : '📥 Ingest Content'}
                </button>
              </div>
              <div className="ingest-info">
                <p>💡 <strong>Tips:</strong></p>
                <ul>
                  <li>Try documentation sites like MDN, Wikipedia, or tech blogs</li>
                  <li>The bot will crawl the page and related links</li>
                  <li>Processing may take a few minutes for large sites</li>
                </ul>
              </div>
            </div>

            <div className="manage-section">
              <h3>📊 Knowledge Base Management</h3>
              <div className="knowledge-stats">
                <div className="stat">
                  <div className="stat-value">{knowledgeCount}</div>
                  <div className="stat-label">Total Entries</div>
                </div>
              </div>
              <div className="management-buttons">
                <button onClick={getKnowledgeCount} className="refresh-button">
                  🔄 Refresh Count
                </button>
                <button onClick={clearKnowledge} className="danger-button">
                  🗑️ Clear All Knowledge
                </button>
              </div>
            </div>

            <div className="manage-section">
              <h3>🔧 System Status</h3>
              <div className="system-status">
                <div className="status-item">
                  <span className="status-label">API Status:</span>
                  <span className={`status-value ${apiHealth?.status === 'healthy' ? 'healthy' : 'error'}`}>
                    {apiHealth?.status === 'healthy' ? '✅ Healthy' : '❌ Error'}
                  </span>
                </div>
                <div className="status-item">
                  <span className="status-label">MongoDB:</span>
                  <span className="status-value">
                    {apiHealth?.mongodb === 'connected' ? '✅ Connected' : '❌ Disconnected'}
                  </span>
                </div>
                <div className="status-item">
                  <span className="status-label">AI Engine:</span>
                  <span className="status-value">
                    {apiHealth?.gemini === 'configured' ? '✅ Google Gemini Ready' : '❌ Not Configured'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;