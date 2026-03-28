import React, { useState, useEffect } from 'react';
import { Database, FileText, Trash2, Loader2, Search, Filter } from 'lucide-react';
import { fetchDocuments, deleteDocument } from '../api';

export default function KnowledgeBase() {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // States for our Filters!
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL'); // 'ALL', 'COMPLETED', or 'PENDING'

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const data = await fetchDocuments();
      setDocuments(data);
    } catch (error) {
      console.error("Failed to load documents");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleDelete = async (docId) => {
    if (!window.confirm("Are you sure you want to delete this document? This will also remove its vector embeddings.")) return;
    
    try {
      await deleteDocument(docId);
      loadDocuments(); // Refresh the list after deletion
    } catch (error) {
      alert("Failed to delete the document.");
    }
  };

  // --- DYNAMIC FILTERING LOGIC ---
  const filteredDocs = documents.filter(doc => {
    const matchesSearch = doc.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || doc.processing_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="animate-in fade-in duration-500 pb-12 h-full flex flex-col">
      {/* Page Header */}
      <div className="flex justify-between items-start mb-8 shrink-0">
        <div>
          <h2 className="text-3xl font-bold mb-1 text-text-main flex items-center space-x-3">
            <Database className="text-primary" size={28} />
            <span>Knowledge Base</span>
          </h2>
          <p className="text-text-muted text-sm">Manage and audit all indexed documents across your workspace</p>
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4 mb-8 shrink-0">
        
        {/* Search */}
        <div className="relative flex-1">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
          <input 
            type="text" 
            placeholder="Search documents by name..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-panel border border-panel-border rounded-xl py-3 pl-12 pr-4 text-text-main placeholder:text-text-muted focus:outline-none focus:border-primary/50 transition-colors"
          />
        </div>

        {/* --- WORKING STATUS FILTER --- */}
        <div className="relative shrink-0">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="appearance-none w-full sm:w-auto bg-panel border border-panel-border hover:border-text-muted/50 text-text-main px-5 py-3 pl-11 rounded-xl font-medium transition-colors focus:outline-none focus:border-primary/50 cursor-pointer"
          >
            <option value="ALL">All Statuses</option>
            <option value="COMPLETED">Completed Only</option>
            <option value="PENDING">Pending Only</option>
          </select>
          <Filter size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-panel border border-panel-border rounded-xl overflow-hidden shadow-sm flex-1 flex flex-col">
        <div className="overflow-x-auto flex-1">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-background z-10">
              <tr className="border-b border-panel-border text-xs uppercase tracking-wider text-text-muted">
                <th className="p-4 font-semibold">Document Name</th>
                <th className="p-4 font-semibold">Project ID</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Uploaded At</th>
                <th className="p-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-panel-border">
              {isLoading ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center">
                    <Loader2 className="animate-spin text-primary mx-auto mb-2" size={32} />
                    <p className="text-text-muted text-sm">Loading documents...</p>
                  </td>
                </tr>
              ) : filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-12 text-center text-text-muted">
                    <Database size={40} className="mx-auto mb-4 opacity-30" />
                    <p>No documents found matching your filters.</p>
                  </td>
                </tr>
              ) : (
                filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-background/50 transition-colors group">
                    <td className="p-4">
                      <div className="flex items-center space-x-3">
                        <div className="h-8 w-8 rounded bg-blue-500/10 flex items-center justify-center shrink-0">
                          <FileText size={16} className="text-blue-500" />
                        </div>
                        <span className="font-medium text-text-main text-sm">{doc.filename}</span>
                      </div>
                    </td>
                    <td className="p-4 text-sm text-text-muted font-mono">{doc.project}</td>
                    <td className="p-4">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        doc.processing_status === 'COMPLETED' 
                          ? 'text-emerald-500 bg-emerald-500/10 border border-emerald-500/20' 
                          : 'text-amber-500 bg-amber-500/10 border border-amber-500/20'
                      }`}>
                        {doc.processing_status}
                      </span>
                    </td>
                    <td className="p-4 text-sm text-text-muted">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="p-4 text-right">
                      <button 
                        onClick={() => handleDelete(doc.id)}
                        className="text-text-muted hover:text-rose-500 p-2 rounded-lg hover:bg-rose-500/10 transition-colors opacity-0 group-hover:opacity-100"
                        title="Delete Document"
                      >
                        <Trash2 size={18} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}