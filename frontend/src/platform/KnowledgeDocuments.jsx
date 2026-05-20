import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { FileText, Upload, Search, Trash2, Loader2, CheckCircle, AlertCircle, Database, Brain, RefreshCw } from 'lucide-react';
import { motion, StaggerGrid, MotionCard, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;

export default function KnowledgeDocuments({ token }) {
  const [documents, setDocuments] = useState([]);
  const [ragStatus, setRagStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [querying, setQuerying] = useState(false);
  const [queryForm, setQueryForm] = useState({ doc_id: '', query: '' });
  const [queryResult, setQueryResult] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);
  const jsonHeaders = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchData = useCallback(async () => {
    try {
      const [docsRes, ragRes] = await Promise.all([
        fetch(`${API}/api/documents/list`, { headers }),
        fetch(`${API}/api/documents/rag/status`, { headers }),
      ]);
      if (docsRes.ok) { const d = await docsRes.json(); setDocuments(d.documents || []); }
      if (ragRes.ok) setRagStatus(await ragRes.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const uploadFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API}/api/documents/upload`, {
        method: 'POST', headers, body: formData,
      });
      if (res.ok) fetchData();
    } catch (err) { console.error(err); }
    setUploading(false);
  };

  const queryDoc = async () => {
    if (!queryForm.doc_id || !queryForm.query) return;
    setQuerying(true);
    try {
      const formData = new FormData();
      formData.append('doc_id', queryForm.doc_id);
      formData.append('query', queryForm.query);
      const res = await fetch(`${API}/api/documents/query`, {
        method: 'POST', headers, body: formData,
      });
      if (res.ok) setQueryResult(await res.json());
    } catch (e) { console.error(e); }
    setQuerying(false);
  };

  const deleteDoc = async (docId) => {
    try {
      await fetch(`${API}/api/documents/${docId}`, { method: 'DELETE', headers });
      fetchData();
    } catch (e) { console.error(e); }
  };

  const engines = ragStatus?.engines || {};

  return (
    <div className="flex-1 overflow-auto p-6" style={{ background: 'transparent' }} data-testid="knowledge-documents">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between mb-6"
      >
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-heading)' }}>Knowledge Documents</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
            Multi-Agent RAG, ChromaDB + PageIndex dual retrieval
          </p>
        </div>
        <motion.button onClick={() => { setLoading(true); fetchData(); }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium"
          style={{ background: 'rgba(61,58,57,0.25)', color: 'var(--aurem-heading)' }}
          whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          data-testid="docs-refresh-btn">
          <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </motion.button>
      </motion.div>

      {/* RAG Engine Status */}
      <StaggerGrid className="grid grid-cols-2 gap-4 mb-6">
        {[
          { key: 'chromadb_minilm', icon: Database, label: 'ChromaDB / MiniLM-L6', color: '#22C55E' },
          { key: 'pageindex', icon: Brain, label: 'PageIndex (Reasoning RAG)', color: '#8B5CF6' },
        ].map(({ key, icon: Icon, label, color }) => {
          const engine = engines[key] || {};
          return (
            <MotionCard key={key} className="aurem-glass-card p-4" data-testid={`engine-${key}`} variants={cardVariant}>
              <div className="flex items-center gap-3 mb-2">
                <div className="size-9 rounded-xl flex items-center justify-center" style={{ background: `${color}15` }}>
                  <Icon className="size-4" style={{ color }} />
                </div>
                <div>
                  <div className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{label}</div>
                  <div className="text-[10px]" style={{ color: engine.status === 'active' ? '#22C55E' : '#EAB308' }}>
                    {engine.status === 'active' ? 'Active' : engine.status === 'not_configured' ? 'Not Configured (add PAGEINDEX_API_KEY)' : engine.status || 'Unknown'}
                  </div>
                </div>
              </div>
              <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{engine.use_case}</div>
              {engine.documents_indexed !== undefined && (
                <div className="text-[10px] mt-1" style={{ color: color }}>{engine.documents_indexed} documents indexed</div>
              )}
            </MotionCard>
          );
        })}
      </StaggerGrid>

      {/* Upload Section */}
      <div className="aurem-glass-card p-5 mb-6" data-testid="upload-section">
        <div className="flex items-center gap-3 mb-3">
          <Upload className="size-4" style={{ color: '#3B82F6' }} />
          <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Upload Document</span>
          <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>PDF, DOCX, TXT, MD, CSV (max 50MB)</span>
        </div>
        <label className="flex items-center justify-center gap-2 px-6 py-4 rounded-xl border-2 border-dashed cursor-pointer hover:border-[#3B82F6] transition-colors"
          style={{ borderColor: 'rgba(255,107,0,0.1)' }}>
          {uploading ? (
            <Loader2 className="size-5 animate-spin" style={{ color: '#3B82F6' }} />
          ) : (
            <>
              <FileText className="size-5" style={{ color: 'var(--aurem-body-secondary)' }} />
              <span className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Click to upload or drag & drop</span>
            </>
          )}
          <input type="file" className="hidden" accept=".pdf,.docx,.txt,.md,.csv" onChange={uploadFile} data-testid="doc-upload-input" />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Documents List */}
        <div className="aurem-glass-card overflow-hidden" data-testid="documents-list">
          <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(59,130,246,0.03)' }}>
            <FileText className="size-4" style={{ color: '#3B82F6' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Indexed Documents</span>
            <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>{documents.length} docs</span>
          </div>
          {documents.length === 0 ? (
            <div className="flex flex-col items-center py-12">
              <FileText className="size-8 mb-2" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.3 }} />
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No documents uploaded yet</p>
              <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)', opacity: 0.6 }}>
                Upload PDFs, contracts, or manuals for ORA to reason over
              </p>
            </div>
          ) : (
            <div className="max-h-[400px] overflow-y-auto aurem-scroll">
              {documents.map((doc, i) => (
                <div key={i} className="px-5 py-3 border-b flex items-center gap-3" style={{ borderColor: 'rgba(255,107,0,0.05)' }}>
                  <FileText className="size-4 flex-shrink-0" style={{ color: '#3B82F6' }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium truncate" style={{ color: 'var(--aurem-heading)' }}>{doc.filename}</div>
                    <div className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                      {(doc.size_bytes / 1024).toFixed(0)}KB | {doc.status}
                      {doc.pageindex_doc_id && <span className="ml-1 font-mono">ID: {doc.pageindex_doc_id}</span>}
                    </div>
                  </div>
                  <button onClick={() => setQueryForm({ ...queryForm, doc_id: doc.pageindex_doc_id })}
                    className="p-1 rounded hover:bg-[rgba(59,130,246,0.1)]"
                    title="Query this document">
                    <Search className="size-3" style={{ color: '#3B82F6' }} />
                  </button>
                  <button onClick={() => deleteDoc(doc.pageindex_doc_id)}
                    className="p-1 rounded hover:bg-[rgba(239,68,68,0.1)]"
                    title="Delete">
                    <Trash2 className="size-3" style={{ color: '#EF4444' }} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Query Interface */}
        <div className="aurem-glass-card overflow-hidden" data-testid="query-interface">
          <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: 'rgba(61,58,57,0.25)', background: 'rgba(139,92,246,0.03)' }}>
            <Search className="size-4" style={{ color: '#8B5CF6' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--aurem-heading)' }}>Document Query (PageIndex)</span>
          </div>
          <div className="p-5">
            <input placeholder="Document ID"
              className="w-full px-3 py-2 rounded-lg text-[11px] mb-2"
              style={{ background: 'rgba(45,122,74,0.05)', border: '1px solid rgba(255,107,0,0.1)', color: 'var(--aurem-heading)' }}
              value={queryForm.doc_id}
              onChange={(e) => setQueryForm({ ...queryForm, doc_id: e.target.value })}
              data-testid="query-doc-id"
            />
            <textarea placeholder="Ask a question about this document..."
              className="w-full px-3 py-2 rounded-lg text-[11px] mb-2"
              style={{ background: 'rgba(45,122,74,0.05)', border: '1px solid rgba(255,107,0,0.1)', color: 'var(--aurem-heading)', minHeight: '60px' }}
              value={queryForm.query}
              onChange={(e) => setQueryForm({ ...queryForm, query: e.target.value })}
              data-testid="query-text"
            />
            <button onClick={queryDoc} disabled={querying || !queryForm.doc_id || !queryForm.query}
              className="w-full px-4 py-2 rounded-lg text-[11px] font-bold flex items-center justify-center gap-2"
              style={{ background: 'linear-gradient(135deg, #8B5CF6, #7C3AED)', color: '#fff', opacity: (!queryForm.doc_id || !queryForm.query) ? 0.5 : 1 }}
              data-testid="query-submit-btn"
            >
              {querying ? <Loader2 className="size-3 animate-spin" /> : <Search className="size-3" />}
              Query Document
            </button>

            {queryResult && (
              <div className="mt-4 p-3 rounded-xl" style={{ background: 'rgba(139,92,246,0.05)', border: '1px solid rgba(139,92,246,0.15)' }}>
                <div className="flex items-center gap-2 mb-2">
                  {queryResult.reasoning ? (
                    <CheckCircle className="size-3" style={{ color: '#22C55E' }} />
                  ) : (
                    <AlertCircle className="size-3" style={{ color: '#EAB308' }} />
                  )}
                  <span className="text-[10px] font-bold" style={{ color: 'var(--aurem-heading)' }}>
                    Source: {queryResult.source}
                  </span>
                </div>
                <div className="text-xs" style={{ color: 'var(--aurem-heading)', whiteSpace: 'pre-wrap' }}>{queryResult.answer}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
