import React, { useState, useEffect } from 'react';
import { 
  FolderOpen, FileText, Activity, HardDrive, 
  Search, Filter, MoreVertical, Folder, Loader2
} from 'lucide-react';
import { fetchProjects } from '../api'; // Import our new API function!

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // Load data from Django when the component mounts
  useEffect(() => {
    const loadData = async () => {
      try {
        const data = await fetchProjects();
        // Format the raw Django data to match our beautiful UI cards
        const formattedProjects = data.map(formatProjectData);
        setProjects(formattedProjects);
      } catch (error) {
        console.error("Failed to load projects from Django.");
      } finally {
        setIsLoading(false);
      }
    };
    
    loadData();
  }, []);

  // Calculate top-level metrics dynamically
  const totalProjects = projects.length;
  const totalDocs = projects.reduce((sum, p) => sum + p.docs, 0);
  const activeProjects = projects.filter(p => p.progress < 100).length;

  return (
    <div className="animate-in fade-in duration-500 pb-12">
      
      {/* Page Header */}
      <div className="flex justify-between items-start mb-8">
        <div>
          <h2 className="text-3xl font-bold mb-1 text-text-main">Project Workspace</h2>
          <p className="text-text-muted text-sm">Manage and organize your intelligent knowledge projects</p>
        </div>
        <button className="bg-indigo-500/90 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg font-medium transition-colors shadow-[0_0_15px_rgba(99,102,241,0.3)] text-sm flex items-center">
          + New Project
        </button>
      </div>

      {/* Top Metrics Summary (Dynamic!) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <SummaryCard icon={<Folder size={20} className="text-blue-400" />} iconBg="bg-blue-500/10" value={isLoading ? "-" : totalProjects} label="Total Projects" />
        <SummaryCard icon={<FileText size={20} className="text-purple-400" />} iconBg="bg-purple-500/10" value={isLoading ? "-" : totalDocs} label="Total Documents" />
        <SummaryCard icon={<Activity size={20} className="text-emerald-400" />} iconBg="bg-emerald-500/10" value={isLoading ? "-" : activeProjects} label="Active Projects" />
        <SummaryCard icon={<HardDrive size={20} className="text-blue-500" />} iconBg="bg-blue-500/10" value="-- GB" label="Storage Used" />
      </div>

      {/* Projects Grid */}
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="animate-spin text-primary" size={40} />
        </div>
      ) : projects.length === 0 ? (
        <div className="bg-panel border border-dashed border-panel-border rounded-xl p-12 text-center">
          <FolderOpen size={48} className="mx-auto text-text-muted mb-4 opacity-50" />
          <h3 className="text-xl font-semibold text-text-main mb-2">No Projects Found</h3>
          <p className="text-text-muted">Create your first project to start organizing documents.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {projects.map((proj) => (
            <DetailedProjectCard key={proj.id} project={proj} />
          ))}
        </div>
      )}
    </div>
  );
}

// --- HELPER FUNCTION: Maps Django data to UI styling ---
function formatProjectData(djangoProject) {
  const docs = djangoProject.documents || [];
  const docCount = docs.length;
  
  // Calculate real indexing progress based on Document status!
  const completedDocs = docs.filter(d => d.processing_status === 'COMPLETED').length;
  let progress = 0;
  if (docCount > 0) {
    progress = Math.round((completedDocs / docCount) * 100);
  }

  // Set colors based on progress
  const isComplete = progress === 100 && docCount > 0;
  
  return {
    id: djangoProject.id,
    name: djangoProject.name,
    type: "Workspace",
    status: isComplete ? "Completed" : "Active",
    docs: docCount,
    size: "-- MB", // Can be wired to real file sizes later
    lastActive: new Date(djangoProject.updated_at).toLocaleDateString(),
    progress: progress,
    typeColor: "text-blue-400 border-blue-500/20",
    statusColor: isComplete ? "text-purple-400 bg-purple-500/10" : "text-emerald-500 bg-emerald-500/10",
    progColor: isComplete ? "bg-purple-500" : "bg-emerald-500"
  };
}

// --- SUB-COMPONENTS ---

function SummaryCard({ icon, iconBg, value, label }) {
  return (
    <div className="bg-panel border border-panel-border rounded-xl p-6 flex items-center space-x-4 shadow-sm">
      <div className={`h-12 w-12 rounded-xl ${iconBg} flex items-center justify-center shrink-0`}>
        {icon}
      </div>
      <div>
        <h3 className="text-2xl font-bold text-text-main">{value}</h3>
        <p className="text-sm text-text-muted">{label}</p>
      </div>
    </div>
  );
}

function DetailedProjectCard({ project }) {
  return (
    <div className="bg-panel border border-panel-border rounded-xl p-6 hover:border-text-muted/30 transition-all duration-300 group cursor-pointer shadow-sm flex flex-col justify-between min-h-[220px]">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-lg bg-background border border-panel-border flex items-center justify-center shrink-0">
            <FolderOpen size={20} className={project.progColor.replace('bg-', 'text-')} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-text-main leading-tight">{project.name}</h3>
            <div className="flex items-center space-x-2 mt-1.5">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border flex items-center space-x-1 ${project.typeColor}`}>
                <div className={`h-1.5 w-1.5 rounded-full ${project.typeColor.split(' ')[0].replace('text-', 'bg-')}`}></div>
                <span>{project.type}</span>
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${project.statusColor}`}>
                {project.status}
              </span>
            </div>
          </div>
        </div>
        <button className="text-text-muted hover:text-text-main p-1 transition-colors">
          <MoreVertical size={18} />
        </button>
      </div>
      
      <div className="grid grid-cols-3 gap-4 mb-5 border-t border-b border-panel-border py-3 mt-auto">
        <div>
          <p className="text-xs text-text-muted mb-0.5">Documents</p>
          <p className="text-sm font-semibold text-text-main">{project.docs}</p>
        </div>
        <div>
          <p className="text-xs text-text-muted mb-0.5">Size</p>
          <p className="text-sm font-semibold text-text-main">{project.size}</p>
        </div>
        <div>
          <p className="text-xs text-text-muted mb-0.5">Last Activity</p>
          <p className="text-sm font-semibold text-text-main">{project.lastActive}</p>
        </div>
      </div>

      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-text-muted">Indexing Progress</span>
          <span className="font-bold text-text-main">{project.progress}%</span>
        </div>
        <div className="w-full h-1.5 bg-background rounded-full overflow-hidden">
          <div className={`h-full ${project.progColor} rounded-full`} style={{ width: `${project.progress}%`, transition: 'width 1s ease-in-out' }}></div>
        </div>
      </div>
    </div>
  );
}