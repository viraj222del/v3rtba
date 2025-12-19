import streamlit as st
import traceback
import pandas as pd

from typing import Dict, Any, List, Tuple

from git_debt_analyzer import run_analysis_pipeline
from report_generator import security_keyword_scan
from security_analyzer import analyze_repo as run_security_analysis
from gemini_integration import (
    generate_code_analysis_summary,
    generate_contributor_analysis_summary,
    generate_security_analysis_summary
)


def build_tables_from_data(all_file_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build in‑memory table structures from the aggregated analysis data.
    This mirrors the core tables printed by generate_cli_report, but returns
    them as Python lists that Streamlit can render as DataFrames.
    """
    tables: Dict[str, Any] = {}

    # Extract special entries but keep original dictionary untouched for callers
    repo_stats = all_file_data.get("_repo_stats", {})
    contributor_data = all_file_data.get("_contributor_stats", {})
    local_repo_path = all_file_data.get("_local_repo_path", "")

    files = [
        (path, data)
        for path, data in all_file_data.items()
        if not path.startswith("_")
        and isinstance(data, dict)
        and data.get("loc", 0) > 0
        and "risk_score" in data
    ]

    # 2. File Size Summary
    loc_list = sorted(files, key=lambda x: x[1].get("loc", 0), reverse=True)
    tables["file_size"] = [
        {"file_path": path, "loc": data.get("loc", 0)}
        for path, data in loc_list
    ]

    # 3. Complexity & Churn
    complexity_churn = []
    for path, data in files:
        churn = data.get("lines_added", 0) + data.get("lines_removed", 0)
        complexity_churn.append(
            {
                "file_path": path,
                "complexity": data.get("complexity", 0),
                "churn": churn,
                "complexity_x_churn": data.get("complexity", 0) * churn,
            }
        )
    complexity_churn.sort(key=lambda x: x["complexity_x_churn"], reverse=True)
    tables["complexity_churn"] = complexity_churn

    # 4. Highest Risk Files
    top_risk = sorted(files, key=lambda x: x[1].get("risk_score", 0), reverse=True)
    tables["risk"] = [
        {
            "file_path": path,
            "risk_score": data.get("risk_score", 0.0),
            "main_factor": data.get("main_factor", ""),
            "complexity": data.get("complexity", 0),
        }
        for path, data in top_risk
    ]

    # 5. Systemic Risk
    systemic_sorted = sorted(
        files, key=lambda x: x[1].get("systemic_risk_score", 0), reverse=True
    )
    systemic_rows: List[Dict[str, Any]] = []
    for path, data in systemic_sorted:
        factor = data.get("missing_test_coverage_factor", 0.5)
        if factor < 0.2:
            test_status = "Likely Covered"
        elif factor > 0.9:
            test_status = "High Risk/Untested"
        else:
            test_status = "Ambiguous"
        systemic_rows.append(
            {
                "file_path": path,
                "fan_in": data.get("fan_in", 0),
                "test_status": test_status,
                "systemic_risk_score": data.get("systemic_risk_score", 0.0),
            }
        )
    tables["systemic"] = systemic_rows

    # 6. Contributors
    contrib_rows: List[Dict[str, Any]] = []
    for email, stats in contributor_data.items():
        name = email.split("@")[0]
        contrib_rows.append(
            {
                "author": name,
                "email": email,
                "total_commits": stats.get("total_commits", 0),
                "lines_added": int(stats.get("lines_added", 0)),
                "efficiency_score": stats.get("efficiency_score", 0.0),
                "risk_score": stats.get("risk_score", 0.0),
            }
        )
    contrib_rows.sort(key=lambda x: x["efficiency_score"], reverse=True)
    tables["contributors"] = contrib_rows

    # 8. Comment‑to‑Code Ratio (if comment_lines is present)
    comment_rows: List[Dict[str, Any]] = []
    for path, data in files:
        loc = data.get("loc", 0)
        comment_lines = data.get("comment_lines", 0)
        total = loc + comment_lines
        ratio = (comment_lines / total) if total > 0 else 0.0
        comment_rows.append(
            {
                "file_path": path,
                "comment_lines": comment_lines,
                "loc": loc,
                "comment_ratio": ratio,
            }
        )
    comment_rows.sort(key=lambda x: x["comment_ratio"], reverse=True)
    tables["comments"] = comment_rows

    # 9. Security keyword matches using the local repo path (if available)
    if isinstance(local_repo_path, str) and local_repo_path:
        try:
            security_data, total_matches = security_keyword_scan(local_repo_path)
            security_rows = [
                {"file_path": row[0], "keyword_matches": row[1]}
                for row in security_data
            ]
            security_rows.sort(key=lambda x: x["keyword_matches"], reverse=True)
            tables["security_keywords"] = {
                "rows": security_rows,
                "total_matches": total_matches,
            }
        except Exception:
            tables["security_keywords"] = {"rows": [], "total_matches": 0}
    else:
        tables["security_keywords"] = {"rows": [], "total_matches": 0}

    # Repo level summary
    tables["summary"] = {
        "overall_technical_debt": repo_stats.get("overall_technical_debt", 0.0),
        "files_analyzed": len(files),
    }

    # NEW FEATURE 1: Code Quality Metrics Dashboard
    total_loc = sum(data.get("loc", 0) for _, data in files)
    avg_complexity = sum(data.get("complexity", 0) for _, data in files) / len(files) if files else 0
    total_churn = sum(data.get("lines_added", 0) + data.get("lines_removed", 0) for _, data in files)
    avg_risk = sum(data.get("risk_score", 0) for _, data in files) / len(files) if files else 0
    tables["code_quality_metrics"] = {
        "total_loc": total_loc,
        "avg_complexity": avg_complexity,
        "total_churn": total_churn,
        "avg_risk_score": avg_risk,
        "total_files": len(files)
    }

    # NEW FEATURE 2: File Change Frequency Analysis
    change_frequency = []
    for path, data in files:
        commit_count = data.get("commit_count", 0)
        churn = data.get("lines_added", 0) + data.get("lines_removed", 0)
        change_frequency.append({
            "file_path": path,
            "commit_count": commit_count,
            "total_churn": churn,
            "avg_churn_per_commit": churn / commit_count if commit_count > 0 else 0
        })
    change_frequency.sort(key=lambda x: x["commit_count"], reverse=True)
    tables["change_frequency"] = change_frequency

    # NEW FEATURE 3: Code Maintainability Index
    maintainability_scores = []
    for path, data in files:
        complexity = data.get("complexity", 1)
        churn = data.get("lines_added", 0) + data.get("lines_removed", 0)
        risk = data.get("risk_score", 0)
        # Maintainability Index: lower complexity, lower churn, lower risk = higher maintainability
        # Normalize to 0-100 scale (100 = most maintainable)
        maintainability = max(0, 100 - (complexity * 0.3 + churn * 0.01 + risk * 0.5))
        maintainability_scores.append({
            "file_path": path,
            "maintainability_index": maintainability,
            "complexity": complexity,
            "churn": churn,
            "risk_score": risk
        })
    maintainability_scores.sort(key=lambda x: x["maintainability_index"])
    tables["maintainability"] = maintainability_scores

    # NEW FEATURE 1: Bus Factor Analysis (for Contributor Analysis)
    bus_factor_data = []
    for path, data in files:
        unique_authors = data.get("unique_author_count", 0)
        bus_factor_data.append({
            "file_path": path,
            "unique_contributors": unique_authors,
            "risk_score": data.get("risk_score", 0),
            "loc": data.get("loc", 0)
        })
    bus_factor_data.sort(key=lambda x: (x["unique_contributors"], -x["risk_score"]))
    tables["bus_factor"] = bus_factor_data

    # NEW FEATURE 2: Contribution Distribution
    total_commits_all = sum(stats.get("total_commits", 0) for stats in contributor_data.values())
    total_lines_all = sum(int(stats.get("lines_added", 0)) for stats in contributor_data.values())
    contrib_distribution = []
    for email, stats in contributor_data.items():
        name = email.split("@")[0]
        commits_pct = (stats.get("total_commits", 0) / total_commits_all * 100) if total_commits_all > 0 else 0
        lines_pct = (int(stats.get("lines_added", 0)) / total_lines_all * 100) if total_lines_all > 0 else 0
        contrib_distribution.append({
            "author": name,
            "commits_percentage": commits_pct,
            "lines_percentage": lines_pct,
            "total_commits": stats.get("total_commits", 0),
            "lines_added": int(stats.get("lines_added", 0))
        })
    contrib_distribution.sort(key=lambda x: x["commits_percentage"], reverse=True)
    tables["contribution_distribution"] = contrib_distribution

    # NEW FEATURE 3: Knowledge Concentration Risk
    knowledge_concentration = []
    for path, data in files:
        unique_authors = data.get("unique_author_count", 0)
        loc = data.get("loc", 0)
        # High risk if file is large but has few contributors
        concentration_risk = (loc / max(unique_authors, 1)) if unique_authors > 0 else loc
        knowledge_concentration.append({
            "file_path": path,
            "loc": loc,
            "unique_contributors": unique_authors,
            "concentration_risk": concentration_risk,
            "risk_score": data.get("risk_score", 0)
        })
    knowledge_concentration.sort(key=lambda x: x["concentration_risk"], reverse=True)
    tables["knowledge_concentration"] = knowledge_concentration

    return tables


def main():
    st.set_page_config(page_title="Git Technical Debt Analyzer", layout="wide")
    st.title("🔍 Git Technical Debt Analyzer")
    st.write(
        "Enter a public GitHub repository URL to run comprehensive technical debt analysis, "
        "security scanning, and AI-powered insights."
    )

    repo_url = st.text_input(
        "GitHub repository URL",
        placeholder="https://github.com/user/repo",
    )

    run_button = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

    if run_button:
        if not repo_url.strip():
            st.error("⚠️ Please enter a valid GitHub repository URL.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with st.spinner("🔄 Cloning repository and running analysis. This may take a few minutes..."):
            status_text.text("Step 1/3: Cloning repository and analyzing code...")
            progress_bar.progress(20)
            
            try:
                # Technical debt analysis
                all_file_data = run_analysis_pipeline(repo_url.strip())
                tables = build_tables_from_data(all_file_data)
            except Exception as e:
                st.error(f"❌ Technical debt analysis failed: {e}")
                st.code(traceback.format_exc())
                return

            status_text.text("Step 2/3: Running security analysis...")
            progress_bar.progress(60)
            
            # Run the standalone security analyzer as well (separate clone and tools)
            security_results: Dict[str, Any] | None = None
            try:
                security_results = run_security_analysis(repo_url.strip(), return_data=True)
            except Exception as e:
                # We keep tech-debt results even if security scan fails
                st.warning(f"⚠️ Security analyzer failed: {e}")

            status_text.text("Step 3/3: Generating AI insights...")
            progress_bar.progress(90)
            
            # Generate AI summaries for each section
            code_ai_summary = None
            contributor_ai_summary = None
            security_ai_summary = None
            
            try:
                # Code Analysis AI Summary
                risk_files = tables.get("risk", [])
                summary = tables.get("summary", {})
                code_ai_summary = generate_code_analysis_summary(
                    risk_files,
                    summary.get("overall_technical_debt", 0.0),
                    summary.get("files_analyzed", 0)
                )
            except Exception as e:
                st.warning(f"⚠️ Code AI summary generation failed: {e}")
            
            # Contributor Analysis AI Summary
            contributor_ai_summary = None
            contrib_data = tables.get("contributors", [])
            if contrib_data and len(contrib_data) > 0:
                try:
                    contributor_ai_summary = generate_contributor_analysis_summary(contrib_data)
                    if not contributor_ai_summary or contributor_ai_summary.startswith("Gemini API not available"):
                        contributor_ai_summary = None
                except Exception as e:
                    st.warning(f"⚠️ Contributor AI summary generation failed: {e}")
                    contributor_ai_summary = None
            
            try:
                # Security Analysis AI Summary
                if security_results:
                    security_ai_summary = generate_security_analysis_summary(
                        security_results.get("findings", []),
                        security_results.get("risk_score", 0),
                        security_results.get("severity_counts", {})
                    )
            except Exception as e:
                st.warning(f"⚠️ Security AI summary generation failed: {e}")
            
            progress_bar.progress(100)
            status_text.text("✅ Analysis complete!")
            st.success("🎉 Analysis completed successfully!")

        # Summary Metrics
        st.markdown("---")
        st.header("📊 Summary Metrics")
        summary = tables.get("summary", {})
        col1, col2, col3, col4 = st.columns(4)
        
        debt_score = summary.get('overall_technical_debt', 0.0)
        col1.metric(
            "Overall Technical Debt",
            f"{debt_score:.2f}",
            help="0-100 scale, lower is better"
        )
        col2.metric("Files Analyzed", summary.get("files_analyzed", 0))
        
        # Security score
        if security_results:
            sec_score = security_results.get("risk_score", 0)
            col3.metric("Security Score", f"{sec_score}/100")
            counts = security_results.get("severity_counts", {})
            col4.metric("Security Findings", sum(counts.values()))
        else:
            col3.metric("Security Score", "N/A")
            col4.metric("Security Findings", "N/A")

        st.markdown("---")

        # Create tabs for the three sections
        tab1, tab2, tab3 = st.tabs(["📊 Code Analysis", "👥 Contributor Analysis", "🛡️ Security Analysis"])

        # ========== TAB 1: CODE ANALYSIS ==========
        with tab1:
            st.header("📊 Code Analysis")
            
            # File Size Summary
            st.subheader("📏 File Size Summary")
            file_size_rows = tables.get("file_size", [])
            st.dataframe(file_size_rows, use_container_width=True)
            if file_size_rows:
                df_size = pd.DataFrame(file_size_rows).sort_values("loc", ascending=False).head(20)
                st.caption("Top 20 largest files by LOC")
                st.bar_chart(df_size.set_index("file_path")["loc"])

            st.markdown("---")

            # Complexity & Change Cost
            st.subheader("⚙️ Complexity & Change Cost")
            complexity_rows = tables.get("complexity_churn", [])
            st.dataframe(complexity_rows, use_container_width=True)
            if complexity_rows:
                df_cc = (
                    pd.DataFrame(complexity_rows)
                    .sort_values("complexity_x_churn", ascending=False)
                    .head(20)
                )
                st.caption("Top 20 files by Complexity × Churn (higher = more costly to maintain)")
                st.bar_chart(df_cc.set_index("file_path")["complexity_x_churn"])

            st.markdown("---")

            # Highest Risk Files
            st.subheader("🔥 Highest‑Risk Files")
            risk_rows = tables.get("risk", [])
            st.dataframe(risk_rows, use_container_width=True)
            if risk_rows:
                df_risk = (
                    pd.DataFrame(risk_rows)
                    .sort_values("risk_score", ascending=False)
                    .head(20)
                )
                st.caption("Top 20 files by technical debt risk score")
                st.bar_chart(df_risk.set_index("file_path")["risk_score"])

            st.markdown("---")

            # Systemic Risk Hotspots
            st.subheader("🏛 Critical Systemic Risk Hotspots")
            systemic_rows = tables.get("systemic", [])
            st.dataframe(systemic_rows, use_container_width=True)
            if systemic_rows:
                df_sys = (
                    pd.DataFrame(systemic_rows)
                    .sort_values("systemic_risk_score", ascending=False)
                    .head(20)
                )
                st.caption("Top 20 files by systemic risk score")
                st.bar_chart(df_sys.set_index("file_path")["systemic_risk_score"])

            st.markdown("---")

            # Comment-to-Code Ratios
            st.subheader("📝 Comment‑to‑Code Ratios")
            comment_rows = tables.get("comments", [])
            st.dataframe(comment_rows, use_container_width=True)
            if comment_rows:
                df_comments = (
                    pd.DataFrame(comment_rows)
                    .sort_values("comment_ratio", ascending=False)
                    .head(20)
                )
                st.caption("Top 20 files by comment‑to‑code ratio (higher = more documented)")
                st.bar_chart(df_comments.set_index("file_path")["comment_ratio"])

            st.markdown("---")

            # NEW FEATURE 1: Code Quality Metrics Dashboard
            st.subheader("📊 Code Quality Metrics Dashboard")
            quality_metrics = tables.get("code_quality_metrics", {})
            if quality_metrics:
                col_q1, col_q2, col_q3, col_q4 = st.columns(4)
                col_q1.metric("Total LOC", f"{quality_metrics.get('total_loc', 0):,}")
                col_q2.metric("Avg Complexity", f"{quality_metrics.get('avg_complexity', 0):.2f}")
                col_q3.metric("Total Churn", f"{quality_metrics.get('total_churn', 0):,}")
                col_q4.metric("Avg Risk Score", f"{quality_metrics.get('avg_risk_score', 0):.2f}")
                
                # Visual representation
                metrics_df = pd.DataFrame({
                    "Metric": ["Total LOC", "Avg Complexity", "Total Churn", "Avg Risk"],
                    "Value": [
                        quality_metrics.get('total_loc', 0) / 1000,  # Normalize for visualization
                        quality_metrics.get('avg_complexity', 0) * 10,
                        quality_metrics.get('total_churn', 0) / 1000,
                        quality_metrics.get('avg_risk_score', 0)
                    ]
                })
                st.bar_chart(metrics_df.set_index("Metric")["Value"])

            st.markdown("---")

            # NEW FEATURE 2: File Change Frequency Analysis
            st.subheader("🔄 File Change Frequency Analysis")
            change_freq = tables.get("change_frequency", [])
            if change_freq:
                st.dataframe(change_freq, use_container_width=True)
                df_cf = pd.DataFrame(change_freq).head(20)
                col_cf1, col_cf2 = st.columns(2)
                with col_cf1:
                    st.caption("Top 20 files by commit count")
                    st.bar_chart(df_cf.set_index("file_path")["commit_count"])
                with col_cf2:
                    st.caption("Top 20 files by total churn")
                    st.bar_chart(df_cf.set_index("file_path")["total_churn"])

            st.markdown("---")

            # NEW FEATURE 3: Code Maintainability Index
            st.subheader("🔧 Code Maintainability Index")
            maintainability = tables.get("maintainability", [])
            if maintainability:
                st.write("Files ranked by maintainability (lower index = harder to maintain)")
                st.dataframe(maintainability, use_container_width=True)
                df_maint = pd.DataFrame(maintainability).head(20)
                st.caption("Top 20 least maintainable files (lowest index)")
                st.bar_chart(df_maint.set_index("file_path")["maintainability_index"])

            st.markdown("---")

            # AI Summary for Code Analysis
            st.subheader("🤖 AI-Powered Code Analysis Summary")
            if code_ai_summary:
                st.markdown(code_ai_summary)
            else:
                st.info("AI analysis not available. Set GEMINI_API_KEY environment variable to enable AI insights.")

        # ========== TAB 2: CONTRIBUTOR ANALYSIS ==========
        with tab2:
            st.header("👥 Contributor Analysis")
            
            # Contributor Efficiency
            st.subheader("👥 Contributor Efficiency")
            contrib_data = tables.get("contributors", [])
            if contrib_data:
                st.dataframe(contrib_data, use_container_width=True)
                df_contrib = pd.DataFrame(contrib_data)
                
                col_contrib1, col_contrib2 = st.columns(2)
                with col_contrib1:
                    st.subheader("Efficiency Score Distribution")
                    st.bar_chart(df_contrib.set_index("author")["efficiency_score"])
                with col_contrib2:
                    st.subheader("Total Commits Distribution")
                    st.bar_chart(df_contrib.set_index("author")["total_commits"])
                
                st.markdown("---")
                
                col_contrib3, col_contrib4 = st.columns(2)
                with col_contrib3:
                    st.subheader("Lines Added Distribution")
                    st.bar_chart(df_contrib.set_index("author")["lines_added"])
                with col_contrib4:
                    st.subheader("Risk Contribution Distribution")
                    st.bar_chart(df_contrib.set_index("author")["risk_score"])
            else:
                st.info("No contributor data available.")

            st.markdown("---")

            # NEW FEATURE 1: Bus Factor Analysis
            st.subheader("🚌 Bus Factor Analysis")
            st.write("Identifies files with low contributor diversity (high bus factor risk)")
            bus_factor_data = tables.get("bus_factor", [])
            if bus_factor_data:
                # Filter files with low contributor count and high risk
                high_risk_bus = [f for f in bus_factor_data if f["unique_contributors"] <= 2 and f["risk_score"] > 50]
                if high_risk_bus:
                    st.warning(f"⚠️ Found {len(high_risk_bus)} files with high bus factor risk (≤2 contributors, risk >50)")
                    df_bus = pd.DataFrame(high_risk_bus[:20])
                    st.dataframe(df_bus, use_container_width=True)
                    col_bus1, col_bus2 = st.columns(2)
                    with col_bus1:
                        st.bar_chart(df_bus.set_index("file_path")["unique_contributors"])
                    with col_bus2:
                        st.bar_chart(df_bus.set_index("file_path")["risk_score"])
                else:
                    st.info("✅ No high bus factor risks detected.")
                
                # Overall bus factor distribution
                df_all_bus = pd.DataFrame(bus_factor_data)
                st.caption("Distribution of contributors per file")
                st.bar_chart(df_all_bus.set_index("file_path")["unique_contributors"])

            st.markdown("---")

            # NEW FEATURE 2: Contribution Distribution
            st.subheader("📊 Contribution Distribution")
            contrib_dist = tables.get("contribution_distribution", [])
            if contrib_dist:
                st.dataframe(contrib_dist, use_container_width=True)
                df_dist = pd.DataFrame(contrib_dist)
                col_dist1, col_dist2 = st.columns(2)
                with col_dist1:
                    st.caption("Commits Distribution (%)")
                    st.bar_chart(df_dist.set_index("author")["commits_percentage"])
                with col_dist2:
                    st.caption("Lines Added Distribution (%)")
                    st.bar_chart(df_dist.set_index("author")["lines_percentage"])

            st.markdown("---")

            # NEW FEATURE 3: Knowledge Concentration Risk
            st.subheader("🧠 Knowledge Concentration Risk")
            st.write("Files where knowledge is concentrated in few contributors (high risk)")
            knowledge_conc = tables.get("knowledge_concentration", [])
            if knowledge_conc:
                high_conc = [f for f in knowledge_conc if f["concentration_risk"] > 500 and f["unique_contributors"] <= 2]
                if high_conc:
                    st.warning(f"⚠️ Found {len(high_conc)} files with high knowledge concentration risk")
                    df_conc = pd.DataFrame(high_conc[:20])
                    st.dataframe(df_conc, use_container_width=True)
                    col_conc1, col_conc2 = st.columns(2)
                    with col_conc1:
                        st.bar_chart(df_conc.set_index("file_path")["concentration_risk"])
                    with col_conc2:
                        st.bar_chart(df_conc.set_index("file_path")["unique_contributors"])
                else:
                    st.info("✅ Knowledge is well distributed across contributors.")
                
                # Overall distribution
                df_all_conc = pd.DataFrame(knowledge_conc).head(20)
                st.caption("Top 20 files by knowledge concentration risk")
                st.bar_chart(df_all_conc.set_index("file_path")["concentration_risk"])

            st.markdown("---")

            # AI Summary for Contributor Analysis
            st.subheader("🤖 AI-Powered Contributor Analysis Summary")
            if contributor_ai_summary:
                st.markdown(contributor_ai_summary)
            elif not contrib_data or len(contrib_data) == 0:
                st.info("No contributor data available for AI analysis.")
            else:
                st.info("AI analysis not available. Set GEMINI_API_KEY environment variable to enable AI insights.")

        # ========== TAB 3: SECURITY ANALYSIS ==========
        with tab3:
            st.header("🛡️ Security Analysis")
            
            # Security Keyword Hotspots
            st.subheader("🔐 Security Keyword Hotspots")
            sec = tables.get("security_keywords", {"rows": [], "total_matches": 0})
            st.caption(f"Total keyword matches across repository: {sec.get('total_matches', 0)}")
            sec_rows = sec.get("rows", [])
            if sec_rows:
                st.dataframe(sec_rows, use_container_width=True)
                df_sec = pd.DataFrame(sec_rows).head(20)
                st.bar_chart(df_sec.set_index("file_path")["keyword_matches"])
            else:
                st.info("No security keyword matches found.")

            st.markdown("---")

            # Security Analyzer Results
            st.subheader("🛡️ Security Analyzer Results")
            st.write(
                "Results from custom secret scanning, Bandit SAST, and Safety dependency checks."
            )

            if security_results:
                s = security_results
                sc1, sc2 = st.columns(2)
                sec_score = s.get("risk_score", 0)
                sc1.metric("Security Risk Score (0‑100, higher is better)", f"{sec_score}")

                counts = s.get("severity_counts", {})
                sc2.metric("Total Findings", sum(counts.values()))

                st.markdown("---")

                st.subheader("Severity Breakdown")
                sev_rows = [
                    {"severity": "HIGH", "count": counts.get("HIGH", 0)},
                    {"severity": "MEDIUM", "count": counts.get("MEDIUM", 0)},
                    {"severity": "LOW", "count": counts.get("LOW", 0)},
                    {"severity": "INFO", "count": counts.get("INFO", 0)},
                ]
                st.dataframe(sev_rows, use_container_width=True)
                
                # Severity chart
                sev_df = pd.DataFrame(sev_rows)
                st.bar_chart(sev_df.set_index("severity")["count"])

                st.markdown("---")

                findings = s.get("findings", [])
                if findings:
                    st.subheader("📋 Detailed Security Findings")
                    st.dataframe(findings, use_container_width=True)
                else:
                    st.info("✅ No security findings detected by the security analyzer.")
            else:
                st.info("Security analyzer results are not available for this run.")

            st.markdown("---")

            # NEW FEATURE 1: Security Risk Distribution
            st.subheader("📈 Security Risk Distribution")
            if security_results:
                s = security_results
                sec_score = s.get("risk_score", 0)
                counts = s.get("severity_counts", {})
                
                # Risk level categorization
                if sec_score >= 90:
                    risk_level = "🟢 Excellent"
                    risk_color = "green"
                elif sec_score >= 70:
                    risk_level = "🟡 Good"
                    risk_color = "yellow"
                elif sec_score >= 50:
                    risk_level = "🟠 Needs Improvement"
                    risk_color = "orange"
                else:
                    risk_level = "🔴 Critical"
                    risk_color = "red"
                
                col_risk1, col_risk2 = st.columns(2)
                with col_risk1:
                    st.metric("Security Risk Level", risk_level)
                    st.metric("Risk Score", f"{sec_score}/100")
                with col_risk2:
                    st.metric("Total Findings", sum(counts.values()))
                    st.metric("High Severity Issues", counts.get("HIGH", 0))
                
                # Risk distribution pie chart data
                if sum(counts.values()) > 0:
                    severity_data = {
                        "HIGH": counts.get("HIGH", 0),
                        "MEDIUM": counts.get("MEDIUM", 0),
                        "LOW": counts.get("LOW", 0),
                        "INFO": counts.get("INFO", 0)
                    }
                    df_severity = pd.DataFrame(list(severity_data.items()), columns=["Severity", "Count"])
                    st.bar_chart(df_severity.set_index("Severity")["Count"])

            st.markdown("---")

            # NEW FEATURE 2: Vulnerability Severity Breakdown
            st.subheader("🎯 Vulnerability Severity Breakdown")
            if security_results:
                s = security_results
                findings = s.get("findings", [])
                if findings:
                    # Group findings by severity
                    severity_groups = {"HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}
                    for finding in findings:
                        sev = finding.get("severity", "INFO").upper()
                        if sev in severity_groups:
                            severity_groups[sev].append(finding)
                    
                    col_vul1, col_vul2, col_vul3, col_vul4 = st.columns(4)
                    with col_vul1:
                        st.metric("🔴 HIGH", len(severity_groups["HIGH"]))
                    with col_vul2:
                        st.metric("🟡 MEDIUM", len(severity_groups["MEDIUM"]))
                    with col_vul3:
                        st.metric("🔵 LOW", len(severity_groups["LOW"]))
                    with col_vul4:
                        st.metric("🟢 INFO", len(severity_groups["INFO"]))
                    
                    # Show top vulnerabilities by severity
                    if severity_groups["HIGH"]:
                        st.write("**Top High Severity Issues:**")
                        high_df = pd.DataFrame(severity_groups["HIGH"][:10])
                        st.dataframe(high_df[["code", "msg", "file", "line"]], use_container_width=True)
                else:
                    st.success("✅ No vulnerabilities detected!")

            st.markdown("---")

            # NEW FEATURE 3: Security Compliance Score
            st.subheader("✅ Security Compliance Score")
            if security_results:
                s = security_results
                findings = s.get("findings", [])
                counts = s.get("severity_counts", {})
                
                # Calculate compliance score (0-100, 100 = fully compliant)
                total_findings = sum(counts.values())
                high_count = counts.get("HIGH", 0)
                medium_count = counts.get("MEDIUM", 0)
                
                # Compliance calculation: penalize HIGH and MEDIUM findings
                compliance_score = max(0, 100 - (high_count * 10 + medium_count * 5))
                
                col_comp1, col_comp2, col_comp3 = st.columns(3)
                col_comp1.metric("Compliance Score", f"{compliance_score:.1f}/100")
                col_comp2.metric("Critical Issues", high_count)
                col_comp3.metric("Total Violations", total_findings)
                
                # Compliance status
                if compliance_score >= 90:
                    st.success("🟢 **Excellent Compliance** - Security posture is strong")
                elif compliance_score >= 70:
                    st.warning("🟡 **Good Compliance** - Some improvements needed")
                elif compliance_score >= 50:
                    st.warning("🟠 **Fair Compliance** - Significant improvements required")
                else:
                    st.error("🔴 **Poor Compliance** - Immediate action required")
                
                # Recommendations based on score
                if compliance_score < 70:
                    st.info("💡 **Recommendations:** Focus on fixing HIGH and MEDIUM severity issues to improve compliance score.")

            st.markdown("---")

            # AI Summary for Security Analysis
            st.subheader("🤖 AI-Powered Security Analysis Summary")
            if security_ai_summary:
                st.markdown(security_ai_summary)
            else:
                st.info("AI analysis not available. Set GEMINI_API_KEY environment variable to enable AI insights.")

        # Footer
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; padding: 2rem; color: #666; font-style: italic; margin-top: 3rem; border-top: 2px solid #e0e0e0;">
            <p style="font-size: 1.1em; margin: 0;">Developed with ❤️ by <strong>Viraj & Visha</strong></p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
