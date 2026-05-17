"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import {
  Activity, ChevronRight, Sparkles, ArrowLeft, BookOpen,
  Download, FileText, Presentation, ArrowRight, Copy,
  CheckCircle2, TrendingUp, TrendingDown, AlertTriangle,
  Target, Lightbulb, Clock, DollarSign, Loader2, AlertCircle,
  Shield, BarChart3, Brain, Zap, Cpu
} from "lucide-react";
import { getStory, getProfile, getLLMStatus, streamStory, type ProfileResponse, type LLMStatusResponse } from "../api";
import { getSessionFromParams } from "../useSession";

/* ─── TYPEWRITER HOOK ─── */
function useTypewriter(text: string, speed: number = 15) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!text) return;
    setDisplayed("");
    setDone(false);
    let i = 0;
    const interval = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.substring(0, i + 1));
        i++;
      } else {
        setDone(true);
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return { displayed, done };
}

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] as const }
  })
};

function StoryPageContent() {
  const searchParams = useSearchParams();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [narrative, setNarrative] = useState<string>("");
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [llmStatus, setLlmStatus] = useState<LLMStatusResponse | null>(null);
  const [llmPowered, setLlmPowered] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamDone, setStreamDone] = useState(false);
  const narrativeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = getSessionFromParams(searchParams);
    if (id) {
      setSessionId(id);
    } else {
      setError("No session found. Upload a dataset first.");
      setLoading(false);
    }
  }, [searchParams]);

  // Check LLM status on mount
  useEffect(() => {
    getLLMStatus()
      .then(setLlmStatus)
      .catch(() => setLlmStatus({ available: false, model: null, preferred_model: "llama3.2", engine: "ollama" }));
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    async function fetchData() {
      setLoading(true);
      try {
        // Always get profile first
        const profileData = await getProfile(sessionId!);
        setProfile(profileData);

        // Check if LLM is available for streaming
        const status = await getLLMStatus().catch(() => null);
        setLlmStatus(status);

        if (status?.available) {
          // Use streaming mode — LLM generates token by token
          setLoading(false);
          setIsStreaming(true);
          setStreamDone(false);
          setNarrative("");
          setLlmPowered(true);

          let currentNarrative = "";

          await streamStory(
            sessionId!,
            (token) => {
              currentNarrative += token;
              setNarrative(currentNarrative);
            },
            () => {
              setIsStreaming(false);
              setStreamDone(true);
              if (currentNarrative.length === 0) {
                 // Fallback if empty stream
                 setLlmPowered(false);
                 getStory(sessionId!).then((d) => {
                   setNarrative(d.story);
                   setLlmPowered(d.llm_powered || false);
                 }).catch((e) => setError(e.message));
              }
            },
            (err) => {
              console.warn("[Story] Stream failed, falling back:", err);
              setIsStreaming(false);
              setLlmPowered(false);
              // Fall back to non-streaming
              getStory(sessionId!).then((d) => {
                setNarrative(d.story);
                setStreamDone(true);
                setLlmPowered(d.llm_powered || false);
              }).catch((e) => setError(e.message));
            },
          );
        } else {
          // Template mode — get full story at once
          const storyData = await getStory(sessionId!);
          setNarrative(storyData.story);
          setLlmPowered(storyData.llm_powered || false);
          setStreamDone(true);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to generate story.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [sessionId]);

  // Typewriter only used for template mode (non-streaming)
  const useStreamMode = llmPowered && !streamDone && isStreaming;
  const { displayed: typewriterText, done: typewriterDone } = useTypewriter(
    !llmPowered ? narrative : "",
    8
  );

  // Determine what text to show
  const displayedText = llmPowered ? narrative : typewriterText;
  const isDone = llmPowered ? streamDone : typewriterDone;

  // Auto scroll
  useEffect(() => {
    if (narrativeRef.current && !isDone) {
      narrativeRef.current.scrollTop = narrativeRef.current.scrollHeight;
    }
  }, [displayedText, isDone]);

  const handleCopy = () => {
    navigator.clipboard.writeText(narrative);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Derive highlights from profile
  const highlights = profile ? [
    {
      icon: Target,
      value: `${Math.round(profile.quality_score.overall)}/100`,
      label: "Data Health Score",
      color: profile.quality_score.overall >= 80 ? "#22c55e" : profile.quality_score.overall >= 60 ? "#f59e0b" : "#ef4444",
    },
    {
      icon: BarChart3,
      value: `${profile.overview.rows.toLocaleString()}`,
      label: "Total Records",
      color: "#6366f1",
    },
    {
      icon: Shield,
      value: `${profile.overview.cols}`,
      label: "Dimensions",
      color: "#06b6d4",
    },
    {
      icon: Clock,
      value: `${Math.max(3, Math.round(profile.overview.rows / 500))} hrs`,
      label: "Analyst Time Saved",
      color: "#f59e0b",
    },
  ] : [];

  /* Simple markdown renderer */
  const renderMarkdown = (text: string) => {
    const lines = text.split("\n");
    return lines.map((line, i) => {
      if (line.startsWith("## ")) return <h2 key={i} className="font-display text-2xl font-bold mb-4 mt-2 gradient-text">{line.replace("## ", "")}</h2>;
      if (line.startsWith("### ")) return <h3 key={i} className="font-display text-lg font-semibold mt-8 mb-3">{line.replace("### ", "")}</h3>;
      if (line.startsWith("---")) return <hr key={i} className="my-6" style={{ borderColor: "var(--glass-border)" }} />;
      if (line.startsWith("> ")) return <blockquote key={i} className="border-l-2 pl-4 my-4 text-sm italic" style={{ borderColor: "var(--primary)", color: "var(--text-secondary)" }}>{line.replace("> ", "")}</blockquote>;
      if (line.match(/^\d\.\s/)) return <div key={i} className="flex gap-2 my-1.5 text-sm text-[var(--text-secondary)]"><span className="text-[var(--primary)] font-bold flex-shrink-0">{line.match(/^\d\./)![0]}</span><span dangerouslySetInnerHTML={{ __html: line.replace(/^\d\.\s/, "").replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--text-primary)]">$1</strong>') }} /></div>;
      if (line.startsWith("- ")) return <div key={i} className="flex gap-2 my-1 text-sm text-[var(--text-secondary)]"><span className="text-[var(--accent)]">•</span><span dangerouslySetInnerHTML={{ __html: line.replace("- ", "").replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--text-primary)]">$1</strong>') }} /></div>;
      if (line.startsWith("| ")) {
        const cells = line.split("|").filter(c => c.trim());
        if (cells.every(c => c.trim().match(/^[-]+$/))) return null; // separator row
        const isHeader = i > 0 && text.split("\n")[i + 1]?.match(/^\|[-|]+\|$/);
        return (
          <div key={i} className={`flex gap-2 text-xs font-mono py-1 ${isHeader ? "font-bold text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}`}>
            {cells.map((cell, j) => (
              <span key={j} className="flex-1 truncate">{cell.trim()}</span>
            ))}
          </div>
        );
      }
      if (line.trim() === "") return <div key={i} className="h-2" />;
      const formatted = line.replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--text-primary)] font-semibold">$1</strong>');
      return <p key={i} className="text-sm text-[var(--text-secondary)] leading-relaxed my-1" dangerouslySetInnerHTML={{ __html: formatted }} />;
    });
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
        <div className="flex flex-col items-center justify-center py-32 gap-4">
          <div className="relative">
            <Loader2 size={32} className="animate-spin text-[var(--primary)]" />
            {llmStatus?.available && (
              <motion.div
                className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-[var(--success)]"
                animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
            )}
          </div>
          <span className="text-[var(--text-secondary)]">
            {llmStatus?.available
              ? `Generating with Ollama (${llmStatus.model || "llama3.2"})...`
              : "Generating your executive narrative..."}
          </span>
          {llmStatus?.available && (
            <span className="text-xs text-[var(--text-muted)] flex items-center gap-1">
              <Brain size={12} /> Powered by local Ollama AI + RAG knowledge base
            </span>
          )}
        </div>
      </div>
    );
  }

  if (error) {
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
        <div className="max-w-2xl mx-auto px-6 text-center py-24">
          <AlertCircle size={48} className="text-[var(--critical)] mx-auto mb-4" />
          <h2 className="font-display text-2xl font-bold mb-2">Story generation failed</h2>
          <p className="text-[var(--text-secondary)] mb-6">{error}</p>
          <a href="/upload" className="btn-primary inline-flex items-center gap-2"><ArrowLeft size={16} /> Upload a Dataset</a>
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
            <span className="text-sm text-[var(--text-secondary)]">Story Mode</span>
          </div>
          <div className="flex items-center gap-3">
            <a href={`/insights?session=${sessionId}`} className="btn-ghost text-sm flex items-center gap-2">
              <ArrowLeft size={16} /> Insights
            </a>
            <a href={`/export?session=${sessionId}`} className="btn-primary text-sm flex items-center gap-2">
              <Download size={16} /> Export
            </a>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6">
        {/* Header */}
        <motion.div className="text-center mb-8" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="inline-flex items-center gap-2 glass px-4 py-2 rounded-full mb-4">
            {llmPowered ? (
              <>
                <Brain size={14} className="text-[var(--success)]" />
                <span className="text-xs font-medium text-[var(--text-secondary)]">
                  Powered by Ollama ({llmStatus?.model || "llama3.2"}) + RAG Knowledge Base
                </span>
                <span className="w-2 h-2 rounded-full bg-[var(--success)] animate-pulse" />
              </>
            ) : (
              <>
                <Sparkles size={14} className="text-[var(--primary)]" />
                <span className="text-xs font-medium text-[var(--text-secondary)]">AI-Generated Executive Narrative</span>
              </>
            )}
          </div>
          <h1 className="font-display text-3xl md:text-4xl font-bold mb-2">
            <span className="gradient-text">Story Mode</span>
          </h1>
          <p className="text-[var(--text-secondary)]">
            {llmPowered
              ? "Your data, narrated by a local Ollama AI brain with RAG-augmented intelligence"
              : "Your data, transformed into boardroom-ready intelligence"}
          </p>
        </motion.div>

        {/* Highlight Cards */}
        {highlights.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {highlights.map((h, i) => (
              <motion.div key={i} className="glass-card text-center py-4" custom={i} variants={fadeUp} initial="hidden" animate="visible">
                <h.icon size={20} className="mx-auto mb-2" style={{ color: h.color }} />
                <div className="font-display text-xl font-bold" style={{ color: h.color }}>{h.value}</div>
                <div className="text-xs text-[var(--text-muted)]">{h.label}</div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Narrative Container */}
        <motion.div
          className="glass-card relative"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-6 pb-4" style={{ borderBottom: "1px solid var(--glass-border)" }}>
            <div className="flex items-center gap-2">
              <BookOpen size={16} className="text-[var(--primary)]" />
              <span className="text-sm font-medium">Executive Narrative</span>
              {isStreaming && (
                <span className="text-xs text-[var(--accent)] flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
                  {llmPowered ? "Ollama Streaming..." : "Generating..."}
                </span>
              )}
              {!isStreaming && !isDone && narrative && (
                <span className="text-xs text-[var(--accent)] flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse" />
                  Generating...
                </span>
              )}
              {isDone && <span className="text-xs text-[var(--success)] flex items-center gap-1"><CheckCircle2 size={12} /> Complete</span>}
            </div>
            <div className="flex items-center gap-2">
              {llmPowered && (
                <span className="text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ background: "rgba(34,197,94,0.1)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.2)" }}>
                  <Cpu size={10} className="inline mr-1" />
                  {llmStatus?.model?.split(":")[0] || "LLM"}
                </span>
              )}
              <button onClick={handleCopy} className="btn-ghost text-xs px-3 py-1.5 flex items-center gap-1">
                {copied ? <><CheckCircle2 size={12} /> Copied!</> : <><Copy size={12} /> Copy</>}
              </button>
            </div>
          </div>

          {/* Narrative Content */}
          <div ref={narrativeRef} className="max-h-[70vh] overflow-y-auto pr-2">
            {renderMarkdown(displayedText)}
            {!isDone && narrative && <span className="typing-cursor" />}
          </div>
        </motion.div>

        {/* Export CTA */}
        {isDone && (
          <motion.div
            className="glass-card flex flex-col md:flex-row items-center justify-between gap-4 mt-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <div>
              <p className="font-semibold text-sm">Ready to present?</p>
              <p className="text-xs text-[var(--text-secondary)]">Export your cleaned dataset, full narrative, and Colab notebook.</p>
            </div>
            <div className="flex gap-3">
              <a href={`/export?session=${sessionId}`} className="btn-primary text-sm flex items-center gap-2">
                <Download size={16} /> Export Center <ArrowRight size={16} />
              </a>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default function StoryPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 size={32} className="animate-spin text-[var(--primary)]" /></div>}>
      <StoryPageContent />
    </Suspense>
  );
}
