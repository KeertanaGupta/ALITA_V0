// frontend/src/pages/InsightEngine.jsx
import React, { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Send, Bot, User, Sparkles, Loader2, Folder, Plus, MessageSquare, Trash2, Menu, Paperclip, X, Image as ImageIcon } from 'lucide-react';
import { askAlita, fetchProjects } from '../api';
import ChatWithCitations from '../ChatWithCitations';

// Helper to generate UUID
function generateId() {
  return Math.random().toString(36).substring(2, 15);
}

export default function InsightEngine() {
  const [projects, setProjects] = useState([]);
  const location = useLocation();
  const navigate = useNavigate();
  
  // Chat Sessions state
  const [sessions, setSessions] = useState(() => {
    const saved = localStorage.getItem('alitaChatSessions');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Ensure updatedAt exists to sort them
        return parsed.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
      } catch (e) {
        return [];
      }
    }
    return [];
  });
  
  const [activeSessionId, setActiveSessionId] = useState(() => {
    return localStorage.getItem('alitaActiveSession') || null;
  });

  const [input, setInput] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [isThinking, setIsThinking] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Derived state
  const activeSession = sessions.find(s => s.id === activeSessionId) || null;
  const messages = activeSession ? activeSession.messages : [];
  const defaultProject = activeSession ? activeSession.projectId : 'all';
  const [selectedProjectId, setSelectedProjectId] = useState(defaultProject);

  useEffect(() => {
    fetchProjects().then(data => setProjects(data)).catch(console.error);
  }, []);

  useEffect(() => {
    if (location.state?.compareDocumentIds) {
      const docIds = location.state.compareDocumentIds;
      navigate('.', { replace: true, state: {} });
      initCompareSession(docIds);
    }
  }, [location.state, navigate]);

  const initCompareSession = async (docIds) => {
    const currentSessionId = generateId();
    const newSession = {
      id: currentSessionId,
      title: 'Compare Documents',
      projectId: 'all',
      messages: [{ role: 'user', text: 'Please compare the selected documents and summarize their key differences, similarities, and highlights.', sources: [] }],
      updatedAt: Date.now(),
      documentIds: docIds
    };
    
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(currentSessionId);
    setSelectedProjectId('all');
    setIsThinking(true);
    
    try {
      const aiResponse = await askAlita('Please compare the selected documents and summarize their key differences, similarities, and highlights.', 'all', docIds);
      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return {
            ...s,
            messages: [...s.messages, { role: 'assistant', text: aiResponse.answer, sources: aiResponse.sources || [] }],
            updatedAt: Date.now()
          };
        }
        return s;
      }));
    } catch (error) {
      setSessions(prev => prev.map(s => s.id === currentSessionId ? {
        ...s, messages: [...s.messages, { role: 'assistant', text: "Comparison failed due to a server error.", sources: [] }], updatedAt: Date.now()
      } : s));
    } finally {
      setIsThinking(false);
    }
  };

  // Sync to local storage whenever sessions change
  useEffect(() => {
    localStorage.setItem('alitaChatSessions', JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem('alitaActiveSession', activeSessionId);
    } else {
      localStorage.removeItem('alitaActiveSession');
    }
  }, [activeSessionId]);

  // Sync selected project ID when active session changes
  useEffect(() => {
    if (activeSession) {
      setSelectedProjectId(activeSession.projectId);
    } else {
      setSelectedProjectId('all');
    }
  }, [activeSessionId, activeSession]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => { scrollToBottom(); }, [messages, isThinking]);

  const createNewChat = () => {
    const newSession = {
      id: generateId(),
      title: 'New Chat',
      projectId: selectedProjectId,
      messages: [],
      updatedAt: Date.now()
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  };

  const deleteChat = (e, id) => {
    e.stopPropagation();
    const updated = sessions.filter(s => s.id !== id);
    setSessions(updated);
    if (activeSessionId === id) {
      setActiveSessionId(updated.length > 0 ? updated[0].id : null);
    }
  };

  const handleSend = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!input.trim() && !selectedImage) return;
    if (isThinking) return;

    let currentSessionId = activeSessionId;
    let isNewChatTitle = false;
    let newTitle = "New Chat";
    
    if (input.trim()) {
      newTitle = input.trim().substring(0, 30) + (input.trim().length > 30 ? "..." : "");
    } else if (selectedImage) {
      newTitle = "Image Analysis";
    }

    // If no active session, create one implicitly
    if (!currentSessionId) {
      currentSessionId = generateId();
      isNewChatTitle = true;
      const newSession = {
        id: currentSessionId,
        title: newTitle,
        projectId: selectedProjectId,
        messages: [],
        updatedAt: Date.now()
      };
      // Important to use synchronous callback for current tick
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(currentSessionId);
    } else if (messages.length === 0) {
      isNewChatTitle = true;
    }

    const userMsg = input.trim();
    const activeImageData = selectedImage;
    
    setInput('');
    setSelectedImage(null);
    setIsThinking(true);

    const userMessageObj = { role: 'user', text: userMsg, sources: [], image: activeImageData };

    setSessions(prev => prev.map(s => {
      if (s.id === currentSessionId) {
        return { 
          ...s, 
          title: isNewChatTitle ? newTitle : s.title,
          messages: [...s.messages, userMessageObj],
          updatedAt: Date.now()
        };
      }
      return s;
    }));

    try {
      const currentDocIds = activeSession?.documentIds || null;
      const aiResponse = await askAlita(userMsg, selectedProjectId, currentDocIds, activeImageData);
      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return {
            ...s,
            messages: [...s.messages, {
              role: 'assistant',
              text: aiResponse.answer,
              sources: aiResponse.sources || []
            }],
            updatedAt: Date.now()
          };
        }
        return s;
      }));
    } catch (error) {
      setSessions(prev => prev.map(s => {
        if (s.id === currentSessionId) {
          return {
            ...s,
            messages: [...s.messages, {
              role: 'assistant',
              text: "I'm sorry, my neural link to the vector database failed.",
              sources: []
            }],
            updatedAt: Date.now()
          };
        }
        return s;
      }));
    } finally {
      setIsThinking(false);
    }
  };

  const setInputAndSend = (text) => {
    setInput(text);
    // setTimeout to allow the state to update before handleSend uses `input`.
    // Wait, handleSend uses the `input` state, we must pass text directly or simulate.
    // Let's modify handleSend to accept a text override if needed, or just handle it here:
  };

  // We need a helper for those quick action buttons since handleSend relies on `input` state.
  const handleQuickAction = (text) => {
    setInput(text);
  };

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        alert("Please select a valid image file.");
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedImage(reader.result);
      };
      reader.readAsDataURL(file);
    }
    // reset input so same file can be selected again
    e.target.value = null;
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] animate-in fade-in duration-500 gap-6">
      
      {/* Sidebar for Chat History */}
      <div className={`flex flex-col bg-panel border border-panel-border rounded-2xl overflow-hidden transition-all duration-300 shadow-lg shrink-0 ${sidebarOpen ? 'w-64' : 'w-0 border-none opacity-0'}`}>
        <div className="p-4 border-b border-panel-border bg-background/50">
          <button 
            onClick={createNewChat}
            className="w-full flex items-center justify-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl py-2.5 px-4 font-bold text-sm transition-colors shadow-md"
          >
            <Plus size={18} />
            <span>New Chat</span>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
          {sessions.length === 0 ? (
            <div className="text-xs text-text-muted text-center mt-10">No chat history</div>
          ) : (
            sessions.map(session => (
              <button
                key={session.id}
                onClick={() => setActiveSessionId(session.id)}
                className={`w-full flex items-center justify-between text-left px-3 py-3 rounded-xl transition-all group ${
                  activeSessionId === session.id 
                    ? 'bg-primary/20 text-text-main border border-primary/30' 
                    : 'text-text-muted hover:bg-background border border-transparent'
                }`}
              >
                <div className="flex items-center space-x-3 overflow-hidden flex-1">
                  <MessageSquare size={16} className={`shrink-0 ${activeSessionId === session.id ? 'text-primary' : 'text-text-muted group-hover:text-text-main'}`} />
                  <span className="text-sm font-medium truncate flex-1">{session.title}</span>
                </div>
                <Trash2 
                  size={14} 
                  className={`shrink-0 ml-2 transition-opacity ${activeSessionId === session.id ? 'opacity-100 text-rose-500 hover:text-rose-400' : 'opacity-0 group-hover:opacity-100 hover:text-rose-500 text-text-muted'}`}
                  onClick={(e) => deleteChat(e, session.id)}
                />
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Header & Project Selector */}
        <div className="flex justify-between items-end mb-4 shrink-0 px-2">
          <div className="flex items-center space-x-4">
            <button 
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 bg-panel border border-panel-border rounded-lg text-text-muted hover:text-text-main hover:bg-background transition-colors"
              title="Toggle Sidebar"
            >
              <Menu size={20} />
            </button>
            <div>
              <h2 className="text-2xl font-bold mb-1 text-text-main flex items-center space-x-2">
                <Sparkles className="text-primary" size={24} />
                <span>Insight Engine</span>
              </h2>
              <p className="text-text-muted text-xs">Secure, offline document chatting</p>
            </div>
          </div>
          <div className="flex items-center space-x-3 bg-panel border border-panel-border px-4 py-2 rounded-xl">
            <Folder size={16} className="text-text-muted" />
            <select
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                // Update project ID for active session if any
                if (activeSessionId) {
                  setSessions(prev => prev.map(s => s.id === activeSessionId ? { ...s, projectId: e.target.value } : s));
                }
              }}
              className="bg-transparent text-sm font-medium text-text-main focus:outline-none cursor-pointer max-w-[200px] truncate"
            >
              <option value="all" className="bg-panel">Global Search (All Projects)</option>
              {projects.map(p => (
                <option key={p.id} value={p.id} className="bg-panel">{p.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Chat Window */}
        <div className="flex-1 bg-panel border border-panel-border rounded-2xl overflow-hidden flex flex-col shadow-lg">

          <div className="flex-1 overflow-y-auto p-6 space-y-6 flex flex-col">
            {(!activeSessionId || messages.length === 0) ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center max-w-lg mx-auto py-10 animate-in zoom-in-95 duration-500">
                <div className="h-20 w-20 bg-primary/10 rounded-full flex items-center justify-center mb-6 border border-primary/20 shadow-[0_0_30px_rgba(225,29,72,0.15)]">
                  <Sparkles size={40} className="text-primary" />
                </div>
                <h3 className="text-2xl font-bold text-text-main mb-2">How can I help you today?</h3>
                <p className="text-text-muted text-sm mb-8 px-4">Select a project above and ask a question to start a new conversation. Your chats are saved locally and persist when you switch tabs.</p>
                <div className="grid grid-cols-2 gap-4 w-full px-4">
                  <button onClick={() => setInput("What are the key insights in these documents?")} className="p-4 bg-background border border-panel-border rounded-xl text-left hover:border-primary/50 transition-colors group">
                    <p className="text-sm font-bold text-text-main mb-1 group-hover:text-primary transition-colors">Key Insights</p>
                    <p className="text-xs text-text-muted">Summarize the main points</p>
                  </button>
                  <button onClick={() => setInput("Can you extract the numerical data and metrics?")} className="p-4 bg-background border border-panel-border rounded-xl text-left hover:border-primary/50 transition-colors group">
                    <p className="text-sm font-bold text-text-main mb-1 group-hover:text-primary transition-colors">Extract Data</p>
                    <p className="text-xs text-text-muted">Find numbers and metrics</p>
                  </button>
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in`}>
                  <div className={`flex space-x-4 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>

                    {/* Avatar */}
                    <div className={`h-10 w-10 rounded-full flex items-center justify-center shrink-0 ${
                      msg.role === 'user'
                        ? 'bg-indigo-500/20 text-indigo-400'
                        : 'bg-primary/20 text-primary border border-primary/30'
                    }`}>
                      {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                    </div>

                    {/* Message bubble */}
                    <div className={`rounded-2xl text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white rounded-tr-none shadow-md p-4'
                        : 'bg-background border border-panel-border text-text-main rounded-tl-none p-4 shadow-sm'
                    }`}>
                      {msg.role === 'user' ? (
                        <div className="whitespace-pre-wrap flex flex-col">
                          {msg.image && (
                            <img src={msg.image} alt="User attachment" className="max-w-[150px] sm:max-w-[200px] rounded-lg mb-2 shadow-sm border border-white/20 object-contain" />
                          )}
                          {msg.text}
                        </div>
                      ) : (
                        <ChatWithCitations
                          answer={msg.text}
                          sources={msg.sources || []}
                        />
                      )}
                    </div>

                  </div>
                </div>
              ))
            )}

            {/* Thinking indicator */}
            {isThinking && (
              <div className="flex justify-start animate-in fade-in">
                <div className="flex space-x-4 max-w-[80%]">
                  <div className="h-10 w-10 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center shrink-0">
                    <Bot size={20} />
                  </div>
                  <div className="p-4 rounded-2xl bg-background border border-panel-border text-text-main rounded-tl-none flex items-center space-x-3 shadow-sm">
                    <div className="h-4 w-4 shrink-0 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
                    <span className="text-sm font-medium text-text-muted animate-pulse">ALITA is searching the knowledge base...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} className="h-px w-full" />
          </div>

          {/* Input area */}
          <div className="p-4 bg-background border-t border-panel-border">
            {selectedProjectId !== 'all' && (
              <div className="mb-2 flex items-center space-x-2 text-xs text-text-muted px-1">
                <Folder size={12} />
                <span>
                  Searching in: <span className="text-primary font-semibold">
                    {projects.find(p => p.id === selectedProjectId)?.name || selectedProjectId}
                  </span>
                </span>
              </div>
            )}
            
            {/* Image Preview Area */}
            {selectedImage && (
              <div className="mb-3 relative w-24 h-24 rounded-xl overflow-hidden border border-primary/30 group animate-in slide-in-from-bottom-2 shadow-md">
                <img src={selectedImage} alt="Attachment" className="w-full h-full object-cover" />
                <button 
                  onClick={() => setSelectedImage(null)}
                  className="absolute top-1 right-1 bg-black/50 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-rose-500"
                >
                  <X size={14} />
                </button>
              </div>
            )}

            <form onSubmit={handleSend} className="relative flex items-center">
              <input type="file" ref={fileInputRef} className="hidden" accept="image/png, image/jpeg, image/jpg, image/webp" onChange={handleImageSelect} />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className={`absolute left-3 z-10 w-9 h-9 rounded-lg flex items-center justify-center transition-all ${selectedImage ? 'text-primary bg-primary/10' : 'text-text-muted hover:text-text-main hover:bg-background/80'}`}
                title="Attach Image"
              >
                 <Paperclip size={18} />
              </button>
              
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  activeSession?.documentIds
                    ? "Ask follow-up questions about these documents..."
                    : selectedImage 
                      ? "Ask about this image..."
                      : selectedProjectId === 'all'
                        ? "Ask a question across all projects..."
                        : "Ask a question about this project's documents..."
                }
                className="w-full bg-panel border border-panel-border text-text-main rounded-xl py-4 pl-14 pr-16 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all shadow-inner"
                disabled={isThinking}
              />
              <button
                type="submit"
                disabled={(!input.trim() && !selectedImage) || isThinking}
                className="absolute right-2 bg-primary hover:bg-primary/90 disabled:bg-panel-border disabled:text-text-muted text-white h-10 w-10 rounded-lg flex items-center justify-center transition-all duration-200"
              >
                <Send size={18} className={(input.trim() || selectedImage) && !isThinking ? 'translate-x-0.5 -translate-y-0.5' : ''} />
              </button>
            </form>
          </div>

        </div>
      </div>
    </div>
  );
}