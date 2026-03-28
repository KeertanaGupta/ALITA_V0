import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  FolderOpen, FileText, Activity, HardDrive, MoreVertical, Folder, Loader2, X, Plus,
  Edit2, FilePlus, Info, Download, Copy, Trash2, Share2, Archive, Zap, UploadCloud, Shield, CheckCircle2, PlaySquare
} from 'lucide-react';
import { fetchProjects, createProject, deleteProject, updateProject, uploadDocument, processDocumentFastAPI, updateDocumentStatus } from '../api';

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  
  // MODALS
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDesc, setNewProjectDesc] = useState('');
  const [securityLevel, setSecurityLevel] = useState('Standard');
  
  const [projectToRename, setProjectToRename] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [projectForDetails, setProjectForDetails] = useState(null);
  const [projectForUpload, setProjectForUpload] = useState(null);

  // UPLOAD
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [autoProcess, setAutoProcess] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const data = await fetchProjects();
      setProjects(data.map(formatProjectData));
    } catch (error) { console.error("Failed to load projects."); } 
    finally { setIsLoading(false); }
  };

  useEffect(() => { loadData(); }, []);

  const handleProjectAction = async (action, project) => {
    if (action === 'Delete Project') {
      if (window.confirm(`Are you absolutely sure you want to delete "${project.name}"?`)) {
        try { await deleteProject(project.id); loadData(); } catch (e) { alert("Failed to delete."); }
      }
    } 
    else if (action === 'Rename Project') { setRenameValue(project.name); setProjectToRename(project); } 
    else if (action === 'View Details') { setProjectForDetails(project); } 
    else if (action === 'Open Workspace') { navigate('/insight'); } 
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
        loadData();
      } catch (err) {} finally { setIsProcessing(false); }
    }
    else { alert(`System Notification: "${action}" triggered for ${project.name}.`); }
  };

  // UPLOADS
  const handleDrag = (e) => { e.preventDefault(); e.stopPropagation(); if (e.type === "dragenter" || e.type === "dragover") setDragActive(true); else if (e.type === "dragleave") setDragActive(false); };
  const handleDrop = (e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); if (e.dataTransfer.files) handleFiles(e.dataTransfer.files); };
  const handleChange = (e) => { e.preventDefault(); if (e.target.files) handleFiles(e.target.files); };
  const handleFiles = (files) => { setSelectedFiles(prev => [...prev, ...Array.from(files)]); };
  const removeFile = (index) => { setSelectedFiles(prev => prev.filter((_, i) => i !== index)); };

  const submitCreate = async (e) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    setIsProcessing(true);
    let hasUploadErrors = false;

    try {
      // 1. Create the Project
      const newProj = await createProject(newProjectName, newProjectDesc);
      
      // 2. If files were attached, upload and process them immediately
      if (selectedFiles.length > 0 && newProj) {
        for (const file of selectedFiles) {
          if (!file.name.toLowerCase().endsWith('.pdf')) {
            console.warn(`Skipped "${file.name}". Only PDF allowed.`);
            continue;
          }
          
          let docData;
          
          // --- PHASE 1: UPLOAD ---
          try {
            docData = await uploadDocument(newProj.id, file);
          } catch (uploadError) {
            console.error("Django Upload Error:", uploadError);
            hasUploadErrors = true;
            continue; 
          }
          
          // --- PHASE 2: AI PROCESSING & INDEXING ---
          if (docData) {
            try {
              await processDocumentFastAPI(docData.id, newProj.id, docData.file);
              
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
      }

      if (hasUploadErrors) {
        alert("Project created, but some initial files could not be uploaded to the database.");
      }

      // 3. Reset UI and reload
      setIsCreateModalOpen(false);
      setNewProjectName('');
      setNewProjectDesc('');
      setSecurityLevel('Standard');
      setSelectedFiles([]);
      await loadData(); 
      
    } catch (error) {
      console.error("Project Creation Error:", error);
      alert("Failed to create project.");
    } finally {
      setIsProcessing(false);
    }
  };

  const submitUpload = async (e) => {
    e.preventDefault();
    setIsProcessing(true);
    try {
      for (const file of selectedFiles) {
        // Upload the file to Django
        const docData = await uploadDocument(projectForUpload.id, file);
        
        // If the Auto-Process checkbox is true, index it with FastAPI
        if (autoProcess) {
          try {
            await processDocumentFastAPI(docData.id, projectForUpload.id, docData.file);
            await updateDocumentStatus(docData.id, 'COMPLETED');
          } catch (aiError) {
            console.error("FastAPI processing failed:", aiError);
            await updateDocumentStatus(docData.id, 'FAILED');
          }
        }
      }
      
      // CRITICAL FIX: Await the fresh data BEFORE closing the modal!
      await loadData(); 
      setProjectForUpload(null);
      setSelectedFiles([]);
      
    } catch (error) {
      alert("Failed to upload files.");
    } finally {
      setIsProcessing(false);
    }
  };

  const submitRename = async (e) => {
    e.preventDefault(); if (!renameValue.trim()) return;
    setIsProcessing(true);
    try { await updateProject(projectToRename.id, { name: renameValue }); setProjectToRename(null); loadData(); } 
    catch (error) { alert("Failed to rename."); } finally { setIsProcessing(false); }
  };

  const totalProjects = projects.length;
  const totalDocs = projects.reduce((sum, p) => sum + p.docs, 0);
  const activeProjects = projects.filter(p => p.progress < 100).length;

  return (
    <div className="animate-in fade-in duration-500 pb-12 min-h-full relative">
      <div className="flex justify-between items-start mb-8">
        <div><h2 className="text-3xl font-bold mb-1 text-text-main">Project Workspace</h2><p className="text-text-muted text-sm">Manage and organize your intelligent knowledge projects</p></div>
        <button onClick={() => { setIsCreateModalOpen(true); setSelectedFiles([]); }} className="bg-indigo-500/90 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg font-medium transition-transform hover:scale-105 shadow-[0_0_15px_rgba(99,102,241,0.3)] text-sm flex items-center space-x-2"><Plus size={18} /><span>New Project</span></button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <SummaryCard icon={<Folder size={20} className="text-blue-400" />} iconBg="bg-blue-500/10" value={isLoading ? "-" : totalProjects} label="Total Projects" />
        <SummaryCard icon={<FileText size={20} className="text-purple-400" />} iconBg="bg-purple-500/10" value={isLoading ? "-" : totalDocs} label="Total Documents" />
        <SummaryCard icon={<Activity size={20} className="text-emerald-400" />} iconBg="bg-emerald-500/10" value={isLoading ? "-" : activeProjects} label="Active Projects" />
        <SummaryCard icon={<HardDrive size={20} className="text-blue-500" />} iconBg="bg-blue-500/10" value="-- GB" label="Storage Used" />
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary" size={40} /></div>
      ) : projects.length === 0 ? (
        <div className="bg-panel border border-dashed border-panel-border rounded-xl p-12 text-center"><FolderOpen size={48} className="mx-auto text-text-muted mb-4 opacity-50" /><h3 className="text-xl font-semibold text-text-main mb-2">No Projects Found</h3></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {projects.map((proj) => (<DetailedProjectCard key={proj.id} project={proj} onAction={(action) => handleProjectAction(action, proj)} />))}
        </div>
      )}

      {/* --- CREATE MODAL --- */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-panel border border-panel-border rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col animate-in zoom-in-95">
            <div className="flex justify-between items-center p-6 border-b border-panel-border bg-background/50">
              <h3 className="text-xl font-bold text-text-main flex items-center space-x-3">
                <FolderOpen className="text-indigo-400" size={24} /><span>Create New Project</span>
              </h3>
              <button onClick={() => { setIsCreateModalOpen(false); setSelectedFiles([]); }} className="text-text-muted hover:text-rose-500 hover:bg-rose-500/10 rounded-lg p-2 transition-colors"><X size={20} /></button>
            </div>
            <form onSubmit={submitCreate} className="p-8 space-y-6">
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-6">
                  <div>
                    <label className="block text-xs font-bold text-text-muted uppercase tracking-wider mb-2">Project Name <span className="text-rose-500">*</span></label>
                    <input type="text" autoFocus required value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} className="w-full bg-background border border-panel-border text-text-main rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500/50 shadow-inner" disabled={isProcessing} />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-text-muted uppercase mb-2">Security Level</label>
                    <div className="relative">
                      <select value={securityLevel} onChange={(e) => setSecurityLevel(e.target.value)} className="w-full appearance-none bg-background border border-panel-border text-text-main rounded-xl px-4 py-3 pl-10 focus:outline-none focus:border-indigo-500/50 cursor-pointer shadow-inner">
                        <option value="Standard">Standard</option>
                        <option value="Confidential">Confidential</option>
                        <option value="Secret">Secret</option>
                      </select>
                      <Shield size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                    </div>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-text-muted uppercase tracking-wider mb-2">Description (Optional)</label>
                  <textarea value={newProjectDesc} onChange={(e) => setNewProjectDesc(e.target.value)} className="w-full h-[124px] bg-background border border-panel-border text-text-main rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500/50 shadow-inner resize-none" disabled={isProcessing} />
                </div>
              </div>

              {/* INITIAL DOCUMENTS DRAG AND DROP */}
              <div>
                <label className="block text-xs font-bold text-text-muted uppercase tracking-wider mb-2">Initial Documents (Optional)</label>
                <div className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-colors ${dragActive ? 'border-indigo-500 bg-indigo-500/10' : 'border-panel-border bg-background hover:bg-panel'}`} onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}>
                    <input type="file" multiple accept="application/pdf" onChange={handleChange} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" disabled={isProcessing} />
                    <UploadCloud size={28} className={`mx-auto mb-2 ${dragActive ? 'text-indigo-500' : 'text-text-muted'}`} />
                    <p className="text-sm font-medium text-text-main mb-1">Drag & drop PDF files here</p>
                </div>
                {selectedFiles.length > 0 && (
                    <div className="mt-3 max-h-24 overflow-y-auto space-y-2 custom-scrollbar border border-panel-border p-2 rounded-lg bg-background">
                      {selectedFiles.map((file, idx) => (
                        <div key={idx} className="flex justify-between items-center px-2 text-sm">
                          <span className="truncate text-text-main">{file.name}</span>
                          <button type="button" onClick={() => removeFile(idx)} className="text-text-muted hover:text-rose-500"><X size={16} /></button>
                        </div>
                      ))}
                    </div>
                )}
              </div>

              <div className="pt-4 flex items-center justify-end space-x-3 border-t border-panel-border">
                <button type="button" onClick={() => { setIsCreateModalOpen(false); setSelectedFiles([]); }} className="px-5 py-2.5 rounded-xl text-sm font-medium text-text-muted hover:text-text-main hover:bg-background transition-colors" disabled={isProcessing}>Cancel</button>
                <button type="submit" disabled={!newProjectName.trim() || isProcessing} className="px-6 py-2.5 rounded-xl text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-panel-border disabled:text-text-muted transition-all shadow-md">
                  {isProcessing ? <><Loader2 size={16} className="animate-spin inline mr-2" />Creating...</> : "Create Workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* UPLOAD MODAL */}
      {projectForUpload && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-panel border border-panel-border rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col animate-in zoom-in-95">
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

      {/* RENAME MODAL */}
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

      {/* DRILL DOWN MODAL */}
      {projectForDetails && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-panel border border-panel-border rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col animate-in zoom-in-95">
            <div className="flex justify-between items-center p-6 border-b border-panel-border bg-background/50">
              <div className="flex items-center space-x-3 mb-1"><div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20"><FolderOpen className="text-primary" size={20} /></div><div><h2 className="text-2xl font-bold text-text-main leading-none">{projectForDetails.name}</h2></div></div>
              <button onClick={() => setProjectForDetails(null)} className="text-text-muted hover:text-rose-500 hover:bg-rose-500/10 rounded-lg p-2 transition-colors"><X size={24} /></button>
            </div>
            <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="md:col-span-2 space-y-3">
                <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider flex items-center space-x-2">📄 <span>Indexed Documents</span></h3>
                <div className="bg-background border border-panel-border rounded-xl p-4 h-64 overflow-y-auto custom-scrollbar shadow-inner">
                  {projectForDetails.docNames && projectForDetails.docNames.length > 0 ? (
                    <ul className="space-y-2">{projectForDetails.docNames.map((name, idx) => (<li key={idx} className="flex items-center space-x-3 text-sm text-text-main p-3 bg-panel rounded-lg border border-panel-border"><FileText size={18} className="text-blue-500 shrink-0 "/><span className="truncate">{name}</span></li>))}</ul>
                  ) : (<div className="h-full flex flex-col items-center justify-center text-text-muted"><FileText size={40} className="mb-3 opacity-50" /><p className="text-sm font-medium">No documents found</p></div>)}
                </div>
              </div>
              <div className="space-y-8">
                <div>
                  <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3 flex items-center space-x-2">📊 <span>Project Stats</span></h3>
                  <div className="space-y-3">
                    <div className="bg-background p-3 rounded-xl border border-panel-border flex justify-between items-center"><span className="text-xs text-text-muted">Total Docs</span><span className="font-bold">{projectForDetails.docs}</span></div>
                    <div className="bg-background p-3 rounded-xl border border-panel-border flex justify-between items-center"><span className="text-xs text-text-muted">Total Size</span><span className="font-bold">{projectForDetails.size}</span></div>
                  </div>
                </div>
                <div>
                  <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider mb-3 flex items-center space-x-2">⚡ <span>Quick Actions</span></h3>
                  <div className="space-y-2">
                    <button onClick={() => navigate('/insight')} className="w-full flex items-center space-x-3 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 py-2.5 px-4 rounded-xl text-sm font-bold transition-all hover:bg-indigo-500/20"><FolderOpen size={16} /><span>Open Workspace</span></button>
                    <button onClick={() => { setProjectForDetails(null); handleProjectAction('Add Documents', projectForDetails); }} className="w-full flex items-center space-x-3 bg-panel border border-panel-border py-2.5 px-4 rounded-xl text-sm font-medium transition-colors hover:bg-panel-border"><FilePlus size={16} /><span>Add Document</span></button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PROCESSING OVERLAY */}
      {isProcessing && !isCreateModalOpen && !projectForUpload && !projectToRename && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in"><div className="bg-panel border border-panel-border p-6 rounded-xl flex flex-col items-center"><Loader2 size={40} className="animate-spin text-indigo-500 mb-4" /><p className="text-text-main font-bold">Processing Documents...</p></div></div>
      )}
    </div>
  );
}

// --- HELPER FUNCTIONS ---
function formatProjectData(p) {
  const docs = p.documents || [];
  const completedDocs = docs.filter(d => d.processing_status === 'COMPLETED').length;
  const progress = docs.length > 0 ? Math.round((completedDocs / docs.length) * 100) : 0;
  return { 
    id: p.id, name: p.name, desc: p.description, rawDocuments: docs,
    docs: docs.length, docNames: docs.map(d => d.filename), size: docs.length > 0 ? (docs.length * 1.2).toFixed(1) + " MB" : "0 MB", 
    lastActive: new Date(p.updated_at).toLocaleDateString(), progress: progress, 
    status: progress === 100 && docs.length > 0 ? "Completed" : "Active",
    progColor: progress === 100 && docs.length > 0 ? "bg-purple-500" : "bg-emerald-500" 
  };
}

function SummaryCard({ icon, iconBg, value, label }) {
  return (
    <div className="bg-panel border border-panel-border rounded-xl p-6 flex items-center space-x-4 shadow-sm">
      <div className={`h-12 w-12 rounded-xl ${iconBg} flex items-center justify-center shrink-0`}>{icon}</div>
      <div><h3 className="text-2xl font-bold text-text-main">{value}</h3><p className="text-sm text-text-muted">{label}</p></div>
    </div>
  );
}

function MenuItem({ icon, label, danger, onClick }) {
  return (
    <button onClick={onClick} className={`w-full flex items-center space-x-3 px-4 py-2 text-sm font-medium transition-colors hover:bg-background ${danger ? 'text-rose-500 hover:text-rose-400' : 'text-text-main'}`}>
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
      className={`bg-panel border border-panel-border rounded-xl p-6 transition-all duration-200 flex flex-col justify-between min-h-[220px] cursor-pointer shadow-sm relative group ${
        isMenuOpen ? 'z-[100] shadow-2xl border-text-muted/50 transform-none' : 'z-10 hover:shadow-lg hover:-translate-y-1 hover:border-text-muted/30'
      }`}
    >
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-lg bg-background border border-panel-border flex items-center justify-center shrink-0"><FolderOpen size={20} className={project.progColor.replace('bg-', 'text-')} /></div>
          <div>
            <h3 className="text-lg font-bold text-text-main leading-tight">{project.name}</h3>
            <div className="flex items-center space-x-2 mt-1.5">
              {/* FIX: Replaced project.typeColor with safe inline classes */}
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border flex items-center space-x-1 text-blue-400 bg-blue-500/10 border-blue-500/20">
                <div className="h-1.5 w-1.5 rounded-full bg-blue-500"></div><span>WORKSPACE</span>
              </span>
              {/* FIX: Replaced project.statusColor with safe conditional check */}
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${project.status === 'Completed' ? 'text-purple-400 bg-purple-500/10 border-purple-500/20' : 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20'}`}>
                {project.status}
              </span>
            </div>
          </div>
        </div>
        
        <div className="relative">
          <button onClick={(e) => { e.stopPropagation(); setIsMenuOpen(!isMenuOpen); }} className="p-1 rounded-md text-text-muted hover:text-text-main hover:bg-background transition-colors"><MoreVertical size={18} /></button>
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
      
      <div className="flex items-center justify-between mb-4 mt-2">
        <span className="text-xs font-medium text-text-muted flex items-center"><FileText size={14} className="mr-1.5"/> {project.docs} Docs</span>
      </div>

      <p className="text-sm text-text-muted mb-6">{project.desc}</p>
      
      <div className="flex justify-between items-center text-xs text-text-muted mb-3">
        <span>Size: {project.docs > 0 ? (project.docs * 1.2).toFixed(1) + ' MB' : '0 MB'}</span><span>Last activity: {project.lastActive}</span>
      </div>
      <div>
        <div className="flex justify-between text-xs mb-1.5"><span className="text-text-muted">Indexing Progress</span><span className="font-bold text-text-main">{project.progress}%</span></div>
        <div className="w-full h-1.5 bg-background rounded-full overflow-hidden"><div className={`h-full ${project.progColor} rounded-full`} style={{ width: `${project.progress}%` }}></div></div>
      </div>
    </div>
  );
}