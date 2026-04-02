// frontend/src/ChatWithCitations.jsx

import { useState, useRef } from "react";

/**
 * ChatWithCitations
 * Renders ALITA's answer as formatted markdown + clickable citation chips.
 * Clicking a chip opens a PDF viewer modal at the exact source page.
 *
 * Props:
 *   answer  — string (markdown from ALITA)
 *   sources — array: [{ document_name, page_number, source_text, file_url }]
 */
export default function ChatWithCitations({ answer, sources = [] }) {
  const [activePdf, setActivePdf] = useState(null);
  const [tooltipIdx, setTooltipIdx] = useState(null);

  // Deduplicate sources — same page + same doc only shown once
  const uniqueSources = sources.filter(
    (s, i, arr) =>
      arr.findIndex(
        (x) => x.page_number === s.page_number && x.document_name === s.document_name
      ) === i
  );

  const DJANGO_BASE = "http://localhost:8000";

  function getPdfUrl(source) {
    if (!source.file_url) return null;
    const base = source.file_url.startsWith("http")
      ? source.file_url
      : `${DJANGO_BASE}${source.file_url}`;
    // #page=N tells the browser PDF viewer to jump to that page
    return `${base}#page=${source.page_number}`;
  }

  function openViewer(source) {
    setActivePdf({
      url: getPdfUrl(source),
      page_number: source.page_number,
      source_text: source.source_text,
      document_name: source.document_name,
    });
  }

  function closeViewer() {
    setActivePdf(null);
  }

  // ── Markdown renderer ──────────────────────────────────────────────────
  function renderMarkdown(text) {
    if (!text) return null;
    return text.split("\n").map((line, i) => {
      if (line.startsWith("# "))
        return <h1 key={i} style={styles.h1}>{line.slice(2)}</h1>;
      if (line.startsWith("## "))
        return <h2 key={i} style={styles.h2}>{line.slice(3)}</h2>;
      if (line.startsWith("### "))
        return <h3 key={i} style={styles.h3}>{line.slice(4)}</h3>;
      if (line.startsWith("- ") || line.startsWith("* "))
        return <li key={i} style={styles.li}>{renderInline(line.slice(2))}</li>;
      if (line.trim() === "") return <br key={i} />;
      return <p key={i} style={styles.p}>{renderInline(line)}</p>;
    });
  }

  function renderInline(text) {
    return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**"))
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("*") && part.endsWith("*"))
        return <em key={i}>{part.slice(1, -1)}</em>;
      return part;
    });
  }

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div style={styles.wrapper}>

      {/* Answer */}
      <div style={styles.answerBox}>
        {renderMarkdown(answer)}
      </div>

      {/* Citation chips */}
      {uniqueSources.length > 0 && (
        <div style={styles.citationSection}>
          <span style={styles.citationLabel}>📎 Sources</span>
          <div style={styles.chipRow}>
            {uniqueSources.map((source, idx) => (
              <div key={idx} style={styles.chipWrapper}>
                <button
                  style={styles.chip}
                  onClick={() => openViewer(source)}
                  onMouseEnter={() => setTooltipIdx(idx)}
                  onMouseLeave={() => setTooltipIdx(null)}
                >
                  📄 {source.document_name
                    ? source.document_name.replace(/\.[^/.]+$/, "")
                    : "Document"}
                  {source.page_number > 0 && (
                    <span style={styles.pageTag}>p.{source.page_number}</span>
                  )}
                </button>

                {/* Hover tooltip — extracted text preview */}
                {tooltipIdx === idx && source.source_text && (
                  <div style={styles.tooltip}>
                    <div style={styles.tooltipHeader}>
                      Page {source.page_number} — {source.document_name}
                    </div>
                    <div style={styles.tooltipText}>
                      "{source.source_text.slice(0, 200)}
                      {source.source_text.length > 200 ? "..." : ""}"
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PDF Viewer Modal */}
      {activePdf && (
        <div style={styles.modalOverlay} onClick={closeViewer}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>

            {/* Header */}
            <div style={styles.modalHeader}>
              <div style={styles.modalTitle}>
                <span>📄 {activePdf.document_name}</span>
                {activePdf.page_number > 0 && (
                  <span style={styles.modalPageBadge}>
                    Page {activePdf.page_number}
                  </span>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {/* Open in new tab — reliable fallback */}
                {activePdf.url && (
                  <a
                    href={activePdf.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.openTabBtn}
                  >
                    ↗ Open in tab
                  </a>
                )}
                <button style={styles.closeBtn} onClick={closeViewer}>✕</button>
              </div>
            </div>

            {/* Extracted text highlight strip */}
            {activePdf.source_text && (
              <div style={styles.highlightStrip}>
                <span style={styles.highlightIcon}>🔍 Extracted text:</span>
                <span style={styles.highlightText}>
                  "{activePdf.source_text.slice(0, 250)}
                  {activePdf.source_text.length > 250 ? "..." : ""}"
                </span>
              </div>
            )}

            {/* PDF Viewer
                Uses <object> instead of <iframe> — browsers handle it more
                permissively for cross-origin files (localhost:8000 vs :3000).
                Falls back to a friendly "Open in tab" button if still blocked. */}
            {activePdf.url ? (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
                <object
                  data={activePdf.url}
                  type="application/pdf"
                  style={styles.pdfObject}
                >
                  {/* This content only shows if <object> fails to render */}
                  <div style={styles.fallback}>
                    <p style={styles.fallbackText}>
                      Your browser blocked the inline PDF preview.
                    </p>
                    <p style={styles.fallbackSub}>
                      The extracted text above shows exactly what was used to generate this answer.
                    </p>
                    <a
                      href={activePdf.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={styles.fallbackBtn}
                    >
                      🔗 Open PDF in New Tab — Page {activePdf.page_number}
                    </a>
                  </div>
                </object>
              </div>
            ) : (
              <div style={styles.noUrl}>
                PDF URL not available for this document.
              </div>
            )}

          </div>
        </div>
      )}
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    color: "#e2e8f0",
  },
  answerBox: {
    background: "#1e293b",
    borderRadius: "12px",
    padding: "20px 24px",
    lineHeight: "1.7",
    fontSize: "14px",
    border: "1px solid #334155",
  },
  h1: { fontSize: "20px", fontWeight: 700, color: "#f8fafc", margin: "0 0 12px 0" },
  h2: { fontSize: "17px", fontWeight: 600, color: "#94a3b8", margin: "16px 0 8px 0", borderBottom: "1px solid #334155", paddingBottom: "4px" },
  h3: { fontSize: "15px", fontWeight: 600, color: "#cbd5e1", margin: "12px 0 6px 0" },
  p:  { margin: "6px 0", color: "#cbd5e1" },
  li: { margin: "4px 0 4px 16px", color: "#cbd5e1", listStyleType: "disc" },

  citationSection: { display: "flex", flexDirection: "column", gap: "8px" },
  citationLabel: { fontSize: "12px", color: "#64748b", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" },
  chipRow: { display: "flex", flexWrap: "wrap", gap: "8px" },
  chipWrapper: { position: "relative" },
  chip: {
    display: "flex", alignItems: "center", gap: "6px",
    padding: "6px 12px", background: "#0f172a",
    border: "1px solid #334155", borderRadius: "20px",
    color: "#94a3b8", fontSize: "12px", cursor: "pointer",
    transition: "all 0.15s ease", whiteSpace: "nowrap",
  },
  pageTag: { background: "#6366f1", color: "#fff", borderRadius: "10px", padding: "1px 7px", fontSize: "11px", fontWeight: 600 },

  tooltip: {
    position: "absolute", bottom: "calc(100% + 8px)", left: "0",
    width: "300px", background: "#1e293b", border: "1px solid #475569",
    borderRadius: "10px", padding: "12px", zIndex: 1000,
    boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
  },
  tooltipHeader: { fontSize: "11px", fontWeight: 700, color: "#6366f1", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.05em" },
  tooltipText: { fontSize: "12px", color: "#94a3b8", lineHeight: "1.5", fontStyle: "italic" },

  modalOverlay: {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
    zIndex: 2000, display: "flex", alignItems: "center",
    justifyContent: "center", padding: "24px",
  },
  modal: {
    width: "min(900px, 95vw)", height: "85vh",
    background: "#0f172a", borderRadius: "16px",
    border: "1px solid #334155", display: "flex",
    flexDirection: "column", overflow: "hidden",
    boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
  },
  modalHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "16px 20px", borderBottom: "1px solid #1e293b", background: "#0f172a",
    flexShrink: 0,
  },
  modalTitle: { display: "flex", alignItems: "center", gap: "10px", fontSize: "14px", fontWeight: 600, color: "#e2e8f0" },
  modalPageBadge: { background: "#6366f1", color: "#fff", borderRadius: "8px", padding: "2px 10px", fontSize: "12px", fontWeight: 700 },
  openTabBtn: {
    padding: "5px 12px", background: "#1e293b", border: "1px solid #334155",
    borderRadius: "8px", color: "#94a3b8", fontSize: "12px",
    textDecoration: "none", fontWeight: 500,
  },
  closeBtn: { background: "transparent", border: "none", color: "#64748b", fontSize: "18px", cursor: "pointer", padding: "4px 8px", borderRadius: "6px" },

  highlightStrip: {
    padding: "10px 20px", background: "#1e293b",
    borderBottom: "1px solid #334155", fontSize: "12px",
    display: "flex", gap: "8px", alignItems: "flex-start",
    flexWrap: "wrap", flexShrink: 0,
  },
  highlightIcon: { color: "#f59e0b", fontWeight: 600, whiteSpace: "nowrap" },
  highlightText: { color: "#94a3b8", fontStyle: "italic", lineHeight: "1.5" },

  // <object> fills remaining modal height
  pdfObject: {
    flex: 1,
    width: "100%",
    height: "100%",
    border: "none",
    background: "#fff",
    display: "block",
  },

  // Shown inside <object> when browser blocks PDF rendering
  fallback: {
    flex: 1, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    padding: "40px", textAlign: "center", gap: "12px",
    height: "400px",
  },
  fallbackText: { color: "#e2e8f0", fontSize: "15px", fontWeight: 600, margin: 0 },
  fallbackSub: { color: "#64748b", fontSize: "13px", margin: 0, maxWidth: "400px", lineHeight: "1.6" },
  fallbackBtn: {
    marginTop: "8px", padding: "10px 24px",
    background: "#6366f1", color: "#fff",
    borderRadius: "10px", textDecoration: "none",
    fontWeight: 600, fontSize: "14px",
  },

  noUrl: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b", fontSize: "14px" },
};