"""
DataSoul Narrative Engine
===========================
Generates executive narratives, business insights, KPIs,
and handles Conversational Data Chat Q&A.

Dual-mode:
1. LLM Mode — uses Ollama via llm_engine for rich, natural narratives
2. Template Mode — deterministic fallback for instant responses
"""

import pandas as pd
import numpy as np
from typing import Optional
from llm_engine import get_llm


class NarrativeEngine:
    """Generates insights, stories, and answers using dataset analysis"""

    def __init__(self):
        self._llm = get_llm()

    def generate_insights(self, df: pd.DataFrame, profile: dict) -> dict:
        """Generate auto-computed KPIs and insight cards"""
        insights: dict = {
            "kpis": [],
            "distributions": [],
            "anomalies": [],
            "recommendations": [],
        }

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()

        # ─── Auto-detect KPIs ───
        for col in numeric_cols:
            clean = df[col].dropna()
            if len(clean) == 0:
                continue

            kpi: dict = {
                "column": col,
                "type": "numeric",
                "total": round(float(clean.sum()), 2),
                "mean": round(float(clean.mean()), 2),
                "median": round(float(clean.median()), 2),
                "std": round(float(clean.std()), 2),
                "min": round(float(clean.min()), 2),
                "max": round(float(clean.max()), 2),
            }

            # Revenue/price detection → treat as financial KPI
            if any(kw in col.lower() for kw in ["revenue", "amount", "price", "cost", "sales", "total", "income"]):
                kpi["kpi_type"] = "financial"
                kpi["formatted_total"] = self._format_currency(clean.sum())

            insights["kpis"].append(kpi)

        # ─── Category distributions ───
        for col in categorical_cols:
            clean = df[col].dropna().astype(str)
            if len(clean) == 0 or clean.nunique() > 50:
                continue

            dist = clean.value_counts().head(10)
            insights["distributions"].append({
                "column": col,
                "values": {str(k): int(v) for k, v in dist.items()},
                "unique": int(clean.nunique()),
                "mode": str(clean.mode().iloc[0]) if not clean.mode().empty else None,
            })

        # ─── Anomaly detection ───
        for col in numeric_cols:
            clean = df[col].dropna()
            if len(clean) < 20:
                continue

            q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
            iqr = q3 - q1
            extremes = clean[(clean < q1 - 3 * iqr) | (clean > q3 + 3 * iqr)]

            if len(extremes) > 0:
                insights["anomalies"].append({
                    "column": col,
                    "extreme_count": int(len(extremes)),
                    "extreme_pct": round(len(extremes) / len(clean) * 100, 2),
                    "max_extreme": round(float(extremes.max()), 2),
                    "min_extreme": round(float(extremes.min()), 2),
                    "median_value": round(float(clean.median()), 2),
                })

        return insights

    def generate_story(self, df: pd.DataFrame, profile: Optional[dict], threats: Optional[dict],
                        rag_context: str = "") -> str:
        """Generate the executive narrative — LLM first, template fallback"""
        # Try LLM mode first
        if self._llm.is_available and profile:
            try:
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                num_summary = {}
                for col in numeric_cols[:5]:
                    clean = df[col].dropna()
                    if len(clean) > 0:
                        num_summary[col] = {"total": float(clean.sum()), "mean": float(clean.mean()), "median": float(clean.median())}

                df_summary = {"rows": len(df), "cols": len(df.columns), "numeric_summary": num_summary}
                llm_story = self._llm.generate_narrative(
                    profile, threats or {"threats": [], "total": 0, "critical": 0, "warning": 0},
                    df_summary, rag_context=rag_context,
                )
                if llm_story and len(llm_story) > 100:
                    return llm_story
            except Exception as e:
                print(f"[Narrative] LLM generation failed, using template: {e}")

        # Template fallback
        rows = len(df)
        cols = len(df.columns)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df.select_dtypes(include=["object"]).columns.tolist()

        # Quality score
        qs = profile.get("quality_score", {}) if profile else {}
        overall_score = qs.get("overall", 0)
        grade = qs.get("grade", "N/A")

        # Threat count
        threat_list = threats.get("threats", []) if threats else []
        critical = sum(1 for t in threat_list if t.get("severity") == "critical")
        warning = sum(1 for t in threat_list if t.get("severity") == "warning")

        # ─── Build narrative sections ───
        sections = []

        # Headline
        sections.append(f"## DataSoul Intelligence Report\n")
        sections.append(f"**Dataset:** {rows:,} records × {cols} dimensions\n")
        sections.append(f"**Data Health Score:** {overall_score}/100 (Grade: {grade})\n")
        sections.append(f"**Threats Detected:** {len(threat_list)} ({critical} critical, {warning} medium)\n")
        sections.append("---\n")

        # Key Financial Metrics
        financial_cols = [c for c in numeric_cols if any(kw in c.lower() for kw in ["revenue", "amount", "price", "cost", "sales", "total", "income", "salary"])]
        if financial_cols:
            sections.append("### 📈 Key Financial Metrics\n")
            for col in financial_cols[:3]:
                clean = df[col].dropna()
                sections.append(f"- **{col}:** Total {self._format_currency(clean.sum())} | Mean {self._format_currency(clean.mean())} | Median {self._format_currency(clean.median())}")
            sections.append("")

        # Distributions
        if cat_cols:
            sections.append("### 📊 Category Breakdown\n")
            for col in cat_cols[:3]:
                clean = df[col].dropna().astype(str)
                if clean.nunique() <= 20:
                    top = clean.value_counts().head(3)
                    top_str = ", ".join([f"{k} ({v})" for k, v in top.items()])
                    sections.append(f"- **{col}:** {clean.nunique()} categories. Top: {top_str}")
            sections.append("")

        # Threat Summary
        if threat_list:
            sections.append("### 🛡️ Threat Intelligence Summary\n")
            for t in threat_list[:5]:
                emoji = "🔴" if t["severity"] == "critical" else "🟡" if t["severity"] == "warning" else "🟢"
                sections.append(f"{emoji} **{t['title']}** — {t.get('impact', '')[:120]}...")
            sections.append("")

        # Data Quality Dimensions
        if qs.get("dimensions"):
            sections.append("### 🎯 Data Quality Dimensions\n")
            sections.append("| Dimension | Score | Weight |")
            sections.append("|-----------|-------|--------|")
            for dim_name, dim_data in qs["dimensions"].items():
                bar = "█" * int(dim_data["score"] / 10) + "░" * (10 - int(dim_data["score"] / 10))
                sections.append(f"| {dim_name.title()} | {bar} {dim_data['score']} | {int(dim_data['weight']*100)}% |")
            sections.append("")

        # Action Plan
        sections.append("### ✅ Recommended Next Steps\n")
        if critical > 0:
            sections.append(f"1. **Immediately:** Address {critical} critical threats before using this data for decisions")
        if warning > 0:
            sections.append(f"2. **This Week:** Review and resolve {warning} medium-severity issues")
        sections.append(f"3. **Ongoing:** Set up automated data quality monitoring to maintain your {grade} grade")
        sections.append(f"4. **Strategic:** Schedule weekly data refresh to ensure insights reflect current conditions")
        sections.append("")

        # ROI
        sections.append("### 💰 ROI of DataSoul Analysis\n")
        sections.append(f"- ⏱️ ~{max(5, rows // 500)} analyst hours saved on manual profiling and cleaning")
        sections.append(f"- 🛡️ {len(threat_list)} data threats identified before they corrupted decisions")
        sections.append(f"- 📊 Data health quantified: {overall_score}/100 with actionable improvement plan")
        sections.append(f"- 📈 Full audit trail generated for compliance documentation")

        return "\n".join(sections)

    def answer_question(self, question: str, df: pd.DataFrame, profile: Optional[dict],
                         rag_context: str = "") -> str:
        """Answer conversational questions about the dataset — LLM first, pattern-match fallback"""
        q = question.lower().strip()

        # Try LLM for complex/open-ended questions
        if self._llm.is_available and not self._is_simple_question(q):
            try:
                df_context = f"Columns: {list(df.columns)}\n"
                df_context += f"Shape: {df.shape}\n"
                df_context += f"Dtypes: {dict(df.dtypes.astype(str).value_counts())}\n"
                df_context += f"Missing: {dict(df.isna().sum()[df.isna().sum() > 0])}\n"
                for col in df.select_dtypes(include=[np.number]).columns[:3]:
                    clean = df[col].dropna()
                    if len(clean) > 0:
                        df_context += f"{col}: mean={clean.mean():.2f}, median={clean.median():.2f}, std={clean.std():.2f}\n"

                llm_answer = self._llm.answer_question(question, df_context, profile or {}, rag_context)
                if llm_answer and len(llm_answer) > 20:
                    return llm_answer
            except Exception:
                pass  # Fall through to template

        # Pattern-matching fallback

        # ─── Pattern matching for common questions ───
        if any(kw in q for kw in ["missing", "null", "empty", "na"]):
            missing = df.isna().sum()
            missing_cols = missing[missing > 0].sort_values(ascending=False)
            if len(missing_cols) == 0:
                return "Great news — your dataset has no missing values! All columns are 100% complete."
            response = "Here's the missing value breakdown:\n\n"
            response += "| Column | Missing | % |\n|--------|---------|---|\n"
            for col, count in missing_cols.items():
                pct = round(count / len(df) * 100, 1)
                response += f"| {col} | {count:,} | {pct}% |\n"
            response += f"\n**Total:** {int(missing.sum()):,} missing cells out of {len(df) * len(df.columns):,} ({round(missing.sum() / (len(df) * len(df.columns)) * 100, 2)}%)"
            return response

        if any(kw in q for kw in ["duplicate", "dup"]):
            dups = df.duplicated().sum()
            if dups == 0:
                return "No duplicate rows found! Your dataset has clean, unique records."
            return f"Found **{dups:,} duplicate rows** ({round(dups/len(df)*100, 2)}% of dataset). Recommendation: Remove duplicates to prevent inflated metrics."

        if any(kw in q for kw in ["shape", "size", "how many", "rows", "columns"]):
            return f"Your dataset has **{len(df):,} rows** and **{len(df.columns)} columns**.\n\nColumn types: {dict(df.dtypes.value_counts())}\nMemory usage: {round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)} MB"

        if any(kw in q for kw in ["outlier", "extreme", "anomal"]):
            response = "Outlier analysis:\n\n"
            for col in df.select_dtypes(include=[np.number]).columns:
                clean = df[col].dropna()
                if len(clean) < 10:
                    continue
                q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
                iqr = q3 - q1
                outliers = clean[(clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)]
                if len(outliers) > 0:
                    response += f"- **{col}:** {len(outliers)} outliers ({round(len(outliers)/len(clean)*100, 1)}%) | Range: [{round(float(q1 - 1.5*iqr), 2)}, {round(float(q3 + 1.5*iqr), 2)}]\n"
            return response if "**" in response else "No significant outliers detected in numeric columns."

        if any(kw in q for kw in ["health", "quality", "score", "grade"]):
            if profile and "quality_score" in profile:
                qs = profile["quality_score"]
                response = f"## Data Health Score: {qs['overall']}/100 (Grade: {qs['grade']})\n\n"
                for dim, data in qs.get("dimensions", {}).items():
                    bar = "█" * int(data["score"] / 10) + "░" * (10 - int(data["score"] / 10))
                    response += f"- {dim.title()}: {bar} {data['score']}\n"
                return response
            return "Run a full profile first to see your data health score."

        if any(kw in q for kw in ["summary", "overview", "describe", "tell me about"]):
            response = f"## Dataset Summary\n\n"
            response += f"- **Size:** {len(df):,} rows × {len(df.columns)} columns\n"
            response += f"- **Memory:** {round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)} MB\n"
            response += f"- **Missing:** {int(df.isna().sum().sum()):,} cells ({round(df.isna().sum().sum() / (len(df) * len(df.columns)) * 100, 2)}%)\n"
            response += f"- **Duplicates:** {int(df.duplicated().sum()):,} rows\n"
            response += f"\n### Numeric columns ({len(df.select_dtypes(include=[np.number]).columns)})\n"
            for col in df.select_dtypes(include=[np.number]).columns[:5]:
                clean = df[col].dropna()
                if len(clean) > 0:
                    response += f"- **{col}:** mean={clean.mean():.2f}, median={clean.median():.2f}, range=[{clean.min():.2f}, {clean.max():.2f}]\n"
            return response

        # Default response
        return f"I can help you understand your dataset ({len(df):,} rows × {len(df.columns)} columns). Try asking:\n\n- \"What's missing in my data?\"\n- \"Are there duplicates?\"\n- \"Show me the data health score\"\n- \"What outliers exist?\"\n- \"Give me a summary\"\n- \"What's the biggest threat?\""

    @staticmethod
    def _is_simple_question(q: str) -> bool:
        """Check if a question matches our simple pattern-match templates.
        If so, we skip the LLM for faster response."""
        simple_patterns = [
            ["missing", "null", "empty", "na"],
            ["duplicate", "dup"],
            ["shape", "size", "how many", "rows", "columns"],
            ["outlier", "extreme", "anomal"],
            ["health", "quality", "score", "grade"],
            ["summary", "overview", "describe", "tell me about"],
        ]
        return any(any(kw in q for kw in group) for group in simple_patterns)

    @staticmethod
    def _format_currency(value: float) -> str:
        """Format as Indian currency (₹) with L/Cr"""
        if abs(value) >= 1_00_00_000:
            return f"₹{value / 1_00_00_000:.2f}Cr"
        elif abs(value) >= 1_00_000:
            return f"₹{value / 1_00_000:.2f}L"
        elif abs(value) >= 1000:
            return f"₹{value / 1000:.1f}K"
        else:
            return f"₹{value:.2f}"
