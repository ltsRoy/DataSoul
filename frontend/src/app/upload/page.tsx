"use client";

import { useState, useCallback, useRef, Suspense } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Upload, FileSpreadsheet, FileText, X, CheckCircle2,
  Activity, ArrowLeft, Sparkles, Database, ChevronRight,
  AlertCircle, Loader2, FileUp, Table
} from "lucide-react";
import { uploadFile, loadDemo, type UploadResponse } from "../api";
import { useSession } from "../useSession";

/* ─── Sample datasets for demo ─── */
const SAMPLE_DATASETS = [
  {
    id: "retail",
    name: "Retail Sales Dataset",
    rows: "~5,000",
    cols: 12,
    sector: "Retail & E-Commerce",
    description: "Orders, products, customers, revenue with common retail data issues (missing values, duplicates, outliers, inconsistent casing)",
  },
];

/* ─── File type config ─── */
const ACCEPTED_TYPES: Record<string, { ext: string; color: string; icon: typeof FileSpreadsheet }> = {
  "text/csv": { ext: "CSV", color: "#22c55e", icon: FileSpreadsheet },
  "application/vnd.ms-excel": { ext: "XLS", color: "#f59e0b", icon: Table },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": { ext: "XLSX", color: "#3b82f6", icon: Table },
};

/* ─── Animated variants ─── */
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] as const }
  })
};

function UploadPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDemo = searchParams.get("demo") === "true";
  const { setSession } = useSession();
  
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadStep, setUploadStep] = useState(0); // 0=idle, 1=uploading, 2=profiling, 3=done
  const [isUploading, setIsUploading] = useState(false);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  }, []);

  const handleFile = async (f: File) => {
    setFile(f);
    setError(null);
    setIsUploading(true);
    setUploadStep(1);

    try {
      // Real upload to backend
      setUploadStep(1); // uploading
      const result = await uploadFile(f);
      setUploadResult(result);
      setUploadStep(2); // profiling
      
      // Store session
      setSession(result.session_id, result.filename);
      
      // Brief pause for UX
      await new Promise(r => setTimeout(r, 800));
      setUploadStep(3);
      setUploadComplete(true);
      setIsUploading(false);

      // Redirect to health page
      setTimeout(() => {
        router.push(`/health?session=${result.session_id}`);
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Is the backend running on localhost:8000?");
      setIsUploading(false);
      setUploadStep(0);
    }
  };

  const handleDemoSelect = async (id: string) => {
    setError(null);
    setFile(new File(["demo"], `${id}_demo.csv`, { type: "text/csv" }));
    setIsUploading(true);
    setUploadStep(1);

    try {
      const result = await loadDemo(id);
      setUploadResult(result);
      setUploadStep(2);

      setSession(result.session_id, result.filename);

      await new Promise(r => setTimeout(r, 800));
      setUploadStep(3);
      setUploadComplete(true);
      setIsUploading(false);

      setTimeout(() => {
        router.push(`/health?session=${result.session_id}`);
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load demo. Is the backend running on localhost:8000?");
      setIsUploading(false);
      setUploadStep(0);
      setFile(null);
    }
  };

  const uploadProgress = uploadStep === 0 ? 0 : uploadStep === 1 ? 40 : uploadStep === 2 ? 75 : 100;

  return (
    <div className="min-h-screen pt-20 pb-12">
      {/* ─── Navbar ─── */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass" style={{ borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
              <Activity size={18} color="white" />
            </div>
            <span className="font-display font-bold text-lg">DataSoul</span>
          </a>
          <a href="/" className="btn-ghost text-sm flex items-center gap-2">
            <ArrowLeft size={16} />
            Back
          </a>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6">
        {/* ─── Header ─── */}
        <motion.div className="text-center mb-12" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <h1 className="font-display text-3xl md:text-5xl font-bold mb-3">
            {isDemo ? (
              <>Pick a <span className="gradient-text">Demo Dataset</span></>
            ) : (
              <>Upload Your <span className="gradient-text">Dataset</span></>
            )}
          </h1>
          <p className="text-[var(--text-secondary)] text-lg">
            {isDemo
              ? "Choose from pre-loaded datasets to explore DataSoul's capabilities"
              : "Drop your CSV or Excel file — DataSoul will do the rest"
            }
          </p>
        </motion.div>

        {/* ─── Error Banner ─── */}
        <AnimatePresence>
          {error && (
            <motion.div
              className="glass-card mb-6 flex items-start gap-3"
              style={{ background: "rgba(239,68,68,0.08)", borderColor: "rgba(239,68,68,0.2)" }}
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <AlertCircle size={18} className="text-[var(--critical)] mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-[var(--critical)]">Upload Failed</p>
                <p className="text-xs text-[var(--text-secondary)] mt-1">{error}</p>
              </div>
              <button onClick={() => setError(null)} className="ml-auto text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <X size={16} />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─── Demo Datasets ─── */}
        {isDemo && !file && (
          <motion.div className="grid gap-4 mb-8" initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.1 } } }}>
            {SAMPLE_DATASETS.map((d, i) => (
              <motion.button
                key={d.id}
                className="glass-card text-left w-full flex items-center gap-4 md:gap-6"
                style={{ cursor: "pointer" }}
                onClick={() => handleDemoSelect(d.id)}
                variants={fadeUp}
                custom={i}
                whileHover={{ scale: 1.01, borderColor: "rgba(99,102,241,0.3)" }}
                whileTap={{ scale: 0.99 }}
              >
                <div className="w-10 h-10 rounded-lg bg-[var(--primary-light)] text-[var(--primary)] flex items-center justify-center flex-shrink-0"><Database size={20} /></div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold">{d.name}</h3>
                    <span className="badge-info">{d.sector}</span>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] mb-2">{d.description}</p>
                  <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
                    <span>{d.rows} rows</span>
                    <span>{d.cols} columns</span>
                  </div>
                </div>
                <ChevronRight size={20} className="text-[var(--text-muted)]" />
              </motion.button>
            ))}
          </motion.div>
        )}

        {/* ─── Dropzone ─── */}
        {!isDemo && !file && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }}>
            <div
              className={`dropzone ${isDragging ? "active" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xls,.xlsx"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
              <motion.div animate={{ y: isDragging ? -10 : 0 }} transition={{ type: "spring", stiffness: 300 }}>
                <div className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6" style={{ background: "var(--primary-glow)", border: "1px solid rgba(99,102,241,0.2)" }}>
                  <FileUp size={36} className="text-[var(--primary)]" />
                </div>
                <h3 className="font-display font-semibold text-xl mb-2">
                  {isDragging ? "Drop it here!" : "Drag & drop your file here"}
                </h3>
                <p className="text-[var(--text-secondary)] text-sm mb-4">or click to browse</p>
                <div className="flex items-center justify-center gap-3">
                  {Object.values(ACCEPTED_TYPES).map((t, i) => (
                    <span key={i} className="px-3 py-1 rounded-full text-xs font-medium" style={{ background: `${t.color}15`, color: t.color, border: `1px solid ${t.color}30` }}>
                      .{t.ext.toLowerCase()}
                    </span>
                  ))}
                </div>
              </motion.div>
            </div>
            
            {/* Or use demo */}
            <div className="text-center mt-6">
              <a href="/upload?demo=true" className="text-sm text-[var(--primary)] hover:underline flex items-center justify-center gap-1">
                <Sparkles size={14} />
                Or try a demo dataset instead
              </a>
            </div>
          </motion.div>
        )}

        {/* ─── Upload Progress ─── */}
        <AnimatePresence>
          {file && (
            <motion.div
              className="glass-card mt-8"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <div className="flex items-center gap-4 mb-6">
                <div className="w-14 h-14 rounded-xl flex items-center justify-center" style={{ background: "var(--primary-glow)" }}>
                  <FileSpreadsheet size={28} className="text-[var(--primary)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold truncate">{uploadResult?.filename || file.name}</h3>
                  <p className="text-sm text-[var(--text-secondary)]">
                    {uploadResult
                      ? `${uploadResult.rows.toLocaleString()} rows × ${uploadResult.cols} columns • ${uploadResult.size_mb} MB`
                      : `${(file.size / 1024).toFixed(1)} KB`
                    }
                  </p>
                </div>
                {uploadComplete && (
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring" }}>
                    <CheckCircle2 size={28} className="text-[var(--success)]" />
                  </motion.div>
                )}
              </div>

              {/* Progress bar */}
              <div className="h-2 rounded-full overflow-hidden mb-3" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: uploadComplete ? "var(--success)" : "var(--gradient-primary)" }}
                  initial={{ width: 0 }}
                  animate={{ width: `${uploadProgress}%` }}
                  transition={{ ease: "easeOut", duration: 0.5 }}
                />
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-secondary)]">
                  {uploadComplete ? (
                    <span className="text-[var(--success)] font-medium flex items-center gap-1">
                      <CheckCircle2 size={14} /> Upload complete — redirecting to health report...
                    </span>
                  ) : isUploading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin" />
                      {uploadStep === 1 ? "Uploading to DataSoul..." : "Preparing dataset..."}
                    </span>
                  ) : "Ready"}
                </span>
                <span className="text-sm font-medium" style={{ color: uploadComplete ? "var(--success)" : "var(--primary)" }}>
                  {Math.round(uploadProgress)}%
                </span>
              </div>

              {/* Processing steps */}
              {(isUploading || uploadComplete) && (
                <motion.div className="mt-6 space-y-2" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
                  {[
                    { label: "Uploading file to DataSoul engine", done: uploadStep >= 2 },
                    { label: "Parsing file structure & detecting column types", done: uploadStep >= 2 },
                    { label: "Calculating statistics & quality metrics", done: uploadStep >= 3 },
                    { label: "Ready for profiling & threat detection", done: uploadStep >= 3 },
                  ].map((step, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      {step.done ? (
                        <CheckCircle2 size={14} className="text-[var(--success)]" />
                      ) : uploadStep > 0 ? (
                        <Loader2 size={14} className="text-[var(--primary)] animate-spin" />
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border" style={{ borderColor: "var(--glass-border)" }} />
                      )}
                      <span style={{ color: step.done ? "var(--success)" : "var(--text-muted)" }}>
                        {step.label}
                      </span>
                    </div>
                  ))}
                </motion.div>
              )}

              {/* Show columns after upload */}
              {uploadResult && uploadComplete && (
                <motion.div className="mt-6 pt-4" style={{ borderTop: "1px solid var(--glass-border)" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <p className="text-xs text-[var(--text-muted)] mb-2">Detected Columns:</p>
                  <div className="flex flex-wrap gap-1.5">
                    {uploadResult.columns.map((col, i) => (
                      <span key={i} className="text-xs px-2 py-1 rounded-md font-mono" style={{ background: "var(--glass-bg)", color: "var(--text-secondary)" }}>
                        {col}
                      </span>
                    ))}
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function UploadPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 size={32} className="animate-spin text-[var(--primary)]" /></div>}>
      <UploadPageContent />
    </Suspense>
  );
}
