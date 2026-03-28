import { fetchProjects, fetchDocuments, fetchSystemStats, deleteProject, updateProject, uploadDocument, processDocumentFastAPI, updateDocumentStatus } from './api';
import { Loader2 } from 'lucide-react';
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, FolderOpen, Database, FileText, Activity, Code, Settings as SettingsIcon, Terminal, Moon, Sun, User, 
  Cpu, HardDrive, ShieldCheck, Zap, Server, ChevronRight, X, FilePlus, PlaySquare, MoreVertical, Edit2, Info, Download, Copy, Trash2, Share2, Archive, UploadCloud, CheckCircle2
} from 'lucide-react';
import Projects from './pages/Projects';
import DocumentStudio from './pages/DocumentStudio';
import InsightEngine from './pages/InsightEngine';
import KnowledgeBase from './pages/KnowledgeBase';
import Settings from './pages/Settings';

export default function App() {
  const [isDark, setIsDark] = useState(true);
  useEffect(() => {
    if (isDark) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  }, [isDark]);

  return (
    <Router>
      <div className="flex h-screen w-full bg-background text-text-main transition-colors duration-300">
        <Sidebar />
        <main className="flex-1 flex flex-col h-full relative overflow-hidden">
          <Topbar isDark={isDark} toggleTheme={() => setIsDark(!isDark)} />
          <div className="flex-1 overflow-y-auto p-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/studio" element={<DocumentStudio/>}/>
              <Route path="/insight" element={<InsightEngine/>}/>
              <Route path="/knowledge" element={<KnowledgeBase />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}

function Topbar({ isDark, toggleTheme }) {
  const location = useLocation();
  const title = location.pathname === '/projects' ? 'Project Workspace' : 'Control Center';
  return (
    <header className="h-16 border-b border-panel-border flex items-center justify-between px-8 bg-background/80 backdrop-blur-md z-10 shrink-0 transition-colors duration-300">
      <h1 className="text-lg font-semibold text-text-main">{title}</h1>
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full border bg-emerald-500/10 border-emerald-500/20 text-emerald-500 text-xs font-semibold tracking-wide">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></div><span>LLM Active</span>
        </div>
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full border bg-panel border-panel-border text-text-muted text-xs font-semibold"><HardDrive size={14} /><span>2.4GB</span></div>
        <div className="h-5 w-px bg-panel-border mx-1"></div>
        <button onClick={toggleTheme} className="h-9 w-9 rounded-full bg-panel border border-panel-border flex items-center justify-center text-text-muted hover:text-text-main transition-colors">{isDark ? <Sun size={16} /> : <Moon size={16} />}</button>
        <button className="h-9 w-9 rounded-full bg-primary/20 border border-primary/50 text-primary flex items-center justify-center hover:scale-105 transition-transform"><User size={16} /></button>
      </div>
    </header>
  );
}

function Sidebar() {
  const location = useLocation();
  return (
    <aside className="w-64 border-r border-panel-border bg-background flex flex-col z-20 transition-colors duration-300">
      <div className="h-16 flex items-center px-6 border-b border-panel-border"><div className="h-7 w-7 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center mr-3 shadow-[0_0_10px_rgba(225,29,72,0.4)]"></div><span className="text-lg font-bold tracking-wider">ALITA</span></div>
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        <SidebarItem to="/" icon={<LayoutDashboard size={18} />} label="Dashboard" active={location.pathname === '/'} />
        <SidebarItem to="/projects" icon={<FolderOpen size={18} />} label="Projects" active={location.pathname === '/projects'} />
        <SidebarItem to="/knowledge" icon={<Database size={18} />} label="Knowledge Base" active={location.pathname === '/knowledge'} />
        <SidebarItem to="/studio" icon={<FileText size={18} />} label="AI Document Studio" active={location.pathname === '/studio'} />
        <SidebarItem to="/insight" icon={<Activity size={18} />} label="Insight Engine" active={location.pathname === '/insight'} />
        <div className="pt-6 pb-2"><p className="text-[10px] font-bold text-text-muted uppercase tracking-widest px-3">Developer Tools</p></div>
        <SidebarItem to="#" icon={<Code size={18} />} label="Code Intelligence" />
        <SidebarItem to="#" icon={<Terminal size={18} />} label="API Workspace" />
        <SidebarItem to="/settings" icon={<SettingsIcon size={18} />} label="Settings" active={location.pathname === '/settings'} />
      </nav>
    </aside>
  );
}

function SidebarItem({ icon, label, to, active }) {
  return (
    <Link to={to} className={`flex items-center space-x-3 px-3 py-2.5 rounded-md transition-all duration-200 group ${active ? 'bg-panel border border-panel-border' : 'border border-transparent hover:bg-panel/50'}`}>
      <span className={active ? 'text-primary' : 'text-text-muted group-hover:text-text-main transition-colors'}>{icon}</span><span className={`text-sm font-medium ${active ? 'text-text-main' : 'text-text-muted group-hover:text-text-main'}`}>{label}</span>
    </Link>
  );
}

// --- MAIN DASHBOARD VIEW ---

function Dashboard() {
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({ totalDocs: 0, activeModel: "Loading...", embedModel: "Loading...", vectorSize: "0 MB" });
  const [recentProjects, setRecentProjects] = useState([]);
  const navigate = useNavigate();

  const [selectedProject, setSelectedProject] = useState(null); 
  const [projectToRename, setProjectToRename] = useState(null); 
  const [renameValue, setRenameValue] = useState('');
  const [projectForUpload, setProjectForUpload] = useState(null); 
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [autoProcess, setAutoProcess] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [docsData, projectsData, aiStats] = await Promise.all([fetchDocuments(), fetchProjects(), fetchSystemStats()]);
      setStats({ totalDocs: docsData.length, activeModel: aiStats.active_model, embedModel: aiStats.embedding_model, vectorSize: `${aiStats.vector_store_size_mb} MB` });
      
      const formattedProjects = projectsData.slice(0, 4).map(p => {
        const docCount = p.documents ? p.documents.length : 0;
        const completedDocs = p.documents ? p.documents.filter(d => d.processing_status === 'COMPLETED').length : 0;
        const progress = docCount > 0 ? Math.round((completedDocs / docCount) * 100) : 0;
        return { 
          id: p.id, name: p.name, docs: docCount, rawDocuments: p.documents || [],
          docNames: p.documents ? p.documents.map(d => d.filename) : [], 
          desc: p.description || "Intelligent knowledge workspace", 
          lastActive: new Date(p.updated_at).toLocaleDateString(), progress: progress,
          status: progress === 100 && docCount > 0 ? "Completed" : "Active",
          progColor: progress === 100 && docCount > 0 ? "bg-purple-500" : "bg-emerald-500" 
        };
      });
      setRecentProjects(formattedProjects);
    } catch (error) { console.error("Failed to load data"); } 
    finally { setIsLoading(false); }
  };

  useEffect(() => { loadDashboardData(); }, []);

  const handleDashboardAction = async (action, project) => {
    if (action === 'Delete Project') {
      if (window.confirm(`Are you absolutely sure you want to delete "${project.name}"?`)) {
        try { await deleteProject(project.id); loadDashboardData(); } catch (e) { alert("Failed to delete project."); }
      }
    } 
    else if (action === 'Rename Project') { setRenameValue(project.name); setProjectToRename(project); } 
    else if (action === 'Open Workspace') { navigate('/insight'); } 
    else if (action === 'View Details') { setSelectedProject(project); } 
    else if (action === 'Add Documents') { setProjectForUpload(project); setSelectedFiles([]); setAutoProcess(true); } 
    else if (action === 'Process Pending Files') {
      const pendingDocs = project.rawDocuments.filter(d => d.processing_status !== 'COMPLETED');
      if (pendingDocs.length === 0) return alert("All documents are processed!");
      setIsProcessing(true);
      try {
        for (const doc of pendingDocs) {
          let aiSuccess = false;
          try {
            await processDocumentFastAPI(doc.id, project.id, doc.file);
            aiSuccess = true;
          } catch (e) { await updateDocumentStatus(doc.id, 'FAILED'); }
          
          if (aiSuccess) {
            try { await updateDocumentStatus(doc.id, 'COMPLETED'); } catch (e) {}
          }
        }
        loadDashboardData();
      } catch (err) {} finally { setIsProcessing(false); }
    }
  };

  const handleDrag = (e) => { 
    e.preventDefault(); e.stopPropagation(); 
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true); 
    else if (e.type === "dragleave") setDragActive(false); 
  };
  const handleDrop = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); if (e.dataTransfer.files) setSelectedFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]); };
  const handleChange = (e) => { e.preventDefault(); if (e.target.files) setSelectedFiles(prev => [...prev, ...Array.from(e.target.files)]); };
  const removeFile = (index) => { setSelectedFiles(prev => prev.filter((_, i) => i !== index)); };

  const submitUpload = async (e) => {
    e.preventDefault();
    setIsProcessing(true);
    let hasUploadErrors = false;

    try {
      for (const file of selectedFiles) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
          console.warn(`Skipped "${file.name}". Only PDF allowed.`);
          continue; 
        }
        
        let docData;
        
        // --- PHASE 1: UPLOAD ---
        try {
          docData = await uploadDocument(projectForUpload.id, file);
        } catch (uploadError) {
          console.error("Django Upload Error:", uploadError);
          hasUploadErrors = true;
          continue; 
        }
        
        // --- PHASE 2: AI PROCESSING & INDEXING ---
        if (autoProcess && docData) {
          try {
            await processDocumentFastAPI(docData.id, projectForUpload.id, docData.file);
            
            // --- PHASE 3: UPDATE BADGE TO COMPLETED ---
            try {
              await updateDocumentStatus(docData.id, 'COMPLETED');
            } catch (statusError) {
              console.warn("AI succeeded, but Django failed to update the UI badge to COMPLETED.");
            }

          } catch (aiError) { 
            console.error("FastAPI Processing Error:", aiError);
            try {
              await updateDocumentStatus(docData.id, 'FAILED'); 
            } catch (statusError) {
              console.warn("Failed to update UI badge to FAILED.");
            }
          }
        }
      }

      if (hasUploadErrors) {
        alert("Some files could not be uploaded to the database. Check the console.");
      }

      setProjectForUpload(null); 
      setSelectedFiles([]); 
      loadDashboardData(); 

    } catch (criticalError) { 
      console.error("Critical Upload Pipeline Error:", criticalError);
    } finally { 
      setIsProcessing(false); 
    }
  };

  const submitRename = async (e) => {
    e.preventDefault(); if (!renameValue.trim()) return;
    setIsProcessing(true);
    try { await updateProject(projectToRename.id, { name: renameValue }); setProjectToRename(null); loadDashboardData(); } 
    catch (error) { alert("Failed to rename."); } finally { setIsProcessing(false); }
  };

  const capabilities = [
    { title: "AI Document Studio", desc: "Generate, analyze, and transform documents with AI", icon: <FileText size={20} className="text-rose-500"/>, iconBg: "bg-rose-500/10", path: "/studio" },
    { title: "Smart Context Memory", desc: "Persistent conversation context across sessions", icon: <Cpu size={20} className="text-purple-500"/>, iconBg: "bg-purple-500/10", path: "/insight" },
    { title: "Insight Engine", desc: "Extract key insights and generate summaries", icon: <Activity size={20} className="text-emerald-500"/>, iconBg: "bg-emerald-500/10", path: "/insight" }
  ];

  if (isLoading) return (<div className="h-full flex flex-col items-center justify-center"><Loader2 className="animate-spin text-primary mb-4" size={40} /><p className="text-text-muted">Initializing Neural Systems...</p></div>);

  return (
    <div className="animate-in fade-in duration-500 pb-12 min-h-full">
      <h2 className="text-xl font-bold mb-4 text-text-main">System Intelligence</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        <MetricCard icon={<FileText size={18} className="text-rose-500" />} iconBg="bg-rose-500/10" title="Documents Indexed" value={stats.totalDocs} subtext="Across all projects" />
        <MetricCard icon={<Server size={18} className="text-purple-500" />} iconBg="bg-purple-500/10" title="Active Model" value={stats.activeModel} subtext="Local deployment" />
        <MetricCard icon={<Cpu size={18} className="text-emerald-500" />} iconBg="bg-emerald-500/10" title="Embedding Model" value={stats.embedModel} subtext="Offline Vectorization" />
        <MetricCard icon={<HardDrive size={18} className="text-blue-500" />} iconBg="bg-blue-500/10" title="Vector Store Size" value={stats.vectorSize} subtext="FAISS Database" />
      </div>

      <h2 className="text-xl font-bold mb-4 text-text-main">Active Projects</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10 relative">
        {recentProjects.length > 0 ? (
          recentProjects.map((proj) => (<DetailedProjectCard key={proj.id} project={proj} onAction={handleDashboardAction} />))
        ) : (<div className="col-span-2 bg-panel border border-dashed border-panel-border rounded-xl p-8 text-center"><p className="text-text-muted">No active projects found. Head to the Project Workspace to create one.</p></div>)}
      </div>

      <h2 className="text-xl font-bold mb-4 text-text-main">AI Capability Modules</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {capabilities.map((cap, idx) => (<CapabilityCard key={idx} cap={cap} onClick={() => navigate(cap.path)} />))}
      </div>

      {/* DRILL DOWN MODAL */}
      {selectedProject && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-panel border border-panel-border rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col animate-in zoom-in-95">
            <div className="flex justify-between items-center p-6 border-b border-panel-border bg-background/50">
              <div className="flex items-center space-x-3 mb-1"><div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20"><FolderOpen className="text-primary" size={20} /></div><h2 className="text-2xl font-bold text-text-main">{selectedProject.name}</h2></div>
              <button onClick={() => setSelectedProject(null)} className="text-text-muted hover:text-rose-500 hover:bg-rose-500/10 rounded-lg p-2 transition-colors"><X size={24} /></button>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="md:col-span-2 space-y-3">
                <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider flex items-center space-x-2">📄 <span>Indexed Documents</span></h3>
                <div className="bg-background border border-panel-border rounded-xl p-4 h-64 overflow-y-auto custom-scrollbar shadow-inner">
                  {selectedProject.docNames && selectedProject.docNames.length > 0 ? (
                    <ul className="space-y-2">{selectedProject.docNames.map((name, idx) => (<li key={idx} className="flex items-center space-x-3 text-sm text-text-main p-3 bg-panel rounded-lg border border-panel-border"><FileText size={18} className="text-blue-500 shrink-0 "/><span className="truncate">{name}</span></li>))}</ul>
                  ) : (<div className="h-full flex flex-col items-center justify-center text-text-muted"><FileText size={40} className="mb-3 opacity-50" /><p className="text-sm font-medium">No documents found</p></div>)}
                </div>
              </div>
              <div className="space-y-8">
                <div>
                  <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3 flex items-center space-x-2">📊 <span>Project Stats</span></h3>
                  <div className="space-y-3">
                    <div className="bg-background p-3 rounded-xl border border-panel-border flex justify-between items-center"><span className="text-xs text-text-muted">Total Docs</span><span className="font-bold">{selectedProject.docs}</span></div>
                    <div className="bg-background p-3 rounded-xl border border-panel-border flex justify-between items-center"><span className="text-xs text-text-muted">Total Size</span><span className="font-bold">{selectedProject.docs > 0 ? (selectedProject.docs * 1.2).toFixed(1) + " MB" : "0 MB"}</span></div>
                  </div>
                </div>
                <div>
                  <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3 flex items-center space-x-2">⚡ <span>Quick Actions</span></h3>
                  <div className="space-y-2">
                    <button onClick={() => navigate('/insight')} className="w-full flex items-center space-x-3 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 py-2.5 px-4 rounded-xl text-sm font-bold transition-all hover:bg-indigo-500/20"><FolderOpen size={16} /><span>Open Workspace</span></button>
                    <button onClick={() => { handleDashboardAction('Add Documents', selectedProject); setSelectedProject(null); }} className="w-full flex items-center space-x-3 bg-panel border border-panel-border py-2.5 px-4 rounded-xl text-sm font-medium transition-colors hover:bg-panel-border"><FilePlus size={16} /><span>Add Document</span></button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* DASHBOARD UPLOAD MODAL */}
      {projectForUpload && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-panel border border-panel-border rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center p-6 border-b border-panel-border bg-background/50">
              <h3 className="text-lg font-bold text-text-main flex items-center space-x-2"><FilePlus className="text-indigo-400" size={20} /><span>Upload to {projectForUpload.name}</span></h3>
              <button onClick={() => setProjectForUpload(null)} className="text-text-muted hover:text-rose-500 hover:bg-rose-500/10 rounded-lg p-2"><X size={20} /></button>
            </div>
            <form onSubmit={submitUpload} className="p-6 space-y-4">
              <div className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors ${dragActive ? 'border-indigo-500 bg-indigo-500/10' : 'border-panel-border bg-background hover:bg-panel'}`} onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}>
                  <input type="file" multiple accept="application/pdf" onChange={handleChange} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" disabled={isProcessing} />
                  <UploadCloud size={32} className={`mx-auto mb-3 ${dragActive ? 'text-indigo-500' : 'text-text-muted'}`} />
                  <p className="text-sm font-medium text-text-main mb-1">Drag & drop PDF files here</p>
              </div>
              {selectedFiles.length > 0 && (
                  <div className="max-h-32 overflow-y-auto space-y-2 custom-scrollbar border border-panel-border p-2 rounded-lg bg-background">
                    {selectedFiles.map((file, idx) => (<div key={idx} className="flex justify-between items-center px-2 py-1 text-sm"><span className="truncate text-text-main">{file.name}</span><button type="button" onClick={() => removeFile(idx)} className="text-text-muted hover:text-rose-500"><X size={16} /></button></div>))}
                  </div>
              )}
              <div className="bg-indigo-500/10 border border-indigo-500/20 p-4 rounded-xl flex items-start space-x-3 cursor-pointer" onClick={() => !isProcessing && setAutoProcess(!autoProcess)}>
                <div className={`mt-0.5 shrink-0 h-4 w-4 rounded border flex items-center justify-center transition-colors ${autoProcess ? 'bg-indigo-500 border-indigo-500' : 'border-text-muted'}`}>{autoProcess && <CheckCircle2 size={12} className="text-white" />}</div>
                <div><p className="text-sm font-bold text-text-main leading-none mb-1">Process & Index Automatically</p><p className="text-xs text-text-muted">Extract data and generate embeddings.</p></div>
              </div>
              <div className="pt-2 flex items-center justify-end space-x-3">
                <button type="button" onClick={() => setProjectForUpload(null)} className="px-5 py-2 text-sm font-medium text-text-muted hover:text-text-main" disabled={isProcessing}>Cancel</button>
                <button type="submit" disabled={selectedFiles.length === 0 || isProcessing} className="px-5 py-2 rounded-xl text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-panel-border transition-all flex items-center space-x-2">
                  {isProcessing ? <><Loader2 size={16} className="animate-spin inline" /><span>Processing...</span></> : <span>{autoProcess ? "Upload & Process" : "Upload Only"}</span>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DASHBOARD RENAME MODAL */}
      {projectToRename && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-panel border border-panel-border rounded-2xl p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-lg font-bold text-text-main mb-4">Rename Project</h3>
            <form onSubmit={submitRename}>
              <input type="text" autoFocus required value={renameValue} onChange={(e) => setRenameValue(e.target.value)} className="w-full bg-background border border-panel-border text-text-main rounded-xl px-4 py-3 mb-4 focus:outline-none focus:border-indigo-500" disabled={isProcessing} />
              <div className="flex justify-end space-x-3"><button type="button" onClick={() => setProjectToRename(null)} className="px-4 py-2 text-sm text-text-muted">Cancel</button><button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold disabled:bg-panel-border">Save</button></div>
            </form>
          </div>
        </div>
      )}

      {/* PROCESSING OVERLAY */}
      {isProcessing && !projectForUpload && !projectToRename && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in"><div className="bg-panel border border-panel-border p-6 rounded-xl flex flex-col items-center"><Loader2 size={40} className="animate-spin text-indigo-500 mb-4" /><p className="text-text-main font-bold">Processing Documents...</p></div></div>
      )}
    </div>
  );
}

function MetricCard({ icon, iconBg, title, value, subtext }) {
  return (
    <div className="bg-panel border border-panel-border rounded-xl p-5 shadow-sm">
      <div className={`h-10 w-10 rounded-lg ${iconBg} flex items-center justify-center mb-4`}>{icon}</div>
      <p className="text-xs font-medium text-text-muted mb-1">{title}</p><h4 className="text-2xl font-bold text-text-main mb-1">{value}</h4><p className="text-xs text-text-muted">{subtext}</p>
    </div>
  );
}

function MenuItem({ icon, label, danger, onClick }) {
  return (
    <button onClick={onClick} className={`w-full flex items-center space-x-3 px-4 py-1.5 text-sm font-medium transition-colors hover:bg-background ${danger ? 'text-rose-500 hover:text-rose-400' : 'text-text-main'}`}>
      {icon}<span>{label}</span>
    </button>
  );
}

function DetailedProjectCard({ project, onAction }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const handleActionClick = (e, action) => { e.stopPropagation(); setIsMenuOpen(false); onAction(action, project); };
  const needsProcessing = project.progress < 100 && project.docs > 0;

  return (
    <div 
      onClick={() => onAction('View Details', project)}
      className={`bg-panel border border-panel-border rounded-xl p-6 transition-all duration-200 shadow-sm cursor-pointer relative group ${
        isMenuOpen ? 'z-[100] shadow-2xl border-text-muted/50 transform-none' : 'z-10 hover:shadow-lg hover:-translate-y-1 hover:border-text-muted/30'
      }`}
    >
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-bold text-text-main group-hover:text-primary transition-colors">{project.name}</h3>
        <div className="relative">
          <button onClick={(e) => { e.stopPropagation(); setIsMenuOpen(!isMenuOpen); }} className={`p-1 rounded-md transition-colors ${isMenuOpen ? 'text-text-main bg-background' : 'text-text-muted hover:text-text-main hover:bg-background'}`}><MoreVertical size={18} /></button>
          {isMenuOpen && (
            <>
              <div className="fixed inset-0 z-[99]" onClick={(e) => { e.stopPropagation(); setIsMenuOpen(false); }}></div>
              <div className="absolute right-0 mt-2 w-48 bg-panel border border-panel-border rounded-xl shadow-2xl z-[100] py-1.5 animate-in fade-in" onClick={e => e.stopPropagation()}>
                {needsProcessing && (
                  <div className="mb-1 pb-1 border-b border-panel-border">
                    <MenuItem icon={<Zap size={16} className="text-amber-500"/>} label="Process Pending Files" onClick={(e) => handleActionClick(e, 'Process Pending Files')} />
                  </div>
                )}
                <MenuItem icon={<FolderOpen size={16}/>} label="Open Workspace" onClick={(e) => handleActionClick(e, 'Open Workspace')} />
                <MenuItem icon={<Edit2 size={16}/>} label="Rename Project" onClick={(e) => handleActionClick(e, 'Rename Project')} />
                <MenuItem icon={<FilePlus size={16}/>} label="Add Documents" onClick={(e) => handleActionClick(e, 'Add Documents')} />
                <MenuItem icon={<Info size={16}/>} label="View Details" onClick={(e) => handleActionClick(e, 'View Details')} />
                <div className="h-px bg-panel-border my-1"></div>
                <MenuItem icon={<Download size={16}/>} label="Export Report" onClick={(e) => handleActionClick(e, 'Export Report')} />
                <MenuItem icon={<Copy size={16}/>} label="Duplicate Project" onClick={(e) => handleActionClick(e, 'Duplicate Project')} />
                <MenuItem icon={<Share2 size={16}/>} label="Share" onClick={(e) => handleActionClick(e, 'Share')} />
                <MenuItem icon={<Archive size={16}/>} label="Archive" onClick={(e) => handleActionClick(e, 'Archive')} />
                <div className="h-px bg-panel-border my-1"></div>
                <MenuItem icon={<Trash2 size={16}/>} label="Delete Project" danger onClick={(e) => handleActionClick(e, 'Delete Project')} />
              </div>
            </>
          )}
        </div>
      </div>
      
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border text-blue-400 bg-blue-500/10 border-blue-500/20">WORKSPACE</span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${project.status === 'Completed' ? 'text-purple-400 bg-purple-500/10 border-purple-500/20' : 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20'}`}>{project.status}</span>
        </div>
        <span className="text-xs font-medium text-text-muted flex items-center"><FileText size={14} className="mr-1.5"/> {project.docs} Docs</span>
      </div>

      <p className="text-sm text-text-muted mb-6">{project.desc}</p>
      
      <div className="flex justify-between items-center text-xs text-text-muted mb-3">
        <span>Size: {project.docs > 0 ? (project.docs * 1.2).toFixed(1) + ' MB' : '0 MB'}</span><span>Last activity: {project.lastActive}</span>
      </div>
      <div className="w-full h-1.5 bg-background rounded-full overflow-hidden">
        <div className={`h-full ${project.progColor} rounded-full`} style={{ width: `${project.progress}%` }}></div>
      </div>
    </div>
  );
}

function CapabilityCard({ cap, onClick }) {
  return (
    <div onClick={onClick} className="bg-panel border border-panel-border rounded-xl p-6 hover:border-text-muted/40 transition-all duration-300 group cursor-pointer shadow-sm relative overflow-hidden hover:-translate-y-1 hover:shadow-lg">
      <div className="flex items-start space-x-4"><div className={`h-10 w-10 shrink-0 rounded-lg ${cap.iconBg} flex items-center justify-center`}>{cap.icon}</div><div><h3 className="text-base font-bold text-text-main mb-1">{cap.title}</h3><p className="text-sm text-text-muted">{cap.desc}</p></div></div>
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-panel via-panel to-transparent pt-8 pb-4 px-6 translate-y-full group-hover:translate-y-0 transition-transform duration-300 flex items-center text-primary text-sm font-medium">Launch Module <ChevronRight size={16} className="ml-1" /></div>
    </div>
  );
}