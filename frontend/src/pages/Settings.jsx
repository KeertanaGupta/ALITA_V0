import React, { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, Cpu, Shield, HardDrive, 
  Bell, User, CheckCircle, Loader2 
} from 'lucide-react';
import { fetchSystemStats, switchActiveModel } from '../api';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('models');
  const [currentModel, setCurrentModel] = useState('Loading...');
  const [isSwitching, setIsSwitching] = useState(false);

  // Available models matching your video
  const availableModels = [
    { id: 'llama3.1', name: 'Llama-3.1-70B', params: '70B', context: '8K tokens' },
    { id: 'mistral', name: 'Mistral-7B-Instruct', params: '7B', context: '8K tokens' },
    { id: 'phi3', name: 'Phi-3-Mini', params: '3.8B', context: '128K tokens' }
  ];

  // Fetch the current model from FastAPI on load
  useEffect(() => {
    fetchSystemStats().then(data => {
      setCurrentModel(data.active_model);
    }).catch(console.error);
  }, []);

  const handleModelSwitch = async (modelId) => {
    if (currentModel === modelId) return;
    
    setIsSwitching(modelId);
    try {
      const response = await switchActiveModel(modelId);
      setCurrentModel(response.active_model);
    } catch (error) {
      alert("Failed to switch AI model. Is the AI Engine running?");
    } finally {
      setIsSwitching(false);
    }
  };

  return (
    <div className="animate-in fade-in duration-500 pb-12 h-full flex flex-col">
      {/* Page Header */}
      <div className="mb-8 shrink-0">
        <h2 className="text-3xl font-bold mb-1 text-text-main">Settings</h2>
        <p className="text-text-muted text-sm">Configure your AI Operating System preferences</p>
      </div>

      <div className="flex flex-1 overflow-hidden space-x-8">
        
        {/* Settings Sidebar */}
        <div className="w-64 shrink-0 space-y-1">
          <SettingsTab icon={<SettingsIcon size={18} />} label="System Configuration" active={activeTab === 'system'} onClick={() => setActiveTab('system')} />
          <SettingsTab icon={<Cpu size={18} />} label="AI Models" active={activeTab === 'models'} onClick={() => setActiveTab('models')} />
          <SettingsTab icon={<Shield size={18} />} label="Security & Privacy" active={activeTab === 'security'} onClick={() => setActiveTab('security')} />
          <SettingsTab icon={<HardDrive size={18} />} label="Storage & Data" active={activeTab === 'storage'} onClick={() => setActiveTab('storage')} />
          <SettingsTab icon={<Bell size={18} />} label="Notifications" active={activeTab === 'notifications'} onClick={() => setActiveTab('notifications')} />
          <SettingsTab icon={<User size={18} />} label="Account" active={activeTab === 'account'} onClick={() => setActiveTab('account')} />
        </div>

        {/* Settings Content Area */}
        <div className="flex-1 bg-panel border border-panel-border rounded-xl p-8 overflow-y-auto shadow-sm">
          
          {activeTab === 'models' && (
            <div className="animate-in fade-in duration-300">
              <h3 className="text-xl font-bold text-text-main mb-6">AI Models Configuration</h3>
              
              {/* Active Model Card */}
              <div className="bg-background border border-panel-border rounded-xl p-6 mb-8 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-primary"></div>
                <h4 className="text-sm font-bold text-text-main mb-1">Active Language Model</h4>
                <p className="text-sm text-text-muted mb-4">Currently running: <span className="font-semibold text-primary">{currentModel}</span></p>
                
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-text-muted mb-1">Status</p>
                    <div className="flex items-center space-x-1.5 text-emerald-500 font-medium text-sm">
                      <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></div>
                      <span>Running</span>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-text-muted mb-1">Connection</p>
                    <p className="text-sm font-medium text-text-main">Local (Ollama)</p>
                  </div>
                </div>
              </div>

              {/* Available Models List */}
              <h4 className="text-base font-bold text-text-main mb-4">Available Models</h4>
              <div className="space-y-3">
                {availableModels.map((model) => (
                  <div 
                    key={model.id}
                    onClick={() => handleModelSwitch(model.id)}
                    className={`flex items-center justify-between p-4 rounded-xl border transition-all duration-300 cursor-pointer ${
                      currentModel === model.id 
                        ? 'bg-primary/5 border-primary shadow-[0_0_10px_rgba(225,29,72,0.1)]' 
                        : 'bg-background border-panel-border hover:border-text-muted/50'
                    }`}
                  >
                    <div>
                      <h5 className="font-bold text-text-main">{model.name}</h5>
                      <p className="text-xs text-text-muted mt-0.5">{model.params} parameters • {model.context}</p>
                    </div>
                    
                    <div className="shrink-0">
                      {isSwitching === model.id ? (
                        <Loader2 className="animate-spin text-primary" size={20} />
                      ) : currentModel === model.id ? (
                        <div className="flex items-center space-x-1.5 text-primary text-sm font-bold bg-primary/10 px-3 py-1.5 rounded-lg">
                          <CheckCircle size={16} />
                          <span>Active</span>
                        </div>
                      ) : (
                        <button className="text-sm font-medium text-text-muted hover:text-text-main px-4 py-2 border border-panel-border rounded-lg bg-panel transition-colors">
                          Switch to Model
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab !== 'models' && (
            <div className="h-full flex flex-col items-center justify-center text-center opacity-50">
              <SettingsIcon size={48} className="text-text-muted mb-4" />
              <h3 className="text-xl font-bold text-text-main mb-2">Coming Soon</h3>
              <p className="text-text-muted">This configuration panel is currently under development.</p>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

function SettingsTab({ icon, label, active, onClick }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
        active 
          ? 'bg-primary/10 text-primary' 
          : 'text-text-muted hover:bg-panel hover:text-text-main'
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}