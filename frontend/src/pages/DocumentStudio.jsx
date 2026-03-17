import React, { useState, useRef, useEffect } from 'react';
import { 
  Sparkles, Languages, AlignLeft, Edit3, Search, FileOutput,
  Briefcase, Settings, BookOpen, FileText, FileSignature,
  UploadCloud, Terminal, Info, FileText as FileIcon, ChevronRight,
  CheckCircle, Loader2, X
} from 'lucide-react';
import { fetchProjects, uploadDocument } from '../api';

export default function DocumentStudio() {
  // --- STATE MANAGEMENT ---
  const [projects, setProjects] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  
  // Upload States
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState(null); // 'success' or 'error'

  const fileInputRef = useRef(null);

  // Load projects so the user can choose where to save the file
  useEffect(() => {
    fetchProjects().then(data => {
      setProjects(data);
      if (data.length > 0) setSelectedProjectId(data[0].id); // Default to first project
    }).catch(console.error);
  }, []);

  // --- DRAG AND DROP HANDLERS ---
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (file) => {
    // Basic validation (only accept PDFs for now)
    if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
      setSelectedFile(file);
      setUploadStatus(null);
      setUploadProgress(0);
    } else {
      alert("Please upload a valid PDF file.");
    }
  };

  // --- UPLOAD LOGIC ---
  const executeUpload = async () => {
    if (!selectedFile || !selectedProjectId) return;
    
    setIsUploading(true);
    setUploadStatus(null);

    try {
      await uploadDocument(selectedProjectId, selectedFile, (progress) => {
        setUploadProgress(progress);
      });
      setUploadStatus('success');
      setTimeout(() => {
        setSelectedFile(null); // Reset UI after 3 seconds
        setUploadStatus(null);
      }, 3000);
    } catch (error) {
      setUploadStatus('error');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="animate-in fade-in duration-500 pb-12">
      {/* Page Header */}
      <div className="flex justify-between items-start mb-8">
        <div>
          <h2 className="text-3xl font-bold mb-1 text-text-main">AI Document Studio</h2>
          <p className="text-text-muted text-sm">Generate, analyze, and transform documents with AI</p>
        </div>
        <button className="bg-primary hover:bg-primary/90 text-white p-2 rounded-lg transition-transform hover:scale-105 shadow-[0_0_15px_rgba(225,29,72,0.3)]">
          <Sparkles size={20} />
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN (Capabilities) - Same as before */}
        <div className="xl:col-span-2 space-y-10">
          <section>
            <h3 className="text-lg font-bold mb-4 text-text-main">AI Capabilities</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <CapabilityCard icon={<Sparkles size={20} className="text-blue-400" />} iconBg="bg-blue-500/10" title="AI Generation" desc="Create documents from prompts with intelligent structure" />
              <CapabilityCard icon={<Edit3 size={20} className="text-emerald-400" />} iconBg="bg-emerald-500/10" title="Smart Editing" desc="AI-powered content refinement and style adjustment" />
              <CapabilityCard icon={<Languages size={20} className="text-purple-400" />} iconBg="bg-purple-500/10" title="Translation" desc="Multi-language document translation with context preservation" />
              <CapabilityCard icon={<Search size={20} className="text-yellow-400" />} iconBg="bg-yellow-500/10" title="Analysis" desc="Deep content analysis and insight extraction" />
            </div>
          </section>

          <section>
            <h3 className="text-lg font-bold mb-4 text-text-main">Recent Documents</h3>
            <div className="space-y-3">
              <RecentDocCard name="Q1_Strategy_Analysis.pdf" meta="Business Document • 245 KB • 2 hours ago" />
              <RecentDocCard name="Technical_Architecture_v2.pdf" meta="Technical Report • 1.2 MB • 5 hours ago" />
            </div>
          </section>
        </div>

        {/* RIGHT COLUMN (Actions & Upload) */}
        <div className="space-y-6">
          <div className="bg-panel border border-panel-border rounded-xl p-6">
            <h3 className="text-sm font-bold text-text-muted uppercase tracking-wider mb-4">Quick Actions</h3>
            
            {/* --- DYNAMIC UPLOAD ZONE --- */}
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={(e) => handleFileSelect(e.target.files[0])} 
              className="hidden" 
              accept=".pdf" 
            />

            {!selectedFile ? (
              // State 1: Waiting for File
              <div 
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current.click()}
                className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer mb-4 transition-all duration-300 ${
                  isDragging ? 'border-primary bg-primary/5 scale-105' : 'border-panel-border hover:border-blue-500/50 hover:bg-blue-500/5'
                }`}
              >
                <div className="h-12 w-12 rounded-full bg-blue-500/10 flex items-center justify-center mb-3">
                  <UploadCloud size={24} className={isDragging ? 'text-primary' : 'text-blue-500'} />
                </div>
                <h4 className="text-sm font-bold text-text-main mb-1">Upload Document</h4>
                <p className="text-xs text-text-muted">Drag & drop PDF or click to browse</p>
              </div>
            ) : (
              // State 2: File Selected & Ready to Upload
              <div className="border border-panel-border bg-background rounded-xl p-5 mb-4 relative">
                {!isUploading && uploadStatus !== 'success' && (
                  <button onClick={() => setSelectedFile(null)} className="absolute top-2 right-2 p-1 text-text-muted hover:text-rose-500 transition-colors">
                    <X size={16} />
                  </button>
                )}
                
                <div className="flex items-center space-x-3 mb-4">
                  <FileIcon size={24} className="text-blue-500 shrink-0" />
                  <div className="overflow-hidden">
                    <p className="text-sm font-bold text-text-main truncate">{selectedFile.name}</p>
                    <p className="text-xs text-text-muted">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>

                {uploadStatus === 'success' ? (
                  <div className="flex items-center justify-center space-x-2 text-emerald-500 bg-emerald-500/10 py-2 rounded-lg text-sm font-bold">
                    <CheckCircle size={18} />
                    <span>Upload & AI Pipeline Started!</span>
                  </div>
                ) : isUploading ? (
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-text-muted">Uploading to Database...</span>
                      <span className="font-bold text-primary">{uploadProgress}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-panel-border rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full transition-all duration-300" style={{ width: `${uploadProgress}%` }}></div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <select 
                      value={selectedProjectId} 
                      onChange={(e) => setSelectedProjectId(e.target.value)}
                      className="w-full bg-panel border border-panel-border text-text-main text-sm rounded-lg p-2 focus:outline-none focus:border-primary/50"
                    >
                      {projects.map(p => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                    <button 
                      onClick={executeUpload}
                      className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded-lg text-sm font-bold transition-colors"
                    >
                      Start Upload
                    </button>
                  </div>
                )}
              </div>
            )}

            <button className="w-full bg-background border border-panel-border hover:bg-panel-border text-text-main py-3 rounded-xl font-medium transition-colors flex items-center justify-center space-x-2 text-sm">
              <Terminal size={16} />
              <span>Generate from Prompt</span>
            </button>
          </div>

          <div className="bg-gradient-to-br from-amber-500/10 to-orange-600/10 border border-amber-500/20 rounded-xl p-6">
            <div className="flex items-center space-x-2 mb-2">
              <Info size={18} className="text-amber-500" />
              <h3 className="text-sm font-bold text-amber-500">System Link</h3>
            </div>
            <p className="text-sm text-text-muted leading-relaxed">
              Uploading a document here automatically triggers Django to save it, and signals FastAPI to extract, chunk, and embed it using Local LLMs.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- SUB-COMPONENTS ---
function CapabilityCard({ icon, iconBg, title, desc }) {
  return (
    <div className="bg-panel border border-panel-border hover:border-text-muted/40 rounded-xl p-5 transition-all duration-300 cursor-pointer shadow-sm">
      <div className="flex items-start space-x-4">
        <div className={`h-10 w-10 shrink-0 rounded-lg ${iconBg} flex items-center justify-center`}>{icon}</div>
        <div>
          <h4 className="text-sm font-bold text-text-main mb-1">{title}</h4>
          <p className="text-xs text-text-muted leading-relaxed">{desc}</p>
        </div>
      </div>
    </div>
  );
}

function RecentDocCard({ name, meta }) {
  return (
    <div className="bg-panel border border-panel-border hover:border-text-muted/40 rounded-xl p-4 flex items-center justify-between transition-all duration-300 cursor-pointer group">
      <div className="flex items-center space-x-4">
        <div className="h-10 w-10 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
          <FileIcon size={20} className="text-blue-500" />
        </div>
        <div>
          <h4 className="text-sm font-bold text-text-main mb-0.5">{name}</h4>
          <p className="text-xs text-text-muted">{meta}</p>
        </div>
      </div>
      <ChevronRight size={16} className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );
}