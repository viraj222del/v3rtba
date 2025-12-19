import os
from typing import Dict, Any, List

# Import the Google GenAI SDK
from google import genai
from google.genai.errors import APIError

# --- ANSI Color Codes for reporting status ---
COLOR_END = '\033[0m'
COLOR_RED = '\033[91m'
COLOR_BOLD = '\033[1m'

# --- Configuration ---
import streamlit as st

# Get API key from Streamlit secrets
try:
    GEMINI_API_KEY = st.secrets["gemini"]["api_key"]
    client = genai.Client(api_key=GEMINI_API_KEY)
    MODEL_NAME = 'gemini-2.5-flash'
except Exception as e:
    print(f"Gemini client initialization error: {e}")
    client = None
    st.warning("Gemini API key not found in Streamlit secrets. AI features will be disabled.")

def generate_refactor_summary(top_risk_data: List[Dict[str, Any]]) -> str:
    """
    Calls the Gemini API to generate a human-readable summary 
    and actionable recommendations for the highest-risk files.
    """
    if not client:
        return f"Gemini API not available. Set the {COLOR_BOLD}GEMINI_API_KEY{COLOR_END} environment variable."

    # Format the data into a clean, structured string for the prompt
    data_points = "\n".join([
        f"- File: {d['path']}, Risk Score: {d['risk_score']:.2f}, Main Factor: {d.get('main_factor', 'N/A')}, Complexity: {d.get('complexity', 0)}"
        for d in top_risk_data
    ])
    
    # --- The Core Prompt ---
    prompt = f"""
    Analyze the following top high-risk files (Risk Score 0-100, 100 is max debt).
    
    Data:
    {data_points}
    
    Generate a concise, 4-point summary suitable for a developer report:
    1. Overall highest-risk concern and why (mention the top file/score).
    2. A primary refactoring recommendation (e.g., reduce complexity, split ownership).
    3. The most complex file that needs immediate attention.
    4. A positive statement summarizing the low-risk areas or overall health.
    
    Format the output purely as a markdown list without any introduction or conclusion.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text
        
    except APIError as e:
        return f"Gemini API Error: Failed to generate summary. ({e})"
    except Exception as e:
        return f"An unexpected error occurred during API call: {e}"


def generate_code_analysis_summary(file_data: List[Dict[str, Any]], overall_debt: float, total_files: int) -> str:
    """Generate comprehensive code analysis summary with recommendations, suggestions, scalability, and file summaries."""
    if not client:
        return f"Gemini API not available. Set the {COLOR_BOLD}GEMINI_API_KEY{COLOR_END} environment variable."
    
    # Prepare file summaries (top 10)
    file_summaries = "\n".join([
        f"- {d.get('path', 'N/A')}: Risk={d.get('risk_score', 0):.2f}, Complexity={d.get('complexity', 0)}, Factor={d.get('main_factor', 'N/A')}"
        for d in file_data[:10]
    ])
    
    prompt = f"""
    Analyze this codebase with the following metrics:
    - Overall Technical Debt Score: {overall_debt:.2f}/100 (lower is better)
    - Total Files Analyzed: {total_files}
    - Top Risk Files:
    {file_summaries}
    
    Generate a comprehensive analysis in markdown format with these sections:
    
    ## 📋 Short Summary
    Provide a 2-3 sentence overview of the codebase health.
    
    ## 🔍 File Analysis Summary
    Brief summary of the top 5 most critical files and their main issues.
    
    ## 💡 Recommendations
    List 3-5 specific, actionable refactoring recommendations prioritized by impact.
    
    ## 🚀 Suggestions
    Provide 3-5 improvement suggestions for code quality, maintainability, and best practices.
    
    ## 📈 Scalability Analysis
    Assess whether this codebase can scale effectively. Discuss:
    - Architecture concerns
    - Performance bottlenecks
    - Maintainability at scale
    - Team collaboration challenges
    
    ## 🔒 Security Considerations
    Provide 3-5 security-related suggestions based on the code structure and complexity.
    
    Format as clean markdown with proper headers and bullet points.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text
    except APIError as e:
        return f"Gemini API Error: Failed to generate code analysis summary. ({e})"
    except Exception as e:
        return f"An unexpected error occurred during API call: {e}"


def generate_contributor_analysis_summary(contributor_data: List[Dict[str, Any]]) -> str:
    """Generate contributor analysis summary with recommendations and suggestions."""
    if not client:
        return f"Gemini API not available. Set the {COLOR_BOLD}GEMINI_API_KEY{COLOR_END} environment variable."
    
    if not contributor_data or len(contributor_data) == 0:
        return "No contributor data available for analysis."
    
    # Prepare contributor summaries
    contrib_summaries = "\n".join([
        f"- {d.get('author', 'N/A')}: Commits={d.get('total_commits', 0)}, Lines Added={d.get('lines_added', 0)}, Efficiency={d.get('efficiency_score', 0):.3f}, Risk Contribution={d.get('risk_score', 0):.2f}"
        for d in contributor_data[:10]
    ])
    
    if not contrib_summaries.strip():
        return "Contributor data is empty or invalid."
    
    prompt = f"""
    Analyze the following contributor metrics:
    
    Contributors:
    {contrib_summaries}
    
    Generate a comprehensive contributor analysis in markdown format with these sections:
    
    ## 📋 Summary
    Provide a 2-3 sentence overview of team contribution patterns and efficiency.
    
    ## 👥 Contributor Insights
    Identify key contributors, their strengths, and contribution patterns.
    
    ## 💡 Recommendations
    Provide 3-5 recommendations for:
    - Knowledge distribution
    - Code ownership balance
    - Team efficiency improvements
    - Risk mitigation strategies
    
    ## 🚀 Suggestions
    Offer 3-5 suggestions for:
    - Improving collaboration
    - Reducing bus factor
    - Mentoring opportunities
    - Code review practices
    
    ## 📈 Team Scalability
    Assess whether the current team structure can scale. Discuss:
    - Knowledge concentration risks
    - Onboarding challenges
    - Collaboration bottlenecks
    
    Format as clean markdown with proper headers and bullet points.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text
    except APIError as e:
        return f"Gemini API Error: Failed to generate contributor analysis summary. ({e})"
    except Exception as e:
        return f"An unexpected error occurred during API call: {e}"


def generate_security_analysis_summary(security_findings: List[Dict[str, Any]], risk_score: int, severity_counts: Dict[str, int]) -> str:
    """Generate security analysis summary with recommendations and security suggestions."""
    if not client:
        return f"Gemini API not available. Set the {COLOR_BOLD}GEMINI_API_KEY{COLOR_END} environment variable."
    
    # Prepare top findings summary
    top_findings = security_findings[:15]  # Top 15 findings
    findings_summary = "\n".join([
        f"- {f.get('severity', 'N/A')}: {f.get('msg', 'N/A')} in {f.get('file', 'N/A')}:{f.get('line', 0)}"
        for f in top_findings
    ])
    
    prompt = f"""
    Analyze the following security scan results:
    
    Security Risk Score: {risk_score}/100 (higher is better)
    Severity Breakdown:
    - HIGH: {severity_counts.get('HIGH', 0)}
    - MEDIUM: {severity_counts.get('MEDIUM', 0)}
    - LOW: {severity_counts.get('LOW', 0)}
    - INFO: {severity_counts.get('INFO', 0)}
    
    Top Security Findings:
    {findings_summary}
    
    Generate a comprehensive security analysis in markdown format with these sections:
    
    ## 📋 Security Summary
    Provide a 2-3 sentence overview of the security posture and risk level.
    
    ## 🔒 Critical Security Issues
    Summarize the top 5 most critical security findings and their potential impact.
    
    ## 💡 Security Recommendations
    Provide 5-7 prioritized security recommendations:
    - Immediate actions required
    - Short-term fixes
    - Long-term security improvements
    
    ## 🛡️ Security Suggestions
    Offer 5-7 proactive security suggestions:
    - Best practices to implement
    - Security tools to integrate
    - Code review focus areas
    - Security training needs
    
    ## 📈 Security Scalability
    Assess security posture for scaling:
    - Security monitoring needs
    - Compliance considerations
    - Security automation opportunities
    - Risk management strategies
    
    Format as clean markdown with proper headers and bullet points.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text
    except APIError as e:
        return f"Gemini API Error: Failed to generate security analysis summary. ({e})"
    except Exception as e:

        return f"An unexpected error occurred during API call: {e}"
