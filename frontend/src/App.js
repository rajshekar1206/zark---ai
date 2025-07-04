import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

// Zark Robot Icon Component
const ZarkRobot = ({ size = 'medium' }) => {
  return (
    <div className={`zark-robot zark-robot-${size}`}>
      <div className="robot-head">
        <div className="robot-antennas">
          <div className="robot-antenna"></div>
          <div className="robot-antenna"></div>
        </div>
        <div className="robot-visor">
          <div className="robot-eyes">
            <div className="robot-eye"></div>
            <div className="robot-eye"></div>
          </div>
        </div>
      </div>
      <div className="robot-body"></div>
    </div>
  );
};

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [insertUrl, setInsertUrl] = useState('');
  const [isInserting, setIsInserting] = useState(false);
  const [knowledgeCount, setKnowledgeCount] = useState(0);
  const [apiHealth, setApiHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('chat');
  const messagesEndRef = useRef(null);

  const [detailedStatus, setDetailedStatus] = useState(null);
  const [showHelp, setShowHelp] = useState(false);
  const [helpInfo, setHelpInfo] = useState(null);

  const getHelpInfo = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/help`);
      const data = await response.json();
      setHelpInfo(data);
      setShowHelp(true);
    } catch (error) {
      console.error('Error fetching help info:', error);
    }
  };

  useEffect(() => {
    checkApiHealth();
    getKnowledgeCount();
    getDetailedStatus();
  }, []);

  const getDetailedStatus = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/status`);
      const data = await response.json();
      setDetailedStatus(data);
    } catch (error) {
      console.error('Error fetching detailed status:', error);
    }
  };

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
    const currentMessage = inputMessage;
    setInputMessage('');
    setIsLoading(true);

    try {
      // Check if user is asking for sources
      const wantsSource = /\b(source|sources|where did you get|reference|link|url|website)\b/i.test(currentMessage);
      
      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: currentMessage,
          conversation_id: conversationId,
          show_sources: wantsSource  // Only show sources if explicitly requested in the query
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

  const handleInsertUrl = async () => {
    if (!insertUrl.trim()) return;

    setIsInserting(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: insertUrl,
          depth: 2
        })
      });

      const data = await response.json();

      if (response.ok) {
        alert(`Successfully inserted content: ${data.message}`);
        setInsertUrl('');
        getKnowledgeCount();
      } else {
        throw new Error(data.detail || 'Error inserting content');
      }
    } catch (error) {
      alert(`Error inserting content: ${error.message}`);
    } finally {
      setIsInserting(false);
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
    setInputMessage('');
  };

  const startNewConversation = () => {
    setMessages([]);
    setConversationId(null);
    setInputMessage('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="app">
      <div className="night-sky">
        <div className="stars">
          {[...Array(20)].map((_, i) => (
            <div key={i} className="star"></div>
          ))}
        </div>
        <div className="moon"></div>
        <div className="clouds">
          <div className="cloud cloud1"></div>
          <div className="cloud cloud2"></div>
          <div className="cloud cloud3"></div>
        </div>
        <div className="shooting-star shooting-star1"></div>
        <div className="shooting-star shooting-star2"></div>
        <div className="shooting-star shooting-star3"></div>
      </div>

      <div className="floating-orbs">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
        <div className="orb orb-4"></div>
        <div className="orb orb-5"></div>
      </div>

      <div className="app-container">
        <div className="tabs-container">
          <button 
            className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            <span className="tab-icon">💬</span>
            <span>Chat with Zark</span>
          </button>
          <button 
            className={`tab ${activeTab === 'manage' ? 'active' : ''}`}
            onClick={() => setActiveTab('manage')}
          >
            <span className="tab-icon">⚙️</span>
            <span>Manage</span>
          </button>
        </div>

        {activeTab === 'chat' ? (
          <div className="chat-section">
            <div className="chat-header">
              <div className="bot-avatar">
                <div className="avatar-circle">
                  <ZarkRobot size="medium" />
                </div>
                <div className="bot-info">
                  <h3 className="bot-name">Zark</h3>
                  <p className="bot-status">
                    {apiHealth?.status === 'healthy' ? (
                      <>
                        <span className="status-dot online"></span>
                        🟢 Online • {knowledgeCount} entries • Full AI Mode
                      </>
                    ) : detailedStatus?.status === 'limited' ? (
                      <>
                        <span className="status-dot limited"></span>
                        🟡 Limited Mode • {knowledgeCount} entries • No AI API
                      </>
                    ) : (
                      <>
                        <span className="status-dot offline"></span>
                        🔴 Offline • Connection Issues
                      </>
                    )}
                  </p>
                </div>
              </div>
              <div className="header-actions">
                <button onClick={getHelpInfo} className="help-button">
                  <span>❓</span>
                  Help
                </button>
                <button onClick={startNewConversation} className="new-chat-button">
                  <span>💬</span>
                  New Chat
                </button>
                <button onClick={clearChat} className="clear-button">
                  <span>🗑️</span>
                </button>
              </div>
            </div>
            
            <div className="messages-container">
              {messages.length === 0 ? (
                <div className="welcome-message">
                  <div className="welcome-avatar">
                    <div className="avatar-circle large">
                      <ZarkRobot size="large" />
                    </div>
                  </div>
                  <div className="welcome-content">
                    <h3>Hi, I'm Zark! 👋</h3>
                    <p>Your AI assistant. Ask me anything!</p>
                    <div className="example-questions">
                      <button className="example-btn" onClick={() => setInputMessage("What is quantum computing?")}>
                        🔬 Quantum computing
                      </button>
                      <button className="example-btn" onClick={() => setInputMessage("Explain machine learning")}>
                        🤖 Machine learning
                      </button>
                      <button className="example-btn" onClick={() => setInputMessage("Tell me about space exploration")}>
                        🚀 Space exploration
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                messages.map((message) => (
                  <div key={message.id} className={`message ${message.type}`}>
                    <div className="message-avatar">
                      {message.type === 'user' ? (
                        <div className="user-avatar">You</div>
                      ) : (
                        <div className="bot-avatar-small">Z</div>
                      )}
                    </div>
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
                      <div className="message-timestamp">{message.timestamp}</div>
                    </div>
                  </div>
                ))
              )}
              
              {isLoading && (
                <div className="message bot">
                  <div className="message-avatar">
                    <div className="bot-avatar-small">
                      <ZarkRobot size="small" />
                    </div>
                  </div>
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

            <div className="chat-input-container">
              <div className="chat-input">
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask Zark anything..."
                  disabled={isLoading}
                  rows={1}
                />
                <button 
                  onClick={handleSendMessage} 
                  disabled={isLoading || !inputMessage.trim()}
                  className="send-button"
                >
                  {isLoading ? <span className="loading-spinner"></span> : <span>🚀</span>}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="manage-section">
            <div className="manage-card">
              <div className="card-header">
                <h3>🌐 Add Content</h3>
                <p>Expand Zark's knowledge from web sources</p>
              </div>
              <div className="insert-form">
                <input
                  type="url"
                  value={insertUrl}
                  onChange={(e) => setInsertUrl(e.target.value)}
                  placeholder="Enter website URL..."
                  disabled={isInserting}
                  className="url-input"
                />
                <button 
                  onClick={handleInsertUrl} 
                  disabled={isInserting || !insertUrl.trim()}
                  className="insert-button"
                >
                  {isInserting ? (
                    <>
                      <span className="loading-spinner"></span>
                      Adding...
                    </>
                  ) : (
                    <>
                      <span>📥</span>
                      Add Content
                    </>
                  )}
                </button>
              </div>
              <div className="insert-tips">
                <p>💡 <strong>Tips:</strong></p>
                <ul>
                  <li>Use Wikipedia, news sites, or documentation</li>
                  <li>Content is analyzed and processed automatically</li>
                  <li>Processing may take a few moments</li>
                </ul>
              </div>
            </div>

            <div className="manage-card">
              <div className="card-header">
                <h3>📊 Knowledge Base</h3>
                <p>Manage your knowledge database</p>
              </div>
              <div className="knowledge-stats">
                <div className="stat-card">
                  <div className="stat-value">{knowledgeCount}</div>
                  <div className="stat-label">Total Entries</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{apiHealth?.status === 'healthy' ? '✅' : '❌'}</div>
                  <div className="stat-label">System Status</div>
                </div>
              </div>
              <div className="management-actions">
                <button onClick={getKnowledgeCount} className="action-button refresh">
                  <span>🔄</span>
                  Refresh
                </button>
                <button onClick={clearKnowledge} className="action-button danger">
                  <span>🗑️</span>
                  Clear All
                </button>
              </div>
            </div>
          </div>
        )}
        
        {showHelp && helpInfo && (
          <div className="help-modal-overlay" onClick={() => setShowHelp(false)}>
            <div className="help-modal" onClick={(e) => e.stopPropagation()}>
              <div className="help-header">
                <h2>🤖 How Zark-AI Works</h2>
                <button onClick={() => setShowHelp(false)} className="close-button">×</button>
              </div>
              <div className="help-content">
                <div className="status-section">
                  <h3>Current Status</h3>
                  <p className={`status-badge ${helpInfo.api_status}`}>
                    {helpInfo.api_status === 'configured' ? '🟢 Online Mode' : '🟡 Limited Mode'}
                  </p>
                  <p>Knowledge Entries: {helpInfo.knowledge_entries}</p>
                </div>
                
                <div className="capabilities-section">
                  <h3>Capabilities</h3>
                  {helpInfo.capabilities.online_mode.enabled ? (
                    <div className="capability-mode online">
                      <h4>🟢 Online Mode (Current)</h4>
                      <ul>
                        {helpInfo.capabilities.online_mode.features.map((feature, index) => (
                          <li key={index}>{feature}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="capability-mode limited">
                      <h4>🟡 Limited Mode (Current)</h4>
                      <ul>
                        {helpInfo.capabilities.offline_mode.features.map((feature, index) => (
                          <li key={index}>{feature}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                
                <div className="usage-section">
                  <h3>How to Use</h3>
                  <div className="usage-steps">
                    <div className="step">
                      <span className="step-number">1</span>
                      <p>{helpInfo.how_to_use.add_content}</p>
                    </div>
                    <div className="step">
                      <span className="step-number">2</span>
                      <p>{helpInfo.how_to_use.ask_questions}</p>
                    </div>
                  </div>
                  <div className="best-practices">
                    <h4>Best Practices:</h4>
                    <ul>
                      {helpInfo.how_to_use.best_practices.map((practice, index) => (
                        <li key={index}>{practice}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                
                {!helpInfo.capabilities.online_mode.enabled && (
                  <div className="setup-section">
                    <h3>Enable Full AI Mode</h3>
                    <ol>
                      {helpInfo.setup_instructions.for_online_mode.map((step, index) => (
                        <li key={index}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;