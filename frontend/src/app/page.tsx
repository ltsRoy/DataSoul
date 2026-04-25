"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence, useScroll, useTransform } from "framer-motion";
import {
  Upload, Shield, Brain, BarChart3, FileText, Zap, ChevronRight,
  Database, AlertTriangle, CheckCircle2, TrendingUp, Lock,
  ArrowRight, Sparkles, Eye, Target, Activity, Clock, DollarSign,
  Layers, LineChart, PieChart, MousePointerClick, Star
} from "lucide-react";

/* ─────────────────────── ANIMATION VARIANTS ─────────────────────── */
const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.1, duration: 0.6, ease: [0.22, 1, 0.36, 1] as const }
  })
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: "easeOut" as const } }
};

/* ─────────────────────── ANIMATED COUNTER ─────────────────────── */
function AnimatedNumber({ value, suffix = "", prefix = "" }: { value: number; suffix?: string; prefix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        let start = 0;
        const duration = 2000;
        const startTime = performance.now();
        const animate = (now: number) => {
          const elapsed = now - startTime;
          const progress = Math.min(elapsed / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          setCount(Math.floor(eased * value));
          if (progress < 1) requestAnimationFrame(animate);
        };
        requestAnimationFrame(animate);
        observer.disconnect();
      }
    }, { threshold: 0.3 });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [value]);

  return <span ref={ref}>{prefix}{count.toLocaleString()}{suffix}</span>;
}

/* ─────────────────────── FLOATING PARTICLES ─────────────────────── */
function Particles() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {Array.from({ length: 30 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: Math.random() * 4 + 1,
            height: Math.random() * 4 + 1,
            background: i % 3 === 0 ? "rgba(99,102,241,0.4)" : i % 3 === 1 ? "rgba(6,182,212,0.3)" : "rgba(139,92,246,0.3)",
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
          }}
          animate={{
            y: [0, -30 - Math.random() * 40, 0],
            x: [0, Math.random() * 20 - 10, 0],
            opacity: [0.2, 0.6, 0.2],
          }}
          transition={{
            duration: 4 + Math.random() * 4,
            repeat: Infinity,
            delay: Math.random() * 3,
            ease: "easeInOut"
          }}
        />
      ))}
    </div>
  );
}

/* ─────────────────────── MOCK DATA FLOW VISUAL ─────────────────────── */
function DataFlowVisual() {
  const steps = [
    { icon: Upload, label: "Upload", color: "#6366f1" },
    { icon: Eye, label: "Profile", color: "#8b5cf6" },
    { icon: Shield, label: "Threats", color: "#ef4444" },
    { icon: MousePointerClick, label: "Review", color: "#f59e0b" },
    { icon: Zap, label: "Transform", color: "#06b6d4" },
    { icon: BarChart3, label: "Insights", color: "#22c55e" },
  ];

  return (
    <div className="flex items-center justify-center gap-2 md:gap-4 flex-wrap">
      {steps.map((step, i) => (
        <motion.div key={i} className="flex items-center gap-2 md:gap-4" custom={i} variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
          <motion.div
            className="flex flex-col items-center gap-2"
            whileHover={{ scale: 1.1, y: -5 }}
            transition={{ type: "spring", stiffness: 400 }}
          >
            <div className="w-12 h-12 md:w-14 md:h-14 rounded-xl flex items-center justify-center" style={{ background: `${step.color}15`, border: `1px solid ${step.color}30` }}>
              <step.icon size={22} style={{ color: step.color }} />
            </div>
            <span className="text-xs font-medium" style={{ color: step.color }}>{step.label}</span>
          </motion.div>
          {i < steps.length - 1 && (
            <motion.div
              animate={{ x: [0, 5, 0], opacity: [0.3, 0.7, 0.3] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
            >
              <ChevronRight size={16} className="text-[var(--text-muted)]" />
            </motion.div>
          )}
        </motion.div>
      ))}
    </div>
  );
}

/* ─────────────────────── THREAT DEMO CARD ─────────────────────── */
function ThreatDemoCard({ severity, title, impact, confidence, delay }: { severity: string; title: string; impact: string; confidence: number; delay: number }) {
  const colors = {
    critical: { bg: "rgba(239,68,68,0.08)", border: "rgba(239,68,68,0.2)", text: "#f87171", badge: "badge-critical" },
    warning: { bg: "rgba(245,158,11,0.08)", border: "rgba(245,158,11,0.2)", text: "#fbbf24", badge: "badge-warning" },
    low: { bg: "rgba(34,197,94,0.08)", border: "rgba(34,197,94,0.2)", text: "#4ade80", badge: "badge-success" },
  };
  const c = colors[severity as keyof typeof colors] || colors.low;

  return (
    <motion.div
      className="glass-card"
      style={{ background: c.bg, borderColor: c.border }}
      custom={delay}
      variants={fadeUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true }}
      whileHover={{ scale: 1.02 }}
    >
      <div className="flex items-start justify-between mb-3">
        <span className={c.badge}>{severity.toUpperCase()}</span>
        <span className="text-xs" style={{ color: c.text }}>{confidence}% confidence</span>
      </div>
      <h4 className="font-semibold text-sm mb-1" style={{ color: "var(--text-primary)" }}>{title}</h4>
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>{impact}</p>
      <div className="flex gap-2 mt-3">
        <button className="text-xs px-3 py-1.5 rounded-lg font-medium" style={{ background: `${c.text}20`, color: c.text }}>Fix Now</button>
        <button className="text-xs px-3 py-1.5 rounded-lg font-medium" style={{ background: "var(--glass-bg)", color: "var(--text-secondary)", border: "1px solid var(--glass-border)" }}>Review</button>
      </div>
    </motion.div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN LANDING PAGE
   ═══════════════════════════════════════════════════════════════ */

export default function LandingPage() {
  const [isDemoHovered, setIsDemoHovered] = useState(false);
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroOpacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);
  const heroY = useTransform(scrollYProgress, [0, 0.5], [0, -50]);

  const pillars = [
    { icon: Eye, title: "Auto-Profile", desc: "Detects types, missing values, outliers, skewness, cardinality, and 14+ quality dimensions instantly", color: "#6366f1" },
    { icon: Brain, title: "AI Strategy", desc: "Recommends imputation, encoding, scaling, and transforms with confidence scores and explanations", color: "#8b5cf6" },
    { icon: Shield, title: "Threat Center", desc: "Exposes data quality, ML, business, and privacy threats before they corrupt your decisions", color: "#ef4444" },
    { icon: MousePointerClick, title: "Human Control", desc: "Every critical decision requires your approval. Override AI, choose methods, set compliance modes", color: "#f59e0b" },
    { icon: FileText, title: "Full Audit Trail", desc: "Every action logged with timestamp, confidence, reason, and who approved it. Compliance-ready", color: "#06b6d4" },
    { icon: LineChart, title: "Story Mode", desc: "Converts cleaned data into executive narratives, KPIs, charts, and boardroom-ready presentations", color: "#22c55e" },
  ];

  const metrics = [
    { value: 120, suffix: "+", label: "AI Patterns", icon: Brain },
    { value: 9, suffix: "", label: "Business Sectors", icon: Layers },
    { value: 85, suffix: "%", label: "Time Saved", icon: Clock },
    { value: 30, suffix: "sec", label: "Profile Speed", icon: Zap },
  ];

  return (
    <div className="min-h-screen">
      {/* ═══ NAVIGATION ═══ */}
      <motion.nav
        className="fixed top-0 left-0 right-0 z-50 glass"
        style={{ borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}
        initial={{ y: -80 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
              <Activity size={18} color="white" />
            </div>
            <span className="font-display font-bold text-lg">DataSoul</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Features</a>
            <a href="#threats" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Threats</a>
            <a href="#pipeline" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Pipeline</a>
            <a href="#sectors" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Sectors</a>
          </div>
          <a href="/upload" className="btn-primary text-sm flex items-center gap-2">
            <Upload size={16} />
            Upload Dataset
          </a>
        </div>
      </motion.nav>

      {/* ═══ HERO SECTION ═══ */}
      <motion.section ref={heroRef} className="relative min-h-screen flex items-center justify-center pt-16" style={{ opacity: heroOpacity, y: heroY }}>
        <Particles />
        <div className="max-w-5xl mx-auto px-6 text-center relative z-10">
          {/* Badge */}
          <motion.div
            className="inline-flex items-center gap-2 glass px-4 py-2 rounded-full mb-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
          >
            <Sparkles size={14} className="text-[var(--primary)]" />
            <span className="text-xs font-medium text-[var(--text-secondary)]">Powered by a proprietary AI Brain with 120+ data patterns</span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            className="font-display text-5xl md:text-7xl lg:text-8xl font-bold leading-[0.95] mb-6"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          >
            Upload Any Messy Dataset.{" "}
            <span className="gradient-text">Leave With Decisions.</span>
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            className="text-lg md:text-xl text-[var(--text-secondary)] max-w-2xl mx-auto mb-10 leading-relaxed"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
          >
            DataSoul reveals threats, keeps humans in control, and converts raw chaos into
            trusted business intelligence — with a proprietary AI brain fine-tuned for data quality.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7, duration: 0.6 }}
          >
            <a
              href="/upload"
              className="btn-primary text-base px-8 py-4 flex items-center gap-3 group"
              onMouseEnter={() => setIsDemoHovered(true)}
              onMouseLeave={() => setIsDemoHovered(false)}
            >
              <Upload size={20} />
              Upload Your Dataset
              <motion.div animate={{ x: isDemoHovered ? 5 : 0 }} transition={{ type: "spring" }}>
                <ArrowRight size={18} />
              </motion.div>
            </a>
            <a href="/upload?demo=true" className="btn-ghost text-base px-8 py-4 flex items-center gap-2">
              <Sparkles size={18} />
              Try Demo Dataset
            </a>
          </motion.div>

          {/* Data Flow Visualization */}
          <motion.div
            className="glass-card p-6 md:p-8"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9, duration: 0.8 }}
          >
            <p className="text-xs text-[var(--text-muted)] mb-4 uppercase tracking-wider font-medium">The DataSoul Pipeline</p>
            <DataFlowVisual />
          </motion.div>
        </div>
      </motion.section>

      {/* ═══ METRICS BAR ═══ */}
      <section className="py-12 border-y" style={{ borderColor: "var(--glass-border)" }}>
        <div className="max-w-6xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8">
          {metrics.map((m, i) => (
            <motion.div key={i} className="text-center" custom={i} variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
              <div className="flex items-center justify-center gap-2 mb-2">
                <m.icon size={20} className="text-[var(--primary)]" />
                <span className="font-display text-3xl md:text-4xl font-bold gradient-text-primary">
                  <AnimatedNumber value={m.value} suffix={m.suffix} />
                </span>
              </div>
              <span className="text-sm text-[var(--text-secondary)]">{m.label}</span>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ═══ 6 PILLARS ═══ */}
      <section id="features" className="py-24">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div className="text-center mb-16" variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }} custom={0}>
            <h2 className="font-display text-3xl md:text-5xl font-bold mb-4">
              5 Pillars. <span className="gradient-text">Zero Compromises.</span>
            </h2>
            <p className="text-[var(--text-secondary)] max-w-xl mx-auto">Every pillar is engineered to turn raw, messy data into trusted intelligence — not just clean tables.</p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {pillars.map((p, i) => (
              <motion.div
                key={i}
                className="glass-card group"
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
              >
                <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-transform group-hover:scale-110" style={{ background: `${p.color}15`, border: `1px solid ${p.color}25` }}>
                  <p.icon size={22} style={{ color: p.color }} />
                </div>
                <h3 className="font-display font-semibold text-lg mb-2">{p.title}</h3>
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{p.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ THREAT DEMO ═══ */}
      <section id="threats" className="py-24" style={{ background: "rgba(239,68,68,0.02)" }}>
        <div className="max-w-6xl mx-auto px-6">
          <motion.div className="text-center mb-16" variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }} custom={0}>
            <span className="badge-critical mb-4 inline-block">THREAT-FIRST INTELLIGENCE</span>
            <h2 className="font-display text-3xl md:text-5xl font-bold mb-4 mt-4">
              Others Clean Data Silently.{" "}
              <span className="gradient-text">We Expose Every Threat.</span>
            </h2>
            <p className="text-[var(--text-secondary)] max-w-xl mx-auto">Data quality, ML, business, and privacy threats — all detected, scored, and actionable.</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6 mb-12">
            <ThreatDemoCard severity="critical" title="Duplicate Customer IDs" impact="Revenue reports may be inflated. 132 duplicate records detected across 3 ID columns." confidence={97} delay={0} />
            <ThreatDemoCard severity="warning" title="Missing Salary Data (12%)" impact="Payroll projections unreliable. Mean inflated 25% by executive outliers." confidence={88} delay={1} />
            <ThreatDemoCard severity="low" title="Inconsistent Region Names" impact="'East', 'east', 'EAST' — 3 phantom segments affecting geographic analysis." confidence={94} delay={2} />
          </div>

          {/* Threat summary bar */}
          <motion.div className="glass-card flex flex-col md:flex-row items-center justify-between gap-6 p-6" variants={scaleIn} initial="hidden" whileInView="visible" viewport={{ once: true }}>
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center heartbeat" style={{ background: "var(--critical-bg)", border: "1px solid rgba(239,68,68,0.3)" }}>
                <Activity size={28} className="text-[var(--critical)]" />
              </div>
              <div>
                <div className="font-display text-2xl font-bold text-[var(--text-primary)]">12 Threats Detected</div>
                <div className="text-sm text-[var(--text-secondary)]">Dataset Risk Score: 68/100</div>
              </div>
            </div>
            <div className="flex gap-6 text-center">
              <div><div className="font-semibold text-xl text-[var(--critical)]">3</div><div className="text-xs text-[var(--text-muted)]">Critical</div></div>
              <div><div className="font-semibold text-xl text-[var(--warning)]">5</div><div className="text-xs text-[var(--text-muted)]">Medium</div></div>
              <div><div className="font-semibold text-xl text-[var(--success)]">4</div><div className="text-xs text-[var(--text-muted)]">Low</div></div>
            </div>
            <a href="/upload" className="btn-primary flex items-center gap-2">
              <Shield size={16} />
              Scan Your Dataset
            </a>
          </motion.div>
        </div>
      </section>

      {/* ═══ SECTOR INTELLIGENCE ═══ */}
      <section id="sectors" className="py-24">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div className="text-center mb-16" variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }} custom={0}>
            <h2 className="font-display text-3xl md:text-5xl font-bold mb-4">
              One Platform.{" "}
              <span className="gradient-text">Every Sector.</span>
            </h2>
            <p className="text-[var(--text-secondary)] max-w-xl mx-auto">DataSoul automatically detects your business type from column names and adapts its intelligence.</p>
          </motion.div>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {[
              { name: "Retail", cols: "SKU, inventory, orders", emoji: "🛒" },
              { name: "Healthcare", cols: "patient_id, diagnosis", emoji: "🏥" },
              { name: "Finance", cols: "transaction, balance", emoji: "💰" },
              { name: "HR", cols: "employee_id, salary", emoji: "👥" },
              { name: "Manufacturing", cols: "machine_id, sensor", emoji: "🏭" },
              { name: "Education", cols: "student_id, grades", emoji: "🎓" },
              { name: "Logistics", cols: "shipment, tracking", emoji: "🚚" },
              { name: "Real Estate", cols: "listing, price/sqft", emoji: "🏠" },
              { name: "General", cols: "Any CSV/XLSX", emoji: "📊" },
            ].map((s, i) => (
              <motion.div
                key={i}
                className="glass-card text-center py-6"
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
              >
                <div className="text-3xl mb-2">{s.emoji}</div>
                <h4 className="font-semibold text-sm mb-1">{s.name}</h4>
                <p className="text-xs text-[var(--text-muted)]">{s.cols}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ AI BRAIN SECTION ═══ */}
      <section className="py-24" style={{ background: "var(--primary-glow)" }}>
        <div className="max-w-6xl mx-auto px-6">
          <motion.div className="text-center mb-16" variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }} custom={0}>
            <h2 className="font-display text-3xl md:text-5xl font-bold mb-4">
              Not a Generic LLM.{" "}
              <span className="gradient-text">A Proprietary AI Brain.</span>
            </h2>
            <p className="text-[var(--text-secondary)] max-w-2xl mx-auto">DataSoul is powered by a custom-trained AI with 120+ curated data quality patterns, fine-tuned locally on your hardware with no external dependencies.</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            <motion.div className="glass-card" custom={0} variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
              <Database size={28} className="text-[var(--primary)] mb-4" />
              <h3 className="font-display font-semibold text-lg mb-2">RAG Knowledge Base</h3>
              <p className="text-sm text-[var(--text-secondary)] mb-3">100+ curated patterns for missing values, outliers, encoding, scaling, threats, and sector-specific intelligence.</p>
              <div className="text-xs text-[var(--text-muted)]">18 files • 150KB • 9 sectors</div>
            </motion.div>
            <motion.div className="glass-card" custom={1} variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
              <Brain size={28} className="text-[var(--accent)] mb-4" />
              <h3 className="font-display font-semibold text-lg mb-2">Fine-Tuned LLM</h3>
              <p className="text-sm text-[var(--text-secondary)] mb-3">LoRA-adapted Llama 3.1 8B running locally on your GPU. Speaks DataSoul natively — trained on expert data analysis responses.</p>
              <div className="text-xs text-[var(--text-muted)]">QLoRA • 4-bit • RTX 4060 compatible</div>
            </motion.div>
            <motion.div className="glass-card" custom={2} variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
              <Lock size={28} className="text-[var(--success)] mb-4" />
              <h3 className="font-display font-semibold text-lg mb-2">Zero External Dependencies</h3>
              <p className="text-sm text-[var(--text-secondary)] mb-3">No OpenAI. No cloud APIs. No internet required. Your data never leaves your machine. Full privacy guaranteed.</p>
              <div className="text-xs text-[var(--text-muted)]">100% local • 100% private</div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══ CTA ═══ */}
      <section className="py-24">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <motion.div variants={scaleIn} initial="hidden" whileInView="visible" viewport={{ once: true }}>
            <div className="glass-card p-12 md:p-16 relative overflow-hidden">
              <div className="absolute inset-0 opacity-30" style={{ background: "var(--gradient-mesh)" }} />
              <div className="relative z-10">
                <h2 className="font-display text-3xl md:text-5xl font-bold mb-4">
                  Ready to Trust Your Data?
                </h2>
                <p className="text-[var(--text-secondary)] max-w-lg mx-auto mb-8">
                  Upload any CSV or Excel file. DataSoul will profile it, detect threats, and give you a complete data health report in under 30 seconds.
                </p>
                <a href="/upload" className="btn-primary text-lg px-10 py-5 inline-flex items-center gap-3">
                  <Upload size={22} />
                  Upload Your Dataset Now
                  <ArrowRight size={20} />
                </a>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-12 border-t" style={{ borderColor: "var(--glass-border)" }}>
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
                <Activity size={14} color="white" />
              </div>
              <span className="font-display font-bold">DataSoul</span>
              <span className="text-xs text-[var(--text-muted)]">v1.0</span>
            </div>
            <p className="text-sm text-[var(--text-muted)]">
              Upload any messy dataset. Leave with decisions. Built with ❤️ and a proprietary AI brain.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
