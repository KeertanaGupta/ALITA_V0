import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, FolderOpen, Database, FileText, 
  Activity, Code, Settings, Terminal, Moon, Sun, User, 
  Cpu, HardDrive, ShieldCheck, Zap, Server, ChevronRight,
  GitBranch, Lightbulb, Lock, Search, Play
} from 'lucide-react';
import Projects from './pages/Projects';
import DocumentStudio from './pages/DocumentStudio';
import InsightEngine from './pages/InsightEngine';

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
              <Route path="insight" element={<InsightEngine/>}/>
            </Routes>
          </div>
        </main>
      </div>
    </Router>
  );
}

// --- TOPBAR & SIDEBAR ---

function Topbar({ isDark, toggleTheme }) {
  const location = useLocation();
  const title = location.pathname === '/projects' ? 'Project Workspace' : 'Control Center';

  return (
    <header className="h-16 border-b border-panel-border flex items-center justify-between px-8 bg-background/80 backdrop-blur-md z-10 shrink-0 transition-colors duration-300">
      <h1 className="text-lg font-semibold text-text-main">{title}</h1>
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full border bg-emerald-500/10 border-emerald-500/20 text-emerald-500 text-xs font-semibold tracking-wide">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
          <span>LLM Active</span>
        </div>
        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full border bg-panel border-panel-border text-text-muted text-xs font-semibold">
          <HardDrive size={14} /><span>2.4GB</span>
        </div>
        <div className="h-5 w-px bg-panel-border mx-1"></div>
        <button onClick={toggleTheme} className="h-9 w-9 rounded-full bg-panel border border-panel-border flex items-center justify-center text-text-muted hover:text-text-main transition-colors">
          {isDark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button className="h-9 w-9 rounded-full bg-primary/20 border border-primary/50 text-primary flex items-center justify-center hover:scale-105 transition-transform">
          <User size={16} />
        </button>
      </div>
    </header>
  );
}

function Sidebar() {
  const location = useLocation();
  return (
    <aside className="w-64 border-r border-panel-border bg-background flex flex-col z-20 transition-colors duration-300">
      <div className="h-16 flex items-center px-6 border-b border-panel-border">
        <div className="h-7 w-7 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center mr-3 shadow-[0_0_10px_rgba(225,29,72,0.4)]"></div>
        <span className="text-lg font-bold tracking-wider">ALITA</span>
      </div>
      <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
        <SidebarItem to="/" icon={<LayoutDashboard size={18} />} label="Dashboard" active={location.pathname === '/'} />
        <SidebarItem to="/projects" icon={<FolderOpen size={18} />} label="Projects" active={location.pathname === '/projects'} />
        <SidebarItem to="#" icon={<Database size={18} />} label="Knowledge Base" />
        <SidebarItem to="/studio" icon={<FileText size={18} />} label="AI Document Studio" active={location.pathname === '/studio'} />
        <SidebarItem to="/insight" icon={<Activity size={18} />} label="Insight Engine" active={location.pathname === '/insight'} />
        
        <div className="pt-6 pb-2">
          <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest px-3">Developer Tools</p>
        </div>
        <SidebarItem to="#" icon={<Code size={18} />} label="Code Intelligence" />
        <SidebarItem to="#" icon={<Terminal size={18} />} label="API Workspace" />
        <SidebarItem to="#" icon={<Settings size={18} />} label="Settings" />
      </nav>
    </aside>
  );
}

function SidebarItem({ icon, label, to, active }) {
  return (
    <Link to={to} className={`flex items-center space-x-3 px-3 py-2.5 rounded-md transition-all duration-200 group ${active ? 'bg-panel border border-panel-border' : 'border border-transparent hover:bg-panel/50'}`}>
      <span className={active ? 'text-primary' : 'text-text-muted group-hover:text-text-main transition-colors'}>{icon}</span>
      <span className={`text-sm font-medium ${active ? 'text-text-main' : 'text-text-muted group-hover:text-text-main'}`}>{label}</span>
    </Link>
  );
}

// --- MAIN DASHBOARD VIEW ---

function Dashboard() {
  // Dummy data representing what we will fetch from Django later
  const activeProjects = [
    { name: "Enterprise Research Q1 2026", badge: "Confidential", badgeColor: "text-orange-500 bg-orange-500/10 border-orange-500/20", docs: 342, desc: "Market analysis and competitive intelligence for Q1 strategic planning", lastActive: "2 hours ago", progress: 78, progColor: "bg-orange-500" },
    { name: "Product Development Archive", badge: "Secret", badgeColor: "text-rose-500 bg-rose-500/10 border-rose-500/20", docs: 1205, desc: "Technical specifications, design docs, and engineering roadmaps", lastActive: "5 hours ago", progress: 95, progColor: "bg-rose-500" },
    { name: "Legal & Compliance Repository", badge: "Secret", badgeColor: "text-rose-500 bg-rose-500/10 border-rose-500/20", docs: 589, desc: "Contracts, regulatory filings, and compliance documentation", lastActive: "1 day ago", progress: 100, progColor: "bg-purple-500" },
    { name: "Customer Intelligence", badge: "Standard", badgeColor: "text-slate-400 bg-slate-500/10 border-slate-500/20", docs: 711, desc: "Customer feedback analysis, support tickets, and usage patterns", lastActive: "3 hours ago", progress: 62, progColor: "bg-cyan-500" }
  ];

  const capabilities = [
    { title: "AI Document Studio", desc: "Generate, analyze, and transform documents with AI", icon: <FileText size={20} className="text-rose-500"/>, iconBg: "bg-rose-500/10" },
    { title: "Smart Context Memory", desc: "Persistent conversation context across sessions", icon: <Cpu size={20} className="text-purple-500"/>, iconBg: "bg-purple-500/10" },
    { title: "Insight Engine", desc: "Extract key insights and generate summaries", icon: <Activity size={20} className="text-emerald-500"/>, iconBg: "bg-emerald-500/10" },
    { title: "Document Comparison", desc: "Side-by-side intelligent document analysis", icon: <GitBranch size={20} className="text-emerald-500"/>, iconBg: "bg-emerald-500/10" },
    { title: "Smart Task Extraction", desc: "Automatically identify action items and tasks", icon: <Search size={20} className="text-rose-500"/>, iconBg: "bg-rose-500/10" },
    { title: "Idea Expansion Mode", desc: "Brainstorm and expand concepts systematically", icon: <Lightbulb size={20} className="text-yellow-500"/>, iconBg: "bg-yellow-500/10" }
  ];

  return (
    <div className="animate-in fade-in duration-500 pb-12">
      <h2 className="text-xl font-bold mb-4 text-text-main">System Intelligence</h2>
      
      {/* Top Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        <MetricCard icon={<FileText size={18} className="text-rose-500" />} iconBg="bg-rose-500/10" title="Documents Indexed" value="2,847" subtext="+124 this week" />
        <MetricCard icon={<Server size={18} className="text-purple-500" />} iconBg="bg-purple-500/10" title="Active Model" value="Mistral-7B" subtext="Local deployment" />
        <MetricCard icon={<Cpu size={18} className="text-emerald-500" />} iconBg="bg-emerald-500/10" title="Embedding Model" value="BGE-Small-EN" subtext="Offline Vectorization" />
        <MetricCard icon={<Lock size={18} className="text-rose-500" />} iconBg="bg-rose-500/10" title="Encryption Status" value="AES-256" subtext="Full disk encrypted" />
      </div>

      <h2 className="text-xl font-bold mb-4 text-text-main">Active Projects</h2>
      
      {/* Active Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
        {activeProjects.map((proj, idx) => (
          <ProjectCard key={idx} project={proj} />
        ))}
      </div>

      <h2 className="text-xl font-bold mb-4 text-text-main">AI Capability Modules</h2>
      
      {/* Capabilities Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {capabilities.map((cap, idx) => (
          <CapabilityCard key={idx} cap={cap} />
        ))}
      </div>
    </div>
  );
}

// --- REUSABLE UI CARDS ---

function MetricCard({ icon, iconBg, title, value, subtext }) {
  return (
    <div className="bg-panel border border-panel-border rounded-xl p-5 hover:border-text-muted/30 transition-all duration-300 shadow-sm">
      <div className={`h-10 w-10 rounded-lg ${iconBg} flex items-center justify-center mb-4`}>{icon}</div>
      <p className="text-xs font-medium text-text-muted mb-1">{title}</p>
      <h4 className="text-2xl font-bold text-text-main mb-1">{value}</h4>
      <p className="text-xs text-text-muted">{subtext}</p>
    </div>
  );
}

function ProjectCard({ project }) {
  return (
    <div className="bg-panel border border-panel-border rounded-xl p-6 hover:border-text-muted/40 transition-all duration-300 relative overflow-hidden shadow-sm group cursor-pointer">
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-bold text-text-main">{project.name}</h3>
        <ChevronRight size={18} className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
      
      <div className="flex items-center space-x-3 mb-4">
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${project.badgeColor}`}>
          {project.badge}
        </span>
        <span className="text-xs text-text-muted">{project.docs} documents</span>
      </div>
      
      <p className="text-sm text-text-muted mb-6">{project.desc}</p>
      
      <div className="flex justify-between items-center text-xs text-text-muted mb-3">
        <span>Last activity: {project.lastActive}</span>
      </div>

      {/* Progress Bar (As seen in the video!) */}
      <div className="w-full h-1.5 bg-background rounded-full overflow-hidden">
        <div className={`h-full ${project.progColor} rounded-full`} style={{ width: `${project.progress}%` }}></div>
      </div>
    </div>
  );
}

function CapabilityCard({ cap }) {
  return (
    <div className="bg-panel border border-panel-border rounded-xl p-6 hover:border-text-muted/40 transition-all duration-300 group cursor-pointer shadow-sm relative overflow-hidden">
      <div className="flex items-start space-x-4">
        <div className={`h-10 w-10 shrink-0 rounded-lg ${cap.iconBg} flex items-center justify-center`}>
          {cap.icon}
        </div>
        <div>
          <h3 className="text-base font-bold text-text-main mb-1">{cap.title}</h3>
          <p className="text-sm text-text-muted">{cap.desc}</p>
        </div>
      </div>
      
      {/* Hover overlay exact to the video */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-panel via-panel to-transparent pt-8 pb-4 px-6 translate-y-full group-hover:translate-y-0 transition-transform duration-300 flex items-center text-primary text-sm font-medium">
        Launch Module <ChevronRight size={16} className="ml-1" />
      </div>
    </div>
  );
}

function ProjectsPlaceholder() {
  return (
    <div className="animate-in fade-in duration-500 flex flex-col items-center justify-center h-full text-center">
      <FolderOpen size={48} className="text-text-muted mb-4 opacity-20" />
      <h2 className="text-2xl font-bold text-text-main mb-2">Projects View</h2>
      <p className="text-text-muted">We will wire this up to Django Axios next!</p>
    </div>
  );
}