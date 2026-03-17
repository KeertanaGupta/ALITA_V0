import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Loader2, Database, Folder } from 'lucide-react';
import { askAlita, fetchProjects } from '../api';

export default function InsightEngine() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: "Hello! I am ALITA. Select a project from the dropdown above, and ask me anything about its documents." }
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  
  // New States for Dynamic Projects
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState('all');
  
  const messagesEndRef = useRef(null);

  // Load Projects on mount
  useEffect(() => {
    fetchProjects().then(data => {
      setProjects(data);
    }).catch(console.error);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => { scrollToBottom(); }, [messages, isThinking]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isThinking) return;

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setIsThinking(true);

    try {
      // Note: In the next step, we will pass selectedProjectId to FastAPI!
      const aiResponse = await askAlita(userMsg, selectedProjectId);
      
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: aiResponse.answer,
        sources: aiResponse.sources 
      }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: "I'm sorry, my neural link to the vector database failed." 
      }]);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] animate-in fade-in duration-500">
      {/* Header & Project Selector */}
      <div className="flex justify-between items-end mb-6 shrink-0">
        <div>
          <h2 className="text-3xl font-bold mb-1 text-text-main flex items-center space-x-3">
            <Sparkles className="text-primary" size={28} />
            <span>Insight Engine</span>
          </h2>
          <p className="text-text-muted text-sm">Secure, offline document chatting powered by Mistral</p>
        </div>
        
        {/* DYNAMIC PROJECT SELECTOR */}
        <div className="flex items-center space-x-3 bg-panel border border-panel-border px-4 py-2 rounded-xl">
          <Folder size={16} className="text-text-muted" />
          <select 
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="bg-transparent text-sm font-medium text-text-main focus:outline-none cursor-pointer"
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
        
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`flex space-x-4 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
                <div className={`h-10 w-10 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-primary/20 text-primary border border-primary/30'}`}>
                  {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                </div>
                <div className={`p-4 rounded-2xl text-sm leading-relaxed ${msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-none shadow-md' : 'bg-background border border-panel-border text-text-main rounded-tl-none'}`}>
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-panel-border/50">
                      <p className="text-xs text-text-muted flex items-center mb-2">
                        <Database size={12} className="mr-1" /> Retrieved from {msg.sources.length} document chunks
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          
          {isThinking && (
            <div className="flex justify-start">
              <div className="flex space-x-4 max-w-[80%]">
                <div className="h-10 w-10 rounded-full bg-primary/20 text-primary border border-primary/30 flex items-center justify-center shrink-0">
                  <Bot size={20} />
                </div>
                <div className="p-4 rounded-2xl bg-background border border-panel-border text-text-main rounded-tl-none flex items-center space-x-2">
                  <Loader2 size={16} className="animate-spin text-primary" />
                  <span className="text-sm text-text-muted animate-pulse">ALITA is searching...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Dynamic Input Area */}
        <div className="p-4 bg-background border-t border-panel-border">
          <form onSubmit={handleSend} className="relative flex items-center">
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={selectedProjectId === 'all' ? "Ask a question across all projects..." : "Ask a question about this specific project..."} 
              className="w-full bg-panel border border-panel-border text-text-main rounded-xl py-4 pl-6 pr-16 focus:outline-none focus:border-primary/50 transition-colors shadow-inner"
              disabled={isThinking}
            />
            <button type="submit" disabled={!input.trim() || isThinking} className="absolute right-2 bg-primary hover:bg-primary/90 disabled:bg-panel-border disabled:text-text-muted text-white h-10 w-10 rounded-lg flex items-center justify-center transition-all duration-200">
              <Send size={18} className={input.trim() && !isThinking ? 'translate-x-0.5 -translate-y-0.5' : ''} />
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}