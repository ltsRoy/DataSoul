"use client";

import { useState, useEffect, useMemo, useCallback, Suspense } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Activity, Shield, Eye, Brain, CheckCircle2, AlertTriangle,
  XCircle, ChevronDown, ChevronRight, ArrowRight, BarChart3,
  TrendingUp, TrendingDown, Minus, FileSpreadsheet, Layers,
  Lock, Clock, Target, Zap, PieChart, ArrowLeft, Info,
  ThumbsUp, ThumbsDown, Filter, Search, Sparkles, AlertCircle,
  MessageSquare, Loader2, RefreshCw
} from "lucide-react";
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  Cell, PieChart as RechartsPie, Pie
} from "recharts";
import {
  getProfile, getThreats, autoClean, chatWithData,
  analyzeCorrections, applyCorrections, getLLMStatus,
  type ProfileResponse, type ThreatsResponse, type Threat,
  type CorrectionAnalysis
} from "../api";
import { getSessionFromParams } from "../useSession";

/* ─── ANIMATION VARIANTS ─── */
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] as const }
  })
};

/* ─── SCORE RING COMPONENT ─── */
function ScoreRing({ score, size = 160, strokeWidth = 10 }: { score: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? "var(--success)" : score >= 60 ? "var(--warning)" : "var(--critical)";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="score-ring">
        <circle className="bg" cx={size / 2} cy={size / 2} r={radius} strokeWidth={strokeWidth} />
        <motion.circle
          cx={size / 2} cy={size / 2} r={radius}
          strokeWidth={strokeWidth}
          stroke={color}
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: [0.4, 0, 0.2, 1], delay: 0.3 }}
          style={{ filter: `drop-shadow(0 0 8px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="font-display text-4xl font-bold"
          style={{ color }}
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.5, duration: 0.5, type: "spring" }}
        >
          {score}
        </motion.span>
        <span className="text-xs text-[var(--text-muted)] mt-1">/ 100</span>
      </div>
    </div>
  );
}

/* ─── HEARTBEAT COMPONENT ─── */
function HeartbeatMonitor({ score }: { score: number }) {
  const isCritical = score < 60;
  const color = score >= 80 ? "var(--success)" : score >= 60 ? "var(--warning)" : "var(--critical)";

  return (
    <motion.div
      className={`flex items-center gap-3 ${isCritical ? "heartbeat-critical" : "heartbeat"}`}
      style={{ color }}
    >
      <Activity size={24} />
      <div className="flex-1">
        <div className="h-8 relative overflow-hidden rounded-lg" style={{ background: `${color}10` }}>
          <motion.svg
            viewBox="0 0 200 40"
            className="absolute inset-0 w-full h-full"
            style={{ fill: "none", stroke: color, strokeWidth: 2 }}
          >
            <motion.path
              d={isCritical
                ? "M0,20 L20,20 L25,5 L30,35 L35,10 L40,30 L45,15 L50,25 L55,20 L75,20 L80,8 L85,32 L90,5 L95,35 L100,20 L120,20 L125,5 L130,35 L135,10 L140,30 L145,20 L165,20 L170,8 L175,32 L180,12 L185,28 L190,20 L200,20"
                : "M0,20 L30,20 L35,20 L40,10 L45,30 L50,15 L55,20 L80,20 L85,20 L90,10 L95,30 L100,15 L105,20 L130,20 L135,20 L140,10 L145,30 L150,15 L155,20 L180,20 L185,10 L190,30 L195,20 L200,20"
              }
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 2, ease: "easeInOut" }}
            />
          </motion.svg>
        </div>
      </div>
    </motion.div>
  );
}

/* ─── LOADING SKELETON ─── */
function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[var(--glass-bg)] ${className}`} />;
}

/* ─── THREAT CARD COMPONENT ─── */
function ThreatCard({ threat, index, onApprove }: { threat: Threat; index: number; onApprove?: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [decision, setDecision] = useState<"approved" | "rejected" | null>(null);

  const severityConfig = {
    critical: { color: "#ef4444", bg: "rgba(239,68,68,0.06)", border: "rgba(239,68,68,0.15)", badge: "badge-critical", icon: XCircle },
    warning: { color: "#f59e0b", bg: "rgba(245,158,11,0.06)", border: "rgba(245,158,11,0.15)", badge: "badge-warning", icon: AlertTriangle },
    low: { color: "#22c55e", bg: "rgba(34,197,94,0.06)", border: "rgba(34,197,94,0.15)", badge: "badge-success", icon: Info },
  };
  const cfg = severityConfig[threat.severity];

  if (decision === "approved") {
    return (
      <motion.div className="glass-card opacity-60" layout custom={index} variants={fadeUp} initial="hidden" animate="visible">
        <div className="flex items-center gap-2 text-[var(--success)]">
          <CheckCircle2 size={16} />
          <span className="text-sm font-medium">Action approved — will be applied during transformation</span>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      className="glass-card cursor-pointer"
      style={{ background: cfg.bg, borderColor: cfg.border }}
      onClick={() => setExpanded(!expanded)}
      layout
      custom={index}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      whileHover={{ scale: 1.005 }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <cfg.icon size={16} style={{ color: cfg.color }} />
          <span className={cfg.badge}>{threat.severity.toUpperCase()}</span>
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--glass-bg)", color: "var(--text-muted)" }}>{threat.category}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium" style={{ color: cfg.color }}>{threat.confidence}%</span>
          <motion.div animate={{ rotate: expanded ? 180 : 0 }}>
            <ChevronDown size={16} className="text-[var(--text-muted)]" />
          </motion.div>
        </div>
      </div>

      <h4 className="font-semibold text-sm mb-1">{threat.title}</h4>
      <p className="text-xs text-[var(--text-muted)]">Column: {threat.column}</p>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <div className="mt-4 pt-4" style={{ borderTop: `1px solid ${cfg.border}` }}>
              <p className="text-sm text-[var(--text-secondary)] mb-4">{threat.impact}</p>
              <div className="mb-4">
                <p className="text-xs font-medium text-[var(--text-muted)] mb-2 uppercase tracking-wider">Recommended Actions</p>
                <ul className="space-y-1.5">
                  {threat.actions.map((action, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]">
                      <ChevronRight size={14} className="mt-0.5 flex-shrink-0" style={{ color: cfg.color }} />
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex gap-3 mt-2">
                <button
                  className="flex items-center gap-2 text-sm px-5 py-2.5 rounded-lg font-bold transition-all hover:scale-105 shadow-lg"
                  style={{ background: "var(--success)", color: "white", border: "none" }}
                  onClick={(e) => { e.stopPropagation(); setDecision("approved"); onApprove?.(); }}
                >
                  <ThumbsUp size={16} /> Approve Fix
                </button>
                <button
                  className="flex items-center gap-2 text-sm px-5 py-2.5 rounded-lg font-medium transition-all hover:bg-white/5"
                  style={{ background: "var(--glass-bg)", color: "var(--text-primary)", border: "1px solid var(--glass-border)" }}
                  onClick={(e) => { e.stopPropagation(); setDecision("rejected"); }}
                >
                  <ThumbsDown size={16} /> Dismiss
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN HEALTH PAGE
   ═══════════════════════════════════════════════════════════════ */

function HealthPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [threats, setThreats] = useState<ThreatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isAutoCleaning, setIsAutoCleaning] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatAnswer, setChatAnswer] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);

  // AI Corrector State
  const [aiCorrections, setAiCorrections] = useState<CorrectionAnalysis | null>(null);
  const [aiCorrectorLoading, setAiCorrectorLoading] = useState(false);
  const [aiCorrectorError, setAiCorrectorError] = useState<string | null>(null);
  const [aiCorrectionsOpen, setAiCorrectionsOpen] = useState(false);
  const [selectedFixes, setSelectedFixes] = useState<Set<string>>(new Set());

  // Get session ID from URL or sessionStorage
  useEffect(() => {
    const id = getSessionFromParams(searchParams);
    if (id) {
      setSessionId(id);
    } else {
      setError("No session found. Please upload a dataset first.");
      setLoading(false);
    }
  }, [searchParams]);

  const refreshHealthData = useCallback(async (currentSessionId: string) => {
    const profileData = await getProfile(currentSessionId);
    setProfile(profileData);
    const threatsData = await getThreats(currentSessionId);
    setThreats(threatsData);
  }, []);

  // Fetch profile and threats
  useEffect(() => {
    if (!sessionId) return;
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        await refreshHealthData(sessionId!);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch data. Is the backend running?");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [sessionId, refreshHealthData]);

  // Filter threats
  const filteredThreats = useMemo(() => {
    if (!threats) return [];
    return threats.threats.filter(t => {
      if (severityFilter !== "all" && t.severity !== severityFilter) return false;
      if (searchQuery && !t.title.toLowerCase().includes(searchQuery.toLowerCase()) && !t.column.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });
  }, [threats, severityFilter, searchQuery]);

  // Auto-clean handler
  const handleAutoClean = async () => {
    if (!sessionId) return;
    setIsAutoCleaning(true);
    setError(null);
    try {
      await autoClean(sessionId);
      await refreshHealthData(sessionId);
    } catch (err) {
      setError("Auto-clean failed: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setIsAutoCleaning(false);
    }
  };

  // Chat handler
  const handleChat = async () => {
    if (!sessionId || !chatQuestion.trim()) return;
    setChatLoading(true);
    setChatAnswer(null);
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      const res = await chatWithData(sessionId, chatQuestion);
      clearTimeout(timeout);
      setChatAnswer(res.answer);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("abort") || msg.includes("timeout")) {
        setChatAnswer("Request timed out — Ollama may still be loading the model. Try again in a moment.");
      } else if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        setChatAnswer("Cannot reach the backend. Make sure it's running on localhost:8000.");
      } else {
        setChatAnswer("Couldn't get an answer right now. If you're using Ollama, make sure it's running (`ollama serve`). Pattern-matched questions like 'what's missing?' work without Ollama.");
      }
    } finally {
      setChatLoading(false);
    }
  };

  // AI Corrector handlers
  const handleAnalyze = async () => {
    if (!sessionId) return;
    
    // Automatically scroll to top so the user sees the panel expanding
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    setAiCorrectionsOpen(true);
    setAiCorrectorLoading(true);
    setAiCorrectorError(null);
    setAiCorrections(null);
    try {
      const status = await getLLMStatus();
      if (!status.available) {
        setAiCorrectionsOpen(false);
        setAiCorrectorError("Data cleaning engine offline. Please ensure the backend and Ollama are running properly.");
        return;
      }
      const res = await analyzeCorrections(sessionId);
      setAiCorrections(res);
      // Auto-select all LLM suggestions by default
      const toSelect = new Set<string>();
      res.category_merges.forEach((m: any, i: number) => toSelect.add(`merge_${i}`));
      res.corrections.forEach((c: any, i: number) => toSelect.add(`corr_${i}`));
      setSelectedFixes(toSelect);
    } catch (err) {
      console.error("Analysis failed:", err);
      setAiCorrectionsOpen(false);
      setAiCorrectorError(err instanceof Error ? err.message : "Correction scan failed. Check the backend and local Ollama service.");
    } finally {
      setAiCorrectorLoading(false);
    }
  };

  const handleApplyFixes = async () => {
    if (!sessionId || !aiCorrections) return;
    
    // Apply all corrections (no manual selection — all are auto-approved)
    const approved: {column: string; old_value: string; new_value: string}[] = [];
    
    aiCorrections.category_merges.forEach((m) => {
      approved.push({ column: m.column, old_value: m.old_value, new_value: m.new_value });
    });
    
    aiCorrections.corrections.forEach((c) => {
      approved.push({ column: c.column, old_value: c.old_value, new_value: c.new_value });
    });
    
    setIsAutoCleaning(true);
    setAiCorrectionsOpen(false);
    setError(null);
    try {
      if (approved.length > 0) {
        await applyCorrections(sessionId, approved);
      }
      
      // Then run auto-clean to fix the deterministic stuff (encoding, formats, type issues)
      await autoClean(sessionId);
      
      await refreshHealthData(sessionId);
      setAiCorrections(null);
    } catch (err) {
      setError("Failed to apply AI fixes: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setIsAutoCleaning(false);
    }
  };


  // Derived data
  const healthScore = profile?.quality_score?.overall ?? 0;
  const grade = profile?.quality_score?.grade ?? "N/A";
  const radarData = profile?.quality_score?.dimensions
    ? Object.entries(profile.quality_score.dimensions).map(([key, dim]) => ({
        dimension: key.charAt(0).toUpperCase() + key.slice(1),
        score: dim.score,
        fullMark: 100,
      }))
    : [];

  const missingChartData = profile?.missing_summary?.by_column
    ?.slice(0, 8)
    .map(c => ({
      name: c.column,
      missing: c.missing_pct,
      fill: c.missing_pct > 20 ? "#ef4444" : c.missing_pct > 5 ? "#f59e0b" : "#22c55e",
    })) ?? [];

  const criticalCount = threats?.critical ?? 0;
  const warningCount = threats?.warning ?? 0;
  const lowCount = threats?.low ?? 0;

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen pt-20 pb-12">
        <nav className="fixed top-0 left-0 right-0 z-50 glass" style={{ borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}>
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center">
            <a href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
                <Activity size={18} color="white" />
              </div>
              <span className="font-display font-bold text-lg">DataSoul</span>
            </a>
          </div>
        </nav>
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex items-center justify-center py-24 gap-3">
            <Loader2 size={24} className="animate-spin text-[var(--primary)]" />
            <span className="text-[var(--text-secondary)]">Profiling your dataset & scanning for threats...</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
            <Skeleton className="h-48" />
          </div>
          <Skeleton className="h-64 mb-8" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  // Error state
  if (error && !profile) {
    return (
      <div className="min-h-screen pt-20 pb-12">
        <nav className="fixed top-0 left-0 right-0 z-50 glass" style={{ borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}>
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center">
            <a href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
                <Activity size={18} color="white" />
              </div>
              <span className="font-display font-bold text-lg">DataSoul</span>
            </a>
          </div>
        </nav>
        <div className="max-w-2xl mx-auto px-6 text-center py-24">
          <AlertCircle size={48} className="text-[var(--critical)] mx-auto mb-4" />
          <h2 className="font-display text-2xl font-bold mb-2">Something went wrong</h2>
          <p className="text-[var(--text-secondary)] mb-6">{error}</p>
          <a href="/upload" className="btn-primary inline-flex items-center gap-2">
            <ArrowLeft size={16} /> Upload a Dataset
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-20 pb-12">
      {/* ─── Navbar ─── */}
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
            <span className="text-sm text-[var(--text-secondary)]">Health Report</span>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-ghost text-sm flex items-center gap-2" onClick={() => setChatOpen(!chatOpen)}>
              <MessageSquare size={16} />
              Query Data
            </button>
            <a href="/upload" className="btn-ghost text-sm flex items-center gap-2">
              <ArrowLeft size={16} />
              Upload New
            </a>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6">
        {/* ═══ Header ═══ */}
        <motion.div className="mb-8" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-3 mb-2">
            <FileSpreadsheet size={20} className="text-[var(--primary)]" />
            <h1 className="font-display text-2xl font-bold">{profile?.filename ?? "Dataset"}</h1>
            {profile?.sector && (
              <span className="badge-info">{profile.sector.sector_name}</span>
            )}
          </div>
          <p className="text-sm text-[var(--text-secondary)]">
            {profile?.overview?.rows?.toLocaleString()} rows × {profile?.overview?.cols} columns • {profile?.overview?.memory_mb} MB
          </p>
        </motion.div>

        {/* ═══ Chat Panel ═══ */}
        <AnimatePresence>
          {chatOpen && (
            <motion.div
              className="glass-card mb-8"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <h3 className="font-display text-sm font-semibold mb-3 flex items-center gap-2">
                <Brain size={16} className="text-[var(--accent)]" />
                Data Query
              </h3>
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  value={chatQuestion}
                  onChange={(e) => setChatQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleChat()}
                  placeholder="e.g., What's missing in my data? Are there duplicates?"
                  className="flex-1 text-sm px-4 py-2.5 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                />
                <button onClick={handleChat} disabled={chatLoading} className="btn-primary text-sm px-4">
                  {chatLoading ? <Loader2 size={16} className="animate-spin" /> : "Ask"}
                </button>
              </div>
              {chatAnswer && (
                <motion.div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap p-4 rounded-lg" style={{ background: "var(--glass-bg)" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  {chatAnswer}
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ═══ AI Corrector Panel ═══ */}
        <AnimatePresence>
          {aiCorrectionsOpen && (
            <motion.div
              className="glass-card mb-8 border border-[var(--primary)]"
              style={{ boxShadow: "0 0 20px rgba(99,102,241,0.15)" }}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <h3 className="font-display text-lg font-bold mb-4 flex items-center gap-2">
                <Brain size={20} className="text-[var(--primary)]" />
                Data Correction Analysis
                {aiCorrectorLoading && <Loader2 size={16} className="animate-spin text-[var(--primary)] ml-2" />}
              </h3>

              {aiCorrectorLoading ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <div className="relative mb-4">
                    <Activity size={32} className="text-[var(--primary)]" />
                    <motion.div className="absolute inset-0 border-2 border-[var(--primary)] rounded-full" animate={{ scale: [1, 1.5, 1], opacity: [1, 0, 1] }} transition={{ duration: 1.5, repeat: Infinity }} />
                  </div>
                  <p className="text-sm text-[var(--text-secondary)]">Analyzing data for correction candidates...</p>
                </div>
              ) : aiCorrections ? (
                <div className="space-y-6">
                  {/* Category Merges */}
                  {aiCorrections.category_merges.length > 0 && (
                    <div>
                      <h4 className="text-base font-bold flex items-center gap-2 mb-3">
                        <Layers size={18} className="text-[var(--warning)]" />
                        Category Merges ({aiCorrections.category_merges.length})
                      </h4>
                      <div className="space-y-2">
                        {aiCorrections.category_merges.map((merge, i) => (
                          <div key={i} className="flex items-start gap-3 p-4 rounded-xl border border-[var(--primary)] bg-[rgba(99,102,241,0.05)] shadow-sm">
                            <CheckCircle2 size={16} className="text-[var(--primary)] mt-0.5 flex-shrink-0" />
                            <div className="flex-1">
                              <div className="text-base font-medium">Merge <span className="text-[var(--critical)] font-bold">&quot;{merge.old_value}&quot;</span> into <span className="text-[var(--success)] font-bold">&quot;{merge.new_value}&quot;</span></div>
                              <div className="text-sm text-[var(--text-secondary)] mt-2 p-2.5 rounded-lg bg-black/20 border border-white/5"><span className="text-[var(--primary)] font-bold">Reason:</span> {merge.reason}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Value Corrections */}
                  {aiCorrections.corrections.length > 0 && (
                    <div className="mt-4">
                      <h4 className="text-base font-bold flex items-center gap-2 mb-3">
                        <Zap size={18} className="text-[var(--accent)]" />
                        Value Corrections ({aiCorrections.corrections.length})
                      </h4>
                      <div className="space-y-2">
                        {aiCorrections.corrections.map((corr, i) => (
                          <div key={i} className="flex items-start gap-3 p-4 rounded-xl border border-[var(--primary)] bg-[rgba(99,102,241,0.05)] shadow-sm">
                            <CheckCircle2 size={16} className="text-[var(--primary)] mt-0.5 flex-shrink-0" />
                            <div className="flex-1">
                              <div className="text-base font-medium">Fix <span className="text-[var(--critical)] font-bold">&quot;{corr.old_value}&quot;</span> → <span className="text-[var(--success)] font-bold">&quot;{corr.new_value}&quot;</span></div>
                              <div className="text-sm text-[var(--text-secondary)] mt-2 p-2.5 rounded-lg bg-black/20 border border-white/5"><span className="text-[var(--primary)] font-bold">Reason:</span> {corr.reason}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {aiCorrections.category_merges.length === 0 && aiCorrections.corrections.length === 0 && (
                    <div className="text-center py-6 text-[var(--text-secondary)] text-sm">
                      No category merges or typo corrections were found. Type, encoding, numeric, and missing-value fixes will still be applied automatically.
                    </div>
                  )}

                  <div className="flex justify-end pt-6 border-t border-[var(--glass-border)] mt-6">
                    <button 
                      className="flex items-center gap-2 px-8 py-4 rounded-xl font-bold text-white shadow-lg transition-all hover:scale-105 active:scale-95" 
                      style={{ background: "var(--gradient-primary)" }}
                      onClick={handleApplyFixes}
                    >
                      <Sparkles size={20} /> Apply Selected Fixes & Clean
                    </button>
                  </div>
                </div>
              ) : null}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ═══ Top Stats Row ═══ */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Health Score Ring */}
          <motion.div className="glass-card flex items-center gap-6" custom={0} variants={fadeUp} initial="hidden" animate="visible">
            <ScoreRing score={Math.round(healthScore)} size={130} strokeWidth={8} />
            <div>
              <h3 className="font-display text-lg font-semibold mb-1">Data Health</h3>
              <p className="text-sm text-[var(--text-secondary)] mb-2">Grade: <span className="font-bold" style={{ color: healthScore >= 80 ? "var(--success)" : healthScore >= 60 ? "var(--warning)" : "var(--critical)" }}>{grade}</span></p>
              <HeartbeatMonitor score={Math.round(healthScore)} />
            </div>
          </motion.div>

          {/* Radar Chart */}
          <motion.div className="glass-card" custom={1} variants={fadeUp} initial="hidden" animate="visible">
            <h3 className="font-display text-sm font-semibold mb-1 flex items-center gap-2">
              <Target size={16} className="text-[var(--accent)]" />
              Quality Dimensions
            </h3>
            {radarData.length > 0 ? (
              <ResponsiveContainer width="100%" height={180}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="var(--glass-border)" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fill: "var(--text-muted)", fontSize: 10 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                  <Radar dataKey="score" stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.15} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[180px] flex items-center justify-center text-sm text-[var(--text-muted)]">No dimension data</div>
            )}
          </motion.div>

          {/* Threat Count Summary */}
          <motion.div className="glass-card flex flex-col justify-between" custom={2} variants={fadeUp} initial="hidden" animate="visible">
            <h3 className="font-display text-sm font-semibold mb-4 flex items-center gap-2">
              <Shield size={16} className="text-[var(--critical)]" />
              Threat Summary
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: "var(--critical)" }} />
                  <span className="text-sm">Critical</span>
                </div>
                <span className="font-display font-bold text-lg text-[var(--critical)]">{criticalCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: "var(--warning)" }} />
                  <span className="text-sm">Medium</span>
                </div>
                <span className="font-display font-bold text-lg text-[var(--warning)]">{warningCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ background: "var(--success)" }} />
                  <span className="text-sm">Low</span>
                </div>
                <span className="font-display font-bold text-lg text-[var(--success)]">{lowCount}</span>
              </div>
            </div>
            {threats && threats.total > 0 && (
              <div className="mt-4 pt-3" style={{ borderTop: "1px solid var(--glass-border)" }}>
                <div className="flex gap-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--glass-bg)" }}>
                  <div className="rounded-full" style={{ width: `${(criticalCount / threats.total) * 100}%`, background: "var(--critical)" }} />
                  <div className="rounded-full" style={{ width: `${(warningCount / threats.total) * 100}%`, background: "var(--warning)" }} />
                  <div className="rounded-full" style={{ width: `${(lowCount / threats.total) * 100}%`, background: "var(--success)" }} />
                </div>
              </div>
            )}
          </motion.div>
        </div>

        {/* ═══ Missing Values Chart ═══ */}
        {missingChartData.length > 0 && (
          <motion.div className="glass-card mb-8" custom={3} variants={fadeUp} initial="hidden" animate="visible">
            <h3 className="font-display text-sm font-semibold mb-4 flex items-center gap-2">
              <BarChart3 size={16} className="text-[var(--primary)]" />
              Missing Values by Column
            </h3>
            <ResponsiveContainer width="100%" height={Math.max(150, missingChartData.length * 35)}>
              <BarChart data={missingChartData} layout="vertical" margin={{ left: 100 }}>
                <XAxis type="number" domain={[0, Math.max(25, ...missingChartData.map(d => d.missing) )]} tick={{ fill: "var(--text-muted)", fontSize: 11 }} tickFormatter={(v) => `${v}%`} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--glass-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "12px" }}
                  formatter={(value: unknown) => [`${value}%`, "Missing"]}
                />
                <Bar dataKey="missing" radius={[0, 6, 6, 0]} barSize={18}>
                  {missingChartData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* ═══ Column Profile Table ═══ */}
        {profile?.columns && (
          <motion.div className="glass-card mb-8 overflow-x-auto" custom={4} variants={fadeUp} initial="hidden" animate="visible">
            <h3 className="font-display text-sm font-semibold mb-4 flex items-center gap-2">
              <Layers size={16} className="text-[var(--accent)]" />
              Column Profile ({profile.columns.length} columns)
            </h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[var(--text-muted)] text-xs uppercase tracking-wider">
                  <th className="text-left py-2 px-3">Column</th>
                  <th className="text-left py-2 px-3">Type</th>
                  <th className="text-right py-2 px-3">Missing</th>
                  <th className="text-right py-2 px-3">Missing %</th>
                  <th className="text-right py-2 px-3">Unique</th>
                  <th className="text-left py-2 px-3">Cardinality</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map((col, i) => (
                  <tr key={i} className="border-t" style={{ borderColor: "var(--glass-border)" }}>
                    <td className="py-2.5 px-3 font-mono text-xs font-medium">{col.name}</td>
                    <td className="py-2.5 px-3 text-xs text-[var(--text-muted)]">{col.dtype}</td>
                    <td className="py-2.5 px-3 text-right font-mono text-xs">{col.missing.toLocaleString()}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span className={`font-mono text-xs font-medium ${col.missing_pct > 10 ? "text-[var(--critical)]" : col.missing_pct > 0 ? "text-[var(--warning)]" : "text-[var(--success)]"}`}>
                        {col.missing_pct}%
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right font-mono text-xs">{col.unique.toLocaleString()}</td>
                    <td className="py-2.5 px-3">
                      <span className="text-xs px-2 py-0.5 rounded-full" style={{
                        background: col.cardinality === "ID" ? "var(--info-bg)" : col.cardinality === "High" ? "rgba(139,92,246,0.1)" : "var(--glass-bg)",
                        color: col.cardinality === "ID" ? "#60a5fa" : col.cardinality === "High" ? "#a78bfa" : "var(--text-muted)"
                      }}>
                        {col.cardinality}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </motion.div>
        )}

        {/* ═══ Threat Cards ═══ */}
        {threats && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-4">
              <h2 className="font-display text-xl font-bold flex items-center gap-2">
                <Shield size={20} className="text-[var(--critical)]" />
                Threat Center ({threats.total} threats)
              </h2>
              <div className="flex items-center gap-3">
                {/* Search */}
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                  <input
                    type="text"
                    placeholder="Search threats..."
                    className="text-sm pl-9 pr-4 py-2 rounded-lg bg-[var(--glass-bg)] border border-[var(--glass-border)] text-[var(--text-primary)] outline-none focus:border-[var(--primary)] transition-colors"
                    style={{ width: "200px" }}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                {/* Filter */}
                <div className="flex gap-1 glass rounded-lg p-1">
                  {["all", "critical", "warning", "low"].map(sev => (
                    <button
                      key={sev}
                      className="text-xs px-3 py-1.5 rounded-md font-medium transition-all"
                      style={{
                        background: severityFilter === sev ? "var(--primary-glow)" : "transparent",
                        color: severityFilter === sev ? "var(--primary-light)" : "var(--text-muted)",
                        border: severityFilter === sev ? "1px solid rgba(99,102,241,0.3)" : "1px solid transparent"
                      }}
                      onClick={() => setSeverityFilter(sev)}
                    >
                      {sev === "all" ? "All" : sev.charAt(0).toUpperCase() + sev.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {filteredThreats.map((threat, i) => (
                <ThreatCard key={threat.id} threat={threat} index={i} />
              ))}
              {filteredThreats.length === 0 && (
                <div className="glass-card text-center py-12">
                  <CheckCircle2 size={32} className="text-[var(--success)] mx-auto mb-3" />
                  <p className="text-[var(--text-secondary)]">No threats match your filter</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ Action Bar ═══ */}
        <motion.div
          className="glass-card flex flex-col md:flex-row items-center justify-between gap-4 sticky bottom-4 z-40"
          style={{ background: "var(--bg-card)", boxShadow: "0 -4px 30px rgba(0,0,0,0.3)" }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1 }}
        >
          <div>
            <p className="font-semibold text-sm">Ready to transform?</p>
            <p className="text-xs text-[var(--text-secondary)]">Approve critical threats above, then proceed to insights. Or auto-fix all safe issues.</p>
          </div>
          <div className="flex gap-3">
            <button
              className="text-sm flex items-center gap-2 px-6 py-3 rounded-xl font-bold transition-all shadow-lg hover:scale-105 hover:brightness-110"
              onClick={handleAnalyze}
              disabled={isAutoCleaning || aiCorrectorLoading}
              style={{ background: "var(--gradient-primary)", border: "none", color: "white", boxShadow: "0 4px 20px rgba(99,102,241,0.4)" }}
            >
              <Brain size={18} />
              Scan with Ollama
            </button>
            <button
              className="btn-ghost text-sm flex items-center gap-2"
              onClick={handleAutoClean}
              disabled={isAutoCleaning}
            >
              {isAutoCleaning ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {isAutoCleaning ? "Cleaning..." : "Auto-Fix All Safe"}
            </button>
            <a href={`/insights?session=${sessionId}`} className="btn-primary text-sm flex items-center gap-2">
              <Zap size={16} />
              View Insights
              <ArrowRight size={16} />
            </a>
          </div>
        </motion.div>
      </div>

      {/* ═══ Error Modal ═══ */}
      <AnimatePresence>
        {aiCorrectorError && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="glass-card max-w-md w-full relative"
              style={{ borderTop: "4px solid var(--critical)" }}
            >
              <div className="flex flex-col items-center text-center py-4">
                <div className="w-16 h-16 rounded-full bg-[rgba(239,68,68,0.1)] flex items-center justify-center mb-4 text-[var(--critical)]">
                  <AlertTriangle size={32} />
                </div>
                <h3 className="font-display text-xl font-bold mb-2">Engine Unavailable</h3>
                <p className="text-[var(--text-secondary)] mb-6 text-sm px-2">
                  {aiCorrectorError}
                </p>
                <button
                  className="btn-primary w-full py-2.5 font-bold"
                  style={{ background: "var(--critical)", color: "white", border: "none" }}
                  onClick={() => setAiCorrectorError(null)}
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function HealthPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-[var(--primary)]" />
      </div>
    }>
      <HealthPageContent />
    </Suspense>
  );
}
