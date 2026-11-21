"use client";

import { useEffect, useState } from "react";
import {
  BookOpen,
  FileText,
  Upload,
  Search,
  CheckCircle2,
  Trash2,
  Sparkles,
  Layers,
  X,
  Filter,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import {
  MOCK_KNOWLEDGE_DOCUMENTS,
  MOCK_BRANDS,
  KnowledgeDocument,
  Brand,
} from "../lib/mockData";

export default function KnowledgePage() {
  const { user, activeDealershipId } = useAuth();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>(MOCK_KNOWLEDGE_DOCUMENTS);
  const [brands, setBrands] = useState<Brand[]>(MOCK_BRANDS);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Array<{ content: string; source: string; score: number }>>([]);
  const [searching, setSearching] = useState(false);

  // Modal
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [docTitle, setDocTitle] = useState("");
  const [docBrand, setDocBrand] = useState<string>("all");

  const isStaff = user && user.role !== "customer";

  useEffect(() => {
    api<KnowledgeDocument[]>(`/dealerships/${activeDealershipId}/knowledge/documents`)
      .then((data) => {
        if (Array.isArray(data) && data.length) setDocuments(data);
      })
      .catch(() => {});
  }, [activeDealershipId]);

  function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const brandObj = brands.find((b) => String(b.id) === docBrand);
    const newDoc: KnowledgeDocument = {
      id: Math.floor(Math.random() * 9000) + 1000,
      dealership_id: activeDealershipId,
      brand_id: docBrand === "all" ? null : Number(docBrand),
      brand_name: brandObj ? brandObj.name : "All Brands",
      title: docTitle || "Dealership Manual.pdf",
      mime_type: "application/pdf",
      source_file: "uploaded_doc.pdf",
      chunk_count: Math.floor(Math.random() * 10) + 5,
      created_at: new Date().toISOString(),
      status: "ready",
    };

    setDocuments([newDoc, ...documents]);
    setShowUploadModal(false);
    setDocTitle("");
  }

  function handleDelete(id: number) {
    setDocuments(documents.filter((d) => d.id !== id));
  }

  function handleSemanticSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);

    setTimeout(() => {
      setSearchResults([
        {
          source: "Toyota 2024 Camry Specs & Warranty Guide.pdf (Chunk #3)",
          content: "Warranty terms provide 36-month/36,000-mile comprehensive coverage and 60-month/60,000-mile powertrain coverage. Hybrid-related components are covered for 8 years or 100,000 miles.",
          score: 0.89,
        },
        {
          source: "Apex Motors Test Drive Customer Agreement & Safety.pdf (Chunk #1)",
          content: "Customers must hold a valid driver's license and complete identity verification prior to slot commencement. Rescheduling is permissible up to 2 hours before scheduled slot.",
          score: 0.82,
        },
      ]);
      setSearching(false);
    }, 400);
  }

  return (
    <Shell>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            <p className="text-xs font-bold uppercase tracking-wider text-blue-400">
              RAG Intelligence & Documentation
            </p>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Knowledge Base & Document Center
          </h1>
          <p className="text-xs text-slate-400">
            Ingest PDFs, TXT, and Markdown to semantically ground the Dealership AI Copilot
          </p>
        </div>

        {isStaff && (
          <button onClick={() => setShowUploadModal(true)} className="btn-primary">
            <Upload className="h-4 w-4" />
            <span>Upload Document</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Left 2 Cols: Ingested Documents List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white">Ingested Dealership Documents</h2>
            <span className="text-xs text-slate-400 font-mono">{documents.length} Indexed Files</span>
          </div>

          <div className="erp-table-container">
            <table className="erp-table">
              <thead>
                <tr>
                  <th>Document Name</th>
                  <th>Brand Scope</th>
                  <th>Format</th>
                  <th>Chunks</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <div className="flex items-center gap-2.5">
                        <div className="h-8 w-8 rounded bg-blue-500/10 flex items-center justify-center text-blue-400 flex-shrink-0">
                          <FileText className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="font-bold text-white text-xs">{doc.title}</div>
                          <div className="text-[10px] text-slate-500">
                            Indexed {new Date(doc.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-neutral">{doc.brand_name || "All Brands"}</span>
                    </td>
                    <td>
                      <span className="font-mono text-[11px] text-slate-400 uppercase">
                        {doc.mime_type.split("/")[1] || "PDF"}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-success">{doc.chunk_count} Chunks</span>
                    </td>
                    <td>
                      {isStaff && (
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="text-slate-500 hover:text-rose-400 transition-colors p-1"
                          title="Delete Document"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right 1 Col: Semantic Search Test Bench */}
        <div className="space-y-4">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-400" />
            Semantic Retrieval Test Bench
          </h2>

          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4 text-xs">
            <p className="text-slate-400 leading-relaxed">
              Verify RAG semantic matching across indexed document chunks for the AI Copilot:
            </p>

            <form onSubmit={handleSemanticSearch} className="space-y-3">
              <input
                type="text"
                placeholder="e.g. What are the warranty terms for Toyota?"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 outline-none focus:border-purple-500"
              />
              <button
                type="submit"
                disabled={searching || !searchQuery.trim()}
                className="btn-primary w-full justify-center bg-purple-600 hover:bg-purple-700 text-xs py-2 disabled:opacity-40"
              >
                {searching ? "Running Embedding Search..." : "Probe Semantic Chunks"}
              </button>
            </form>

            {searchResults.length > 0 && (
              <div className="space-y-3 pt-3 border-t border-slate-800">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Retrieved Passages ({searchResults.length}):
                </span>
                {searchResults.map((r, i) => (
                  <div key={i} className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold text-purple-300 truncate max-w-[200px]">
                        {r.source}
                      </span>
                      <span className="badge badge-success text-[10px]">
                        Score: {(r.score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed italic">
                      "{r.content}"
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="p-5 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Ingest Knowledge Document</h3>
                <p className="text-xs text-slate-400">Chunked and vector indexed for AI Assistant grounding</p>
              </div>
              <button onClick={() => setShowUploadModal(false)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleUpload} className="p-5 space-y-4 text-xs">
              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Document Title</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 2024 Apex Motors Service & Warranty Policy.pdf"
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Brand Scope</label>
                <select
                  value={docBrand}
                  onChange={(e) => setDocBrand(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-white"
                >
                  <option value="all">Global / All Dealership Brands</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="border-2 border-dashed border-slate-700 rounded-xl p-6 text-center bg-slate-950/50">
                <Upload className="h-8 w-8 text-slate-500 mx-auto mb-2" />
                <p className="text-xs text-slate-300 font-semibold">Drop PDF, Markdown, or TXT file here</p>
                <p className="text-[11px] text-slate-500 mt-1">Supports up to 10MB per document</p>
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end gap-2">
                <button type="button" onClick={() => setShowUploadModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Index Document
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}
