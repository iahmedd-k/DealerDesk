"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  Search,
  Upload,
  Trash2,
  X,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import Shell from "../components/Shell";
import { useAuth } from "../providers";
import { api } from "../api";
import type { Brand, KnowledgeDocument } from "../lib/types";

export default function KnowledgePage() {
  const { user, authReady, activeDealershipId } = useAuth();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showUploadModal, setShowUploadModal] = useState(false);

  const [docBrand, setDocBrand] = useState<number | "all">("all");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadBrandId, setUploadBrandId] = useState<number | "">("");
  const [uploading, setUploading] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<
    Array<{ content: string; score: number; source: string }>
  >([]);

  const isStaff = Boolean(user && user.role !== "customer");

  useEffect(() => {
    if (!authReady || !user) return;
    if (!activeDealershipId) {
      setLoading(false);
      setError("Select a dealership workspace to manage knowledge documents.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      api<KnowledgeDocument[]>(
        `/dealerships/${activeDealershipId}/knowledge/documents`,
      ),
      api<Brand[]>(`/dealerships/${activeDealershipId}/brands`),
    ])
      .then(([nextDocs, nextBrands]) => {
        if (cancelled) return;
        setDocuments(nextDocs);
        setBrands(nextBrands);
      })
      .catch((cause: unknown) => {
        if (!cancelled)
          setError(cause instanceof Error ? cause.message : "Could not load knowledge documents.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, user, activeDealershipId]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !selectedFile) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", selectedFile);
      if (uploadBrandId) {
        form.append("brand_id", String(uploadBrandId));
      }
      const created = await api<KnowledgeDocument>(
        `/dealerships/${activeDealershipId}/knowledge/documents`,
        { method: "POST", body: form },
      );
      setDocuments((current) => [created, ...current]);
      setSelectedFile(null);
      setUploadBrandId("");
      setShowUploadModal(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not upload document.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(doc: KnowledgeDocument) {
    if (!activeDealershipId || !window.confirm(`Delete "${doc.filename}"?`)) return;
    setError("");
    try {
      await api<void>(
        `/dealerships/${activeDealershipId}/knowledge/documents/${doc.id}`,
        { method: "DELETE" },
      );
      setDocuments((current) => current.filter((item) => item.id !== doc.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete document.");
    }
  }

  async function handleSemanticSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!activeDealershipId || !searchQuery.trim()) return;
    setSearching(true);
    setError("");
    try {
      const results = await api<
        Array<{
          content: string;
          score: number;
          filename: string;
          page_number: number | null;
          chunk_index: number;
        }>
      >(`/dealerships/${activeDealershipId}/knowledge/search`, {
        method: "POST",
        body: JSON.stringify({
          query: searchQuery.trim(),
          brand_id: docBrand === "all" ? null : Number(docBrand),
          limit: 5,
        }),
      });
      setSearchResults(
        results.map((result) => ({
          content: result.content,
          score: result.score,
          source: `${result.filename}${result.page_number ? ` (page ${result.page_number})` : ""}, chunk ${result.chunk_index + 1}`,
        })),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Knowledge search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <Shell>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-medium tracking-tight text-[#171717]">
            Knowledge Base & Document Center
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Ingest dealership policies, brochures, and warranty PDFs to ground the AI assistant
          </p>
        </div>

        {isStaff && (
          <button
            type="button"
            onClick={() => setShowUploadModal(true)}
            className="crm-btn-primary"
          >
            <Upload className="h-4 w-4" />
            Upload Document
          </button>
        )}
      </div>

      {error && (
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 cols: Indexed Documents */}
        <div className="lg:col-span-2 crm-card overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-blue-600" />
              <h2 className="text-sm font-medium text-[#171717]">
                Indexed Documents ({documents.length})
              </h2>
            </div>
          </div>

          {loading ? (
            <p className="p-8 text-center text-sm text-slate-500">
              Loading knowledge documents...
            </p>
          ) : documents.length === 0 ? (
            <div className="p-10 text-center">
              <FileText className="h-9 w-9 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-900">No documents indexed</p>
              <p className="text-xs text-slate-500 mt-1">
                Upload PDF, TXT, or Markdown files to build your dealership knowledge base.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="crm-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Brand</th>
                    <th>Chunks</th>
                    <th>Status</th>
                    {isStaff && <th className="text-right">Action</th>}
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => {
                    const brandName =
                      brands.find((b) => b.id === doc.brand_id)?.name || "All Brands";
                    return (
                      <tr key={doc.id}>
                        <td>
                          <div className="font-semibold text-slate-900 text-xs">
                            {doc.filename || doc.title || "Untitled"}
                          </div>
                          <div className="text-[11px] text-slate-500">
                            {(doc.media_type || doc.mime_type || "file").toUpperCase()} ·{" "}
                            {new Date(doc.created_at).toLocaleDateString()}
                          </div>
                        </td>
                        <td className="text-xs text-slate-600">{brandName}</td>
                        <td className="font-mono text-xs text-slate-700">{doc.chunk_count}</td>
                        <td>
                          <span
                            className={`crm-badge ${doc.status === "ready" || doc.status === "indexed"
                              ? "crm-badge-success"
                              : doc.status === "failed"
                                ? "crm-badge-danger"
                                : "crm-badge-warning"
                              }`}
                          >
                            {doc.status}
                          </span>
                        </td>
                        {isStaff && (
                          <td className="text-right">
                            <button
                              type="button"
                              onClick={() => handleDelete(doc)}
                              className="crm-btn-danger py-1 px-2.5 text-xs"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              Delete
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right col: Semantic Search Tester */}
        <div className="crm-card p-5 space-y-4">
          <div>
            <h2 className="text-sm font-medium text-[#171717]">Semantic Retrieval Test</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Verify what chunks the AI assistant retrieves for customer questions.
            </p>
          </div>

          <form onSubmit={handleSemanticSearch} className="space-y-3">
            <select
              value={docBrand}
              onChange={(e) =>
                setDocBrand(e.target.value === "all" ? "all" : Number(e.target.value))
              }
              className="crm-select"
            >
              <option value="all">All Brands</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ask a warranty or policy question..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="crm-input"
              />
              <button
                type="submit"
                disabled={searching || !searchQuery.trim()}
                className="crm-btn-primary shrink-0"
              >
                <Search className="h-4 w-4" />
              </button>
            </div>
          </form>

          <div className="space-y-2.5 pt-2">
            {searchResults.length === 0 ? (
              <p className="text-xs text-slate-500">
                Run a query to inspect matching document excerpts and similarity scores.
              </p>
            ) : (
              searchResults.map((res, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold text-blue-700 truncate">
                      {res.source}
                    </span>
                    <span className="crm-badge crm-badge-info">
                      {(res.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">{res.content}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="crm-modal-overlay">
          <div className="crm-modal max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-[#171717]">Upload Knowledge Document</h2>
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Document File (PDF, TXT, MD)
                </label>
                <input
                  type="file"
                  required
                  accept=".pdf,.txt,.md"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="text-xs text-slate-600 file:mr-3 file:rounded-lg file:border file:border-slate-200 file:bg-white file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-700 hover:file:bg-slate-50"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Brand Scope (Optional)
                </label>
                <select
                  value={uploadBrandId}
                  onChange={(e) =>
                    setUploadBrandId(e.target.value ? Number(e.target.value) : "")
                  }
                  className="crm-select"
                >
                  <option value="">General Dealership Knowledge</option>
                  {brands.map((brand) => (
                    <option key={brand.id} value={brand.id}>
                      {brand.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="crm-btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !selectedFile}
                  className="crm-btn-primary"
                >
                  {uploading ? "Indexing..." : "Upload & Index"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Shell>
  );
}
