"use client";

import { useState, useEffect, Suspense } from "react";
import { motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import {
  Activity, BarChart3, TrendingUp, TrendingDown, ChevronRight,
  ArrowLeft, DollarSign, ShoppingCart, Users, Package, Target,
  Award, AlertTriangle, Sparkles, ArrowRight, PieChart as PieIcon,
  Minus, Layers, LineChart, Loader2, AlertCircle
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
  CartesianGrid
} from "recharts";
import { getInsights, getProfile, type InsightsResponse, type ProfileResponse } from "../api";
import { getSessionFromParams } from "../useSession";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] as const }
  })
};

const tooltipStyle = {
  contentStyle: { background: "var(--bg-card)", border: "1px solid var(--glass-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "12px" }
};

const CHART_COLORS = ["#6366f1", "#8b5cf6", "#06b6d4", "#22c55e", "#f59e0b", "#ef4444", "#ec4899", "#64748b"];

function formatValue(v: number): string {
  if (Math.abs(v) >= 1_00_00_000) return `₹${(v / 1_00_00_000).toFixed(2)}Cr`;
  if (Math.abs(v) >= 1_00_000) return `₹${(v / 1_00_000).toFixed(2)}L`;
  if (Math.abs(v) >= 1000) return `₹${(v / 1000).toFixed(1)}K`;
  return v.toLocaleString();
}

function InsightsPageContent() {
  const searchParams = useSearchParams();
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    const id = getSessionFromParams(searchParams);
    if (id) {
      setSessionId(id);
    } else {
      setError("No session found. Upload a dataset first.");
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!sessionId) return;
    async function fetchData() {
      setLoading(true);
      try {
        const [insightsData, profileData] = await Promise.all([
          getInsights(sessionId!),
          getProfile(sessionId!),
        ]);
        setInsights(insightsData);
        setProfile(profileData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load insights.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [sessionId]);

  const sectorName = profile?.sector?.sector_name ?? "General";

  // Derive KPI cards from insights
  const kpiCards = insights?.kpis?.slice(0, 6).map((kpi, i) => {
    const isFinancial = kpi.kpi_type === "financial";
    const icons = [DollarSign, ShoppingCart, Target, Package, Users, Award];
    const colors = ["#22c55e", "#6366f1", "#06b6d4", "#f59e0b", "#8b5cf6", "#22c55e"];
    return {
      label: kpi.column.replace(/_/g, " "),
      value: isFinancial ? kpi.formatted_total ?? formatValue(kpi.total) : formatValue(kpi.total),
      mean: isFinancial ? formatValue(kpi.mean) : kpi.mean.toLocaleString(),
      median: isFinancial ? formatValue(kpi.median) : kpi.median.toLocaleString(),
      icon: icons[i % icons.length],
      color: colors[i % colors.length],
    };
  }) ?? [];

  // Derive distribution chart data (first category distribution)
  const distData = insights?.distributions?.[0];
  const pieData = distData
    ? Object.entries(distData.values).slice(0, 8).map(([name, value], i) => ({
        name,
        value,
        fill: CHART_COLORS[i % CHART_COLORS.length],
      }))
    : [];

  // All distributions as bar charts
  const barDistributions = insights?.distributions?.slice(0, 3) ?? [];

  // Anomalies
  const anomalies = insights?.anomalies ?? [];

  // Quality benchmarks from profile
  const benchmarks = profile ? [
    {
      metric: "Missing Value Rate",
      yours: `${profile.missing_summary.overall_missing_pct}%`,
      industry: "3.0%",
      status: profile.missing_summary.overall_missing_pct <= 3 ? "success" : "warning",
      verdict: profile.missing_summary.overall_missing_pct <= 3 ? "Below average — good data hygiene" : "Above average — needs improvement",
    },
    {
      metric: "Duplicate Rate",
      yours: `${profile.duplicates.duplicate_pct}%`,
      industry: "1.0%",
      status: profile.duplicates.duplicate_pct <= 1 ? "success" : "warning",
      verdict: profile.duplicates.duplicate_pct <= 1 ? "Below average — good data hygiene" : "Above average — duplicates detected",
    },
    {
      metric: "Completeness Score",
      yours: `${Math.round(profile.quality_score.dimensions?.completeness?.score ?? 0)}%`,
      industry: "85%",
      status: (profile.quality_score.dimensions?.completeness?.score ?? 0) >= 85 ? "success" : "warning",
      verdict: (profile.quality_score.dimensions?.completeness?.score ?? 0) >= 85 ? "Above benchmark" : `${Math.round(85 - (profile.quality_score.dimensions?.completeness?.score ?? 0))} points below benchmark`,
    },
    {
      metric: "Overall Health",
      yours: `${Math.round(profile.quality_score.overall)}/100`,
      industry: "80/100",
      status: profile.quality_score.overall >= 80 ? "success" : "warning",
      verdict: `Grade ${profile.quality_score.grade}`,
    },
  ] : [];

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
          <span className="text-[var(--text-secondary)]">Generating insights from your data...</span>
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
          <h2 className="font-display text-2xl font-bold mb-2">Failed to load insights</h2>
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
            <span className="text-sm text-[var(--text-secondary)]">Insights Dashboard</span>
          </div>
          <div className="flex items-center gap-3">
            <a href={`/health?session=${sessionId}`} className="btn-ghost text-sm flex items-center gap-2">
              <ArrowLeft size={16} /> Health
            </a>
            <a href={`/story?session=${sessionId}`} className="btn-primary text-sm flex items-center gap-2">
              <Sparkles size={16} /> View Story
            </a>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6">
        {/* Header */}
        <motion.div className="mb-8" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-display text-2xl md:text-3xl font-bold mb-2">
            Insights Dashboard — <span className="gradient-text">{sectorName}</span>
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            Auto-generated KPIs, distributions, and anomalies from your dataset
          </p>
        </motion.div>

        {/* KPI Cards */}
        {kpiCards.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
            {kpiCards.map((kpi, i) => (
              <motion.div key={i} className="glass-card" custom={i} variants={fadeUp} initial="hidden" animate="visible">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${kpi.color}15` }}>
                    <kpi.icon size={16} style={{ color: kpi.color }} />
                  </div>
                </div>
                <div className="font-display text-lg font-bold mb-1">{kpi.value}</div>
                <div className="text-xs text-[var(--text-muted)] capitalize">{kpi.label}</div>
                <div className="text-xs text-[var(--text-muted)] mt-1">Mean: {kpi.mean} • Med: {kpi.median}</div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Distribution Charts */}
        <div className="grid lg:grid-cols-2 gap-6 mb-8">
          {/* First distribution as Pie */}
          {pieData.length > 0 && (
            <motion.div className="glass-card" custom={6} variants={fadeUp} initial="hidden" animate="visible">
              <h3 className="font-display text-sm font-semibold mb-4 flex items-center gap-2">
                <PieIcon size={16} className="text-[var(--accent)]" />
                {distData?.column.replace(/_/g, " ")} Distribution
              </h3>
              <div className="flex items-center gap-4">
                <ResponsiveContainer width="50%" height={220}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3}>
                      {pieData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                    </Pie>
                    <Tooltip {...tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-2">
                  {pieData.map((cat, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: cat.fill }} />
                      <span className="text-[var(--text-secondary)] flex-1 truncate">{cat.name}</span>
                      <span className="font-mono font-medium text-xs">{cat.value.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Second distribution as Bar */}
          {barDistributions[1] && (
            <motion.div className="glass-card" custom={7} variants={fadeUp} initial="hidden" animate="visible">
              <h3 className="font-display text-sm font-semibold mb-4 flex items-center gap-2">
                <BarChart3 size={16} className="text-[var(--primary)]" />
                {barDistributions[1].column.replace(/_/g, " ")} Distribution
              </h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={Object.entries(barDistributions[1].values).slice(0, 10).map(([name, value], i) => ({ name: name.length > 12 ? name.slice(0, 12) + "…" : name, count: value }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip {...tooltipStyle} />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={30} fillOpacity={0.8} />
                </BarChart>
              </ResponsiveContainer>
            </motion.div>
          )}
        </div>

        {/* Bottom Row: Anomalies + Benchmarks */}
        <div className="grid lg:grid-cols-2 gap-6 mb-8">
          {/* Anomalies */}
          <motion.div className="glass-card" custom={9} variants={fadeUp} initial="hidden" animate="visible">
            <h3 className="font-display text-sm font-semibold mb-4 flex items-center gap-2">
              <AlertTriangle size={16} className="text-[var(--warning)]" />
              Detected Anomalies ({anomalies.length})
            </h3>
            {anomalies.length > 0 ? (
              <div className="space-y-3">
                {anomalies.slice(0, 5).map((a, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg" style={{ background: a.extreme_pct > 1 ? "var(--critical-bg)" : "var(--warning-bg)" }}>
                    <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" style={{ color: a.extreme_pct > 1 ? "var(--critical)" : "var(--warning)" }} />
                    <div>
                      <div className="text-sm font-medium">Outliers in {a.column}</div>
                      <div className="text-xs text-[var(--text-secondary)]">
                        {a.extreme_count} extreme values ({a.extreme_pct}%) — max: {formatValue(a.max_extreme)}, median: {formatValue(a.median_value)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-sm text-[var(--text-muted)]">No significant anomalies detected ✓</div>
            )}
          </motion.div>

          {/* Benchmarks */}
          <motion.div className="glass-card" custom={10} variants={fadeUp} initial="hidden" animate="visible">
            <h3 className="font-display text-sm font-semibold mb-4 flex items-center gap-2">
              <Target size={16} className="text-[var(--primary)]" />
              Data Quality Benchmark
            </h3>
            <div className="space-y-3">
              {benchmarks.map((b, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-lg" style={{ background: "var(--glass-bg)" }}>
                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: b.status === "success" ? "var(--success)" : "var(--warning)" }} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{b.metric}</div>
                    <div className="text-xs text-[var(--text-muted)]">{b.verdict}</div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-sm font-mono font-medium">{b.yours}</div>
                    <div className="text-xs text-[var(--text-muted)]">Target: {b.industry}</div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* CTA Bar */}
        <motion.div className="glass-card flex flex-col md:flex-row items-center justify-between gap-4" custom={11} variants={fadeUp} initial="hidden" animate="visible">
          <div>
            <p className="font-semibold text-sm">Want the full story?</p>
            <p className="text-xs text-[var(--text-secondary)]">AI-generated executive narrative with sector-specific insights and action plan.</p>
          </div>
          <a href={`/story?session=${sessionId}`} className="btn-primary text-sm flex items-center gap-2">
            <Sparkles size={16} /> Generate AI Story <ArrowRight size={16} />
          </a>
        </motion.div>
      </div>
    </div>
  );
}

export default function InsightsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><Loader2 size={32} className="animate-spin text-[var(--primary)]" /></div>}>
      <InsightsPageContent />
    </Suspense>
  );
}
