"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Upload, Shield, Brain, FileText, Zap, ChevronRight,
  CheckCircle2, Lock, ArrowRight, Activity, Database,
  Search, BarChart3, AlertTriangle, Cpu, HardDrive, Server
} from "lucide-react";

/* ─────────────────────── ANIMATION VARIANTS ─────────────────────── */
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" as const }
  })
};

/* ─────────────────────── COMPONENTS ─────────────────────── */

function ThreatMockupCard({ severity, title, impact }: { severity: 'critical' | 'warning' | 'success', title: string, impact: string }) {
  const badgeClass = `badge-${severity}`;
  return (
    <div className="bg-white border border-[var(--bg-border)] rounded-lg p-4 shadow-sm mb-3">
      <div className="mb-2">
        <span className={badgeClass}>{severity.toUpperCase()}</span>
      </div>
      <h4 className="font-medium text-[var(--text-primary)] text-sm mb-1">{title}</h4>
      <p className="text-xs text-[var(--text-secondary)]">{impact}</p>
    </div>
  );
}

function CapabilityCard({ icon: Icon, title, description }: { icon: React.ElementType, title: string, description: string }) {
  return (
    <div className="glass-card group">
      <div className="w-10 h-10 rounded-lg bg-[var(--primary-light)] text-[var(--primary)] flex items-center justify-center mb-4">
        <Icon size={20} />
      </div>
      <h3 className="font-semibold text-[var(--text-primary)] mb-2">{title}</h3>
      <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{description}</p>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   MAIN LANDING PAGE
   ═══════════════════════════════════════════════════════════════ */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      {/* ═══ NAVIGATION ═══ */}
      <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-[var(--bg-border)]">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-gradient-primary">
              <Activity size={18} color="white" />
            </div>
            <span className="font-semibold text-lg text-[var(--text-primary)]" style={{ fontFamily: "var(--font-body)" }}>DataSoul</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#capabilities" className="text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Capabilities</a>
            <a href="#features" className="text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Features</a>
            <a href="#architecture" className="text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Architecture</a>
          </div>
          <div className="flex items-center gap-4">
            <a href="/upload?demo=true" className="text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors hidden sm:block">Try Demo</a>
            <a href="/upload" className="btn-primary text-sm flex items-center gap-2">
              <Upload size={16} />
              Upload
            </a>
          </div>
        </div>
      </nav>

      {/* ═══ HERO SECTION — Left-aligned, technical ═══ */}
      <section className="relative pt-24 pb-20 overflow-hidden bg-gradient-hero">
        <div className="max-w-6xl mx-auto px-6 relative z-10">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.1 } } }}>
              <motion.h1
                className="text-4xl md:text-5xl lg:text-[3.5rem] font-bold leading-tight mb-6 text-[var(--text-primary)]"
                style={{ fontFamily: "var(--font-body)", letterSpacing: "-0.03em" }}
                variants={fadeUp} custom={0}
              >
                RAG-Powered Data Intelligence.{" "}
                <span className="text-gradient">Run Entirely on Your Machine.</span>
              </motion.h1>

              <motion.p
                className="text-lg text-[var(--text-secondary)] mb-8 leading-relaxed"
                variants={fadeUp} custom={1}
              >
                Profile datasets, detect threats, auto-clean with local LLMs, and query your data
                using ChromaDB-backed RAG — all offline, all private, zero cloud dependencies.
              </motion.p>

              <motion.div className="flex flex-col sm:flex-row gap-3 mb-8" variants={fadeUp} custom={2}>
                <a href="/upload" className="btn-primary text-base px-6 py-3 flex items-center gap-2 shadow-md">
                  <Upload size={18} />
                  Upload Dataset
                </a>
                <a href="/upload?demo=true" className="btn-ghost text-base px-6 py-3 flex items-center gap-2">
                  <Database size={18} />
                  Try Demo Dataset
                </a>
              </motion.div>

              <motion.div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-[var(--text-muted)]" variants={fadeUp} custom={3}>
                <span className="flex items-center gap-1.5"><Lock size={14} /> 100% local processing</span>
                <span className="flex items-center gap-1.5"><Cpu size={14} /> Local LLM runtime</span>
                <span className="flex items-center gap-1.5"><Database size={14} /> ChromaDB RAG</span>
              </motion.div>
            </motion.div>

            {/* Right side — Interactive mockup */}
            <motion.div
              className="mockup-container text-left"
              initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4, duration: 0.6 }}
            >
              <div className="bg-[var(--bg-secondary)] border-b border-[var(--bg-border)] p-4 flex items-center justify-between">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-400"></div>
                  <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                  <div className="w-3 h-3 rounded-full bg-green-400"></div>
                </div>
                <span className="text-xs text-[var(--text-muted)] font-mono">datasoul — threat audit</span>
              </div>
              <div className="p-5 bg-white">
                <ThreatMockupCard severity="critical" title="Duplicate Customer IDs" impact="Revenue reports inflated. 132 duplicate records found across 3 columns." />
                <ThreatMockupCard severity="warning" title="Missing Salary Data" impact="Mean inflated 25% by executive outliers. 847 null values in salary_annual." />
                <ThreatMockupCard severity="success" title="Formatting Standardized" impact="All dates resolved to ISO-8601 format. 12 inconsistent patterns fixed." />
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ═══ CAPABILITIES GRID ═══ */}
      <section id="capabilities" className="py-24 bg-white border-b border-[var(--bg-border)]">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div className="mb-16" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0}>
            <h2 className="text-3xl font-bold text-[var(--text-primary)] mb-3" style={{ fontFamily: "var(--font-body)" }}>
              What DataSoul does
            </h2>
            <p className="text-lg text-[var(--text-secondary)] max-w-2xl">
              Every capability runs locally through the inference runtime and ChromaDB. No API keys, no cloud, no data leaving your machine.
            </p>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <CapabilityCard
              icon={BarChart3}
              title="Deep Profiling"
              description="Statistical profiling with quality scoring across 6 dimensions — completeness, accuracy, consistency, validity, uniqueness, and timeliness."
            />
            <CapabilityCard
              icon={AlertTriangle}
              title="Threat Detection"
              description="120+ AI-powered quality patterns detect duplicates, outliers, missing data, format inconsistencies, and ML-readiness risks."
            />
            <CapabilityCard
              icon={Zap}
              title="Auto-Cleaning Pipeline"
              description="Iterative cleaning with LLM-guided imputation, deduplication, and standardization. Re-profiles after each pass."
            />
            <CapabilityCard
              icon={Search}
              title="RAG-Augmented Q&A"
              description="Ask plain-English questions about your data. ChromaDB indexes your dataset context for hyper-relevant answers."
            />
            <CapabilityCard
              icon={FileText}
              title="Executive Narratives"
              description="Boardroom-ready reports with threat summaries, KPI breakdowns, and action plans."
            />
            <CapabilityCard
              icon={Shield}
              title="CSV Correction Engine"
              description="LLM-powered value correction with encoding fixes, category merges, and type coercion. Confidence-scored suggestions."
            />
          </div>
        </div>
      </section>

      {/* ═══ ALTERNATING FEATURE SECTIONS ═══ */}
      <section id="features" className="py-24 bg-[var(--bg-primary)]">
        <div className="max-w-6xl mx-auto px-6 space-y-32">
          
          {/* Feature 1: Threat Detection */}
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0}>
              <div className="w-12 h-12 rounded-xl bg-[var(--primary-light)] text-[var(--primary)] flex items-center justify-center mb-6">
                <Shield size={24} />
              </div>
              <h2 className="text-3xl font-bold text-[var(--text-primary)] mb-4" style={{ fontFamily: "var(--font-body)" }}>
                Threat-First Intelligence
              </h2>
              <p className="text-lg text-[var(--text-secondary)] mb-6 leading-relaxed">
                Every dataset gets a full threat audit. Data quality, ML-readiness, business, and privacy risks are automatically detected, severity-scored, and prioritized.
              </p>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center gap-3 text-[var(--text-secondary)]">
                  <CheckCircle2 size={18} className="text-[var(--success)]" /> Duplicate resolution across composite keys
                </li>
                <li className="flex items-center gap-3 text-[var(--text-secondary)]">
                  <CheckCircle2 size={18} className="text-[var(--success)]" /> LLM-guided missing value imputation
                </li>
                <li className="flex items-center gap-3 text-[var(--text-secondary)]">
                  <CheckCircle2 size={18} className="text-[var(--success)]" /> Statistical anomaly detection (IQR + Isolation Forest)
                </li>
              </ul>
              <a href="/upload" className="text-[var(--primary)] font-medium flex items-center gap-2 hover:gap-3 transition-all">
                Try it on your data <ArrowRight size={16} />
              </a>
            </motion.div>
            <motion.div className="mockup-container bg-[var(--bg-secondary)] p-6" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={1}>
              <h3 className="font-medium text-sm text-[var(--text-muted)] mb-4 uppercase tracking-wider">Automated Threat Audit</h3>
              <ThreatMockupCard severity="critical" title="Duplicate Customer IDs" impact="Revenue reports inflated. 132 duplicate records." />
              <ThreatMockupCard severity="warning" title="Missing Salary Data" impact="Mean inflated 25% by executive outliers." />
              <ThreatMockupCard severity="success" title="Formatting Standardized" impact="All dates resolved to ISO-8601 format." />
            </motion.div>
          </div>

          {/* Feature 2: RAG Chat */}
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <motion.div className="mockup-container bg-white p-6 order-2 md:order-1" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={0}>
               <div className="border border-[var(--bg-border)] rounded-lg overflow-hidden shadow-sm">
                  <div className="bg-[var(--bg-secondary)] p-3 border-b border-[var(--bg-border)] text-sm font-medium flex items-center gap-2">
                    <Brain size={14} className="text-[var(--primary)]" /> RAG-Augmented Chat
                  </div>
                  <div className="p-4 space-y-4">
                    <div className="flex gap-3">
                      <div className="w-8 h-8 rounded-full bg-gray-200 flex-shrink-0 flex items-center justify-center text-xs font-medium text-gray-500">U</div>
                      <div className="bg-[var(--bg-secondary)] p-3 rounded-lg rounded-tl-none text-sm text-[var(--text-secondary)]">What are the key drivers for missing inventory?</div>
                    </div>
                    <div className="flex gap-3 flex-row-reverse">
                      <div className="w-8 h-8 rounded-full bg-[var(--primary-light)] text-[var(--primary)] flex items-center justify-center flex-shrink-0"><Brain size={16}/></div>
                      <div className="bg-[var(--primary)] text-white p-3 rounded-lg rounded-tr-none text-sm">
                        Based on the dataset and RAG context, missing inventory correlates strongly with Warehouse_B and Weekend delivery times. I recommend standardizing the datetime column to investigate further.
                      </div>
                    </div>
                  </div>
               </div>
            </motion.div>
            <motion.div className="order-1 md:order-2" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp} custom={1}>
              <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-6">
                <Search size={24} />
              </div>
              <h2 className="text-3xl font-bold text-[var(--text-primary)] mb-4" style={{ fontFamily: "var(--font-body)" }}>
                Query Your Data in Plain English
              </h2>
              <p className="text-lg text-[var(--text-secondary)] mb-6 leading-relaxed">
                ChromaDB indexes your dataset columns, statistics, correlations, and quality metrics. Ask any question and get answers grounded in your actual data — not hallucinations.
              </p>
              <ul className="space-y-3 mb-8">
                <li className="flex items-center gap-3 text-[var(--text-secondary)]">
                  <CheckCircle2 size={18} className="text-[var(--success)]" /> Dataset-aware context injection
                </li>
                <li className="flex items-center gap-3 text-[var(--text-secondary)]">
                  <CheckCircle2 size={18} className="text-[var(--success)]" /> Knowledge base + live data fusion
                </li>
                <li className="flex items-center gap-3 text-[var(--text-secondary)]">
                  <CheckCircle2 size={18} className="text-[var(--success)]" /> Grounded responses from local context
                </li>
              </ul>
              <a href="/upload" className="text-[var(--primary)] font-medium flex items-center gap-2 hover:gap-3 transition-all">
                Start a conversation <ArrowRight size={16} />
              </a>
            </motion.div>
          </div>

        </div>
      </section>

      {/* ═══ ARCHITECTURE SECTION ═══ */}
      <section id="architecture" className="py-20 bg-[var(--bg-secondary)] border-y border-[var(--bg-border)]">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-[var(--text-primary)] mb-3" style={{ fontFamily: "var(--font-body)" }}>
            Technical Stack
          </h2>
          <p className="text-lg text-[var(--text-secondary)] mb-12 max-w-2xl">
            Every component runs on your local machine. No external API calls, no telemetry, no data exfiltration.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { icon: Cpu, label: "Local LLM", detail: "Qwen / Mistral-class models" },
              { icon: Database, label: "ChromaDB", detail: "Vector store for RAG" },
              { icon: Server, label: "FastAPI", detail: "Backend engine" },
              { icon: HardDrive, label: "Local-only", detail: "Zero cloud dependencies" },
            ].map((item, i) => (
              <motion.div
                key={i}
                className="glass-card text-center"
                initial="hidden" whileInView="visible" viewport={{ once: true }}
                variants={fadeUp} custom={i}
              >
                <div className="w-12 h-12 rounded-xl bg-[var(--primary-light)] text-[var(--primary)] flex items-center justify-center mx-auto mb-4">
                  <item.icon size={22} />
                </div>
                <div className="font-semibold text-[var(--text-primary)] mb-1">{item.label}</div>
                <div className="text-sm text-[var(--text-muted)]">{item.detail}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ CTA SECTION ═══ */}
      <section className="py-24 bg-white">
        <div className="max-w-4xl mx-auto px-6">
          <div className="bg-gradient-primary rounded-2xl p-10 md:p-16 text-center text-white shadow-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 rounded-full bg-white opacity-10"></div>
            <div className="absolute bottom-0 left-0 -ml-16 -mb-16 w-48 h-48 rounded-full bg-black opacity-10"></div>
            
            <div className="relative z-10">
              <h2 className="text-3xl md:text-4xl font-bold mb-6" style={{ fontFamily: "var(--font-body)" }}>
                Ready to profile your dataset?
              </h2>
              <p className="text-lg opacity-90 max-w-xl mx-auto mb-10">
                Upload any CSV or Excel file. DataSoul will profile it, detect threats, and give you a complete data health report — all locally.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <a href="/upload" className="bg-white text-[var(--primary-dark)] px-8 py-3.5 rounded-lg font-semibold hover:bg-gray-50 transition-colors shadow-md">
                  Upload Dataset
                </a>
                <a href="/upload?demo=true" className="bg-[rgba(255,255,255,0.1)] border border-[rgba(255,255,255,0.2)] text-white px-8 py-3.5 rounded-lg font-semibold hover:bg-[rgba(255,255,255,0.2)] transition-colors">
                  Try Demo Dataset
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-8 bg-white border-t border-[var(--bg-border)]">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded flex items-center justify-center bg-gradient-primary">
              <Activity size={12} color="white" />
            </div>
            <span className="font-semibold text-[var(--text-primary)]">DataSoul</span>
            <span className="text-xs text-[var(--text-muted)] border border-[var(--bg-border)] px-2 py-0.5 rounded-full ml-2">v3.0</span>
          </div>
          <p className="text-sm text-[var(--text-muted)]">
            Local-first data intelligence engine
          </p>
        </div>
      </footer>
    </div>
  );
}
