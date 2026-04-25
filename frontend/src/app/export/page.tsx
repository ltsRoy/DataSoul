"use client";

import { useState, useEffect, Suspense } from "react";
import { motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import {
  Activity, ChevronRight, Download, FileSpreadsheet, FileText,
  Presentation, Code2, FileCode2, Package, CheckCircle2,
  ArrowLeft, Loader2, Archive, Sparkles, AlertCircle
} from "lucide-react";
import { exportDataset, getDownloadUrl, getProfile, exportColabNotebook, type ProfileResponse } from "../api";
import { getSessionFromParams } from "../useSession";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] as const }
  })
};

function ExportPageContent() {
  const searchParams = useSearchParams();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const id = getSessionFromParams(searchParams);
    if (id) {
      setSessionId(id);
    } else {
      setError("No session found.");
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!sessionId) return;
    async function fetchProfile() {
      try {
        const data = await getProfile(sessionId!);
        setProfile(data);
      } catch {
        // Non-critical, we can still show exports
      } finally {
        setLoading(false);
      }
    }
    fetchProfile();
  }, [sessionId]);

  const rows = profile?.overview?.rows ?? 0;
  const cols = profile?.overview?.cols ?? 0;
  const healthScore = Math.round(profile?.quality_score?.overall ?? 0);

  const EXPORTS = [
    {
      id: "csv",
      title: "Clean Dataset",
      format: "CSV",
      icon: FileSpreadsheet,
      color: "#22c55e",
      description: "Cleaned dataset ready for analysis — all transformations applied",
      size: `${rows.toLocaleString()} rows`,
      rows: `${cols} columns`,
      available: true,
    },
    {
      id: "json",
      title: "JSON Dataset",
      format: "JSON",
      icon: Code2,
      color: "#f59e0b",
      description: "Dataset exported as structured JSON for API integrations",
      size: `${rows.toLocaleString()} records`,
      rows: `${cols} fields`,
      available: true,
    },
    {
      id: "xlsx",
      title: "Excel Workbook",
      format: "XLSX",
      icon: FileSpreadsheet,
      color: "#3b82f6",
      description: "Full Excel workbook with formatted cells for spreadsheet analysis",
      size: `${rows.toLocaleString()} rows`,
      rows: `${cols} columns`,
      available: true,
    },
    {
      id: "colab-notebook",
      title: "Google Colab Notebook",
      format: ".ipynb",
      icon: FileCode2,
      color: "#F9AB00",
      description: "Ready-to-run notebook with EDA, visualizations, and ML pipeline starter — used by IIT/IISc/IISER researchers",
      size: `${rows.toLocaleString()} rows embedded`,
      rows: "Open in Colab",
      available: true,
    },
    {
      id: "huggingface",
      title: "Hugging Face Hub",
      format: "HF",
      icon: Package,
      color: "#FF9D00",
      description: "Push to Hugging Face Hub with auto-generated dataset card — used by AI4Bharat, IIIT Hyderabad, Jio AI",
      size: "Requires HF Token",
      rows: "",
      available: false,
    },
    {
      id: "google-sheets",
      title: "Google Sheets",
      format: "Sheet",
      icon: FileSpreadsheet,
      color: "#34a853",
      description: "Push cleaned data to a new Google Sheet — widely used across Indian research labs",
      size: "Requires Credentials",
      rows: "",
      available: false,
    },
    {
      id: "pptx",
      title: "Executive Deck",
      format: "PPTX",
      icon: Presentation,
      color: "#6366f1",
      description: "Boardroom-ready presentation with KPIs, charts, and action plan",
      size: "Coming Soon",
      rows: "",
      available: false,
    },
    {
      id: "pdf",
      title: "Audit Report",
      format: "PDF",
      icon: FileText,
      color: "#ef4444",
      description: "Full data quality report with audit trail and compliance documentation",
      size: "Coming Soon",
      rows: "",
      available: false,
    },
  ];

  const handleDownload = async (id: string) => {
    if (!sessionId) return;
    setDownloading(id);
    setError(null);

    try {
      if (id === "colab-notebook") {
        // Colab notebook export
        const result = await exportColabNotebook(sessionId);
        const fullUrl = `http://localhost:8000${result.download_url}`;
        const link = document.createElement("a");
        link.href = fullUrl;
        link.download = result.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        // Standard format export (csv/json/xlsx)
        const format = id as "csv" | "json" | "xlsx";
        const result = await exportDataset(sessionId, format);
        const fullUrl = `http://localhost:8000${result.download_url}`;
        const link = document.createElement("a");
        link.href = fullUrl;
        link.download = `datasoul_export.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }

      setDownloaded(prev => new Set([...prev, id]));
    } catch (err) {
      setError(`Failed to export ${id.toUpperCase()}: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setDownloading(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen pt-20 pb-12">
        <nav className="fixed top-0 left-0 right-0 z-50 glass" style={{ borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}>
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center">
            <a href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}><Activity size={18} color="white" /></div>
              <span className="font-display font-bold text-lg">DataSoul</span>
            </a>
          </div>
        </nav>
        <div className="flex items-center justify-center py-32 gap-3">
          <Loader2 size={24} className="animate-spin text-[var(--primary)]" />
          <span className="text-[var(--text-secondary)]">Preparing exports...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-20 pb-12">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass" style={{ borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <a href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
                <Activity size={18} color="white" />
              </div>
              <span className="font-display font-bold text-lg">DataSoul</span>
            </a>
            <ChevronRight size={16} className="text-[var(--text-muted)]" />
            <span className="text-sm text-[var(--text-secondary)]">Export Center</span>
          </div>
          <a href={`/story?session=${sessionId}`} className="btn-ghost text-sm flex items-center gap-2">
            <ArrowLeft size={16} /> Back to Story
          </a>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6">
        {/* Header */}
        <motion.div className="text-center mb-12" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="inline-flex items-center gap-2 glass px-4 py-2 rounded-full mb-4">
            <Sparkles size={14} className="text-[var(--primary)]" />
            <span className="text-xs font-medium text-[var(--text-secondary)]">Your data is clean, trusted, and ready</span>
          </div>
          <h1 className="font-display text-3xl md:text-4xl font-bold mb-2">
            <span className="gradient-text">Export Center</span>
          </h1>
          <p className="text-[var(--text-secondary)]">Download your cleaned data in any format</p>
        </motion.div>

        {/* Error */}
        {error && (
          <motion.div className="glass-card mb-6 flex items-start gap-3" style={{ borderColor: "rgba(239,68,68,0.2)" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <AlertCircle size={16} className="text-[var(--critical)] mt-0.5" />
            <p className="text-sm text-[var(--text-secondary)]">{error}</p>
          </motion.div>
        )}

        {/* Export Cards */}
        <div className="grid md:grid-cols-2 gap-4 mb-8">
          {EXPORTS.map((exp, i) => {
            const isDownloading = downloading === exp.id;
            const isDownloaded = downloaded.has(exp.id);
            
            return (
              <motion.div
                key={exp.id}
                className={`glass-card group ${!exp.available ? "opacity-50" : ""}`}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
              >
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-110" style={{ background: `${exp.color}12`, border: `1px solid ${exp.color}25` }}>
                    <exp.icon size={26} style={{ color: exp.color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-display font-semibold">{exp.title}</h3>
                      <span className="text-xs px-2 py-0.5 rounded-full font-mono font-medium" style={{ background: `${exp.color}15`, color: exp.color }}>
                        {exp.format}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] mb-3 leading-relaxed">{exp.description}</p>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                        <span>{exp.size}</span>
                        {exp.rows && <><span>•</span><span>{exp.rows}</span></>}
                      </div>
                      <button
                        className="flex items-center gap-1.5 text-xs px-4 py-2 rounded-lg font-medium transition-all"
                        style={{
                          background: isDownloaded ? "var(--success-bg)" : `${exp.color}15`,
                          color: isDownloaded ? "var(--success)" : exp.color,
                          border: `1px solid ${isDownloaded ? "rgba(34,197,94,0.3)" : `${exp.color}30`}`,
                          cursor: exp.available ? "pointer" : "not-allowed",
                        }}
                        onClick={() => exp.available && !isDownloading && !isDownloaded && handleDownload(exp.id)}
                        disabled={isDownloading || !exp.available}
                      >
                        {!exp.available ? (
                          <>Coming Soon</>
                        ) : isDownloading ? (
                          <><Loader2 size={12} className="animate-spin" /> Preparing...</>
                        ) : isDownloaded ? (
                          <><CheckCircle2 size={12} /> Downloaded</>
                        ) : (
                          <><Download size={12} /> Download</>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Summary */}
        <motion.div className="glass-card text-center py-8" custom={7} variants={fadeUp} initial="hidden" animate="visible">
          <CheckCircle2 size={40} className="text-[var(--success)] mx-auto mb-4" />
          <h3 className="font-display text-xl font-bold mb-2">DataSoul Pipeline Complete</h3>
          <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-4">
            Your dataset has been profiled, threats detected, insights generated, and narrative crafted. You&apos;re now working with trusted data.
          </p>
          <div className="flex items-center justify-center gap-6 text-sm">
            <div><span className="font-bold text-[var(--success)]">{healthScore}/100</span> <span className="text-[var(--text-muted)]">Health Score</span></div>
            <div><span className="font-bold text-[var(--primary)]">{rows.toLocaleString()}</span> <span className="text-[var(--text-muted)]">Records</span></div>
            <div><span className="font-bold text-[var(--accent)]">{cols}</span> <span className="text-[var(--text-muted)]">Dimensions</span></div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

export default function ExportPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 size={32} className="animate-spin text-[var(--primary)]" /></div>}>
      <ExportPageContent />
    </Suspense>
  );
}
