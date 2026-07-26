"""
AI-Powered Candidate Screening Platform — Streamlit entrypoint.

Tabs: Upload & configure -> Ranked dashboard -> Test results -> Scheduling.
Each expensive step is gated behind an explicit button so reruns stay cheap.
"""

from __future__ import annotations

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # load .env so SMTP_USER / SMTP_APP_PASSWORD are available

from src.stage1_pretest.orchestrator import run_full_pipeline
from src.stage2_posttest.scheduling.calendar import create_interview_event
from src.stage1_pretest.emailing.sender import send_test_link_email
import datetime
import time
import pandas as pd
from src.common.validators import (
    get_xlsx_sheet_names,
    validate_and_normalize_csv,
    validate_test_results_csv,
)

# Read SMTP credentials from .env (empty string if not set)
_ENV_SMTP_USER = os.getenv("SMTP_USER", "")
_ENV_SMTP_PASS = os.getenv("SMTP_APP_PASSWORD", "")

st.set_page_config(
    page_title="AI Screening Platform",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Session state bootstrap -------------------------------------------------
for key, default in [
    ("candidates_df", None),
    ("upload_summary", None),
    ("job_description", ""),
    ("last_upload_name", None),
    ("test_results_df", None),
    ("ranked_df", None),
    ("final_ranked_df", None),
    ("shortlist_n", 5),
    ("final_shortlist_n", 3),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Custom CSS theme ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* Global font */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* App background */
.stApp {
    background: linear-gradient(135deg, #060612 0%, #0D0D1F 40%, #080812 100%);
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(255,255,255,0.04);
    border-radius: 14px;
    padding: 6px;
    border: 1px solid rgba(255,255,255,0.07);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    padding: 10px 22px;
    font-weight: 600;
    font-size: 14px;
    color: rgba(255,255,255,0.55);
    transition: all 0.25s ease;
    border: none;
    background: transparent;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #7C3AED, #2563EB) !important;
    color: #fff !important;
    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.45);
}
.stTabs [data-baseweb="tab"]:hover {
    color: #fff;
    background: rgba(255,255,255,0.07);
}

/* ── Primary buttons ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #7C3AED, #2563EB) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: 0.3px;
    box-shadow: 0 4px 20px rgba(124,58,237,0.4);
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(124,58,237,0.6) !important;
}

/* ── Secondary buttons ── */
.stButton > button:not([kind="primary"]) {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    background: rgba(255,255,255,0.05) !important;
    color: rgba(255,255,255,0.85) !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
.stButton > button:not([kind="primary"]):hover {
    background: rgba(255,255,255,0.1) !important;
    border-color: rgba(124,58,237,0.5) !important;
}

/* ── Form / text inputs ── */
.stTextInput > div > div, .stTextArea > div > div {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    background: rgba(255,255,255,0.04) !important;
    transition: border-color 0.2s ease;
}
.stTextInput > div > div:focus-within, .stTextArea > div > div:focus-within {
    border-color: rgba(124,58,237,0.6) !important;
    box-shadow: 0 0 0 3px rgba(124,58,237,0.15);
}

/* ── Subheaders ── */
h2, h3 {
    font-weight: 700 !important;
    letter-spacing: -0.3px;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 18px 22px;
    transition: all 0.2s ease;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(124,58,237,0.4);
    background: rgba(124,58,237,0.08);
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.07) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border-radius: 14px !important;
}
[data-testid="stFileUploadDropzone"] {
    border: 2px dashed rgba(124,58,237,0.4) !important;
    border-radius: 14px !important;
    background: rgba(124,58,237,0.05) !important;
    transition: all 0.2s ease;
}
[data-testid="stFileUploadDropzone"]:hover {
    border-color: rgba(124,58,237,0.7) !important;
    background: rgba(124,58,237,0.1) !important;
}

/* ── Info / success / warning / error boxes ── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: none !important;
}

/* ── Divider ── */
hr {
    border-color: rgba(255,255,255,0.07) !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-testid="stThumbValue"] {
    background: linear-gradient(135deg, #7C3AED, #2563EB);
    color: white;
    border-radius: 6px;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    border-radius: 10px !important;
    border: 1px solid rgba(124,58,237,0.4) !important;
    background: rgba(124,58,237,0.1) !important;
    color: #A78BFA !important;
    font-weight: 600 !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: rgba(124,58,237,0.2) !important;
    border-color: rgba(124,58,237,0.7) !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.02) !important;
}

/* ── Select box ── */
[data-testid="stSelectbox"] > div > div {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    background: rgba(255,255,255,0.04) !important;
}

/* ── Date / time inputs ── */
[data-testid="stDateInput"] > div, [data-testid="stTimeInput"] > div {
    border-radius: 10px !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] p {
    color: #A78BFA !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #7C3AED, #2563EB) !important;
    border-radius: 99px;
}
</style>
""", unsafe_allow_html=True)

# ── Hero header ───────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    background: linear-gradient(135deg, rgba(124,58,237,0.15) 0%, rgba(37,99,235,0.1) 100%);
    border: 1px solid rgba(124,58,237,0.25);
    border-radius: 20px;
    padding: 36px 40px 30px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
">
    <div style="
        position: absolute; top: -60px; right: -60px;
        width: 200px; height: 200px;
        background: radial-gradient(circle, rgba(124,58,237,0.3) 0%, transparent 70%);
        pointer-events: none;
    "></div>
    <div style="
        position: absolute; bottom: -40px; left: 20%;
        width: 150px; height: 150px;
        background: radial-gradient(circle, rgba(37,99,235,0.2) 0%, transparent 70%);
        pointer-events: none;
    "></div>
    <div style="display:flex; align-items:center; gap:16px; margin-bottom:10px;">
        <div style="
            background: linear-gradient(135deg, #7C3AED, #2563EB);
            border-radius: 14px; padding: 12px; font-size: 28px;
            box-shadow: 0 4px 20px rgba(124,58,237,0.5);
        ">🚀</div>
        <div>
            <div style="font-size:11px; font-weight:600; letter-spacing:2px; color:#A78BFA; text-transform:uppercase; margin-bottom:4px;">myNachiketa • GTM Engineering</div>
            <h1 style="margin:0; font-size:28px; font-weight:800; background: linear-gradient(135deg, #fff 30%, #A78BFA); -webkit-background-clip:text; -webkit-text-fill-color:transparent; line-height:1.2;">AI Candidate Screening Platform</h1>
        </div>
    </div>
    <p style="margin:0; color:rgba(255,255,255,0.5); font-size:14px; max-width:600px; line-height:1.6;">
        End-to-end automated recruitment pipeline — AI resume evaluation,
        GitHub analysis, pre-test shortlisting, and post-test final ranking.
    </p>
    <div style="display:flex; gap:20px; margin-top:20px; flex-wrap:wrap;">
        <div style="background:rgba(124,58,237,0.15); border:1px solid rgba(124,58,237,0.3); border-radius:8px; padding:8px 16px; font-size:12px; font-weight:600; color:#A78BFA;">⚡ Groq LLM</div>
        <div style="background:rgba(37,99,235,0.15); border:1px solid rgba(37,99,235,0.3); border-radius:8px; padding:8px 16px; font-size:12px; font-weight:600; color:#60A5FA;">🐙 GitHub Analysis</div>
        <div style="background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:8px 16px; font-size:12px; font-weight:600; color:#34D399;">📅 Google Calendar</div>
        <div style="background:rgba(245,158,11,0.15); border:1px solid rgba(245,158,11,0.3); border-radius:8px; padding:8px 16px; font-size:12px; font-weight:600; color:#FBBF24;">✉️ Gmail SMTP</div>
    </div>
</div>
""", unsafe_allow_html=True)

tab_upload, tab_dashboard, tab_tests, tab_schedule = st.tabs(
    ["📁  Upload & configure", "📊  Ranked dashboard", "📝  Test results", "📅  Scheduling"]
)

# --- Tab 1: Upload & configure ------------------------------------------------
with tab_upload:
    st.subheader("1. Upload candidate dataset")
    uploaded_file = st.file_uploader(
        "Candidate CSV / Excel (name, email, github_profile, resume_link, ...)",
        type=["csv", "xlsx"],
        key="candidate_csv_uploader",
    )

    # Re-validate whenever a new/different file is dropped in, not on every rerun.
    if uploaded_file is not None:
        file_identity = f"{uploaded_file.name}:{uploaded_file.size}"
        if file_identity != st.session_state["last_upload_name"]:
            file_bytes = uploaded_file.getvalue()
            sheet_names = get_xlsx_sheet_names(file_bytes)  # [] for CSV

            # --- Determine which sheet holds candidate data ---
            # Exact sheet names from the uploaded Excel file.
            CANDIDATE_SHEET = "Response"
            TEST_SHEET = "Test Result"

            candidate_sheet = 0  # default: first sheet (for CSV or unknown xlsx)
            test_sheet = None

            if sheet_names:
                # Use exact match first, fall back to first/second sheet
                candidate_sheet = (
                    CANDIDATE_SHEET if CANDIDATE_SHEET in sheet_names else sheet_names[0]
                )
                # Pick test sheet: exact match preferred, else any other sheet
                if TEST_SHEET in sheet_names and TEST_SHEET != candidate_sheet:
                    test_sheet = TEST_SHEET
                elif len(sheet_names) > 1:
                    # fallback: any sheet that isn't the candidate sheet
                    test_sheet = next(
                        (s for s in sheet_names if s != candidate_sheet), None
                    )

                # Show the user which sheets were detected
                sheet_info = f"\U0001f4cb Sheets found: {', '.join(sheet_names)}  "
                sheet_info += f"| Candidates \u2192 **{candidate_sheet}**"
                if test_sheet:
                    sheet_info += f"  | Test results \u2192 **{test_sheet}** (auto-loaded)"
                st.info(sheet_info)

            # --- Load candidate sheet ---
            result = validate_and_normalize_csv(
                file_bytes, sheet_name=candidate_sheet
            )
            st.session_state["last_upload_name"] = file_identity
            if result.ok:
                st.session_state["candidates_df"] = result.dataframe
                st.session_state["upload_summary"] = result
            else:
                st.session_state["candidates_df"] = None
                st.session_state["upload_summary"] = result

            # --- Auto-load test results sheet if found ---
            if test_sheet:
                try:
                    test_result = validate_test_results_csv(
                        file_bytes, sheet_name=test_sheet
                    )
                    if test_result.ok:
                        st.session_state["test_results_df"] = test_result.dataframe
                        st.success(
                            f"✅ Test results auto-loaded from sheet '{test_sheet}': "
                            + test_result.summary_text()
                        )
                    else:
                        st.warning(
                            f"Sheet '{test_sheet}' found but missing required columns: "
                            + ", ".join(test_result.missing_required_columns)
                        )
                except Exception as e:
                    st.warning(f"Could not load test-results sheet '{test_sheet}': {e}")

    summary = st.session_state["upload_summary"]
    if summary is not None:
        if not summary.ok:
            st.error(
                "Missing required column(s): "
                + ", ".join(summary.missing_required_columns)
            )
        else:
            st.success(summary.summary_text())
            if summary.row_errors:
                with st.expander(f"{len(summary.row_errors)} row(s) flagged — details"):
                    flagged = summary.dataframe[summary.dataframe["_row_status"] == "flagged"]
                    st.dataframe(
                        flagged[["name", "email", "_row_issues"]]
                        if "name" in flagged.columns
                        else flagged
                    )
            
            with st.expander("Preview Candidate Data", expanded=False):
                st.dataframe(st.session_state["candidates_df"], width="stretch")

    st.subheader("2. Job description")
    with st.form("jd_form"):
        jd_input = st.text_area(
            "Paste the job description to evaluate candidates against",
            value=st.session_state["job_description"],
            height=180,
        )
        saved = st.form_submit_button("Save Job Description")
        if saved:
            st.session_state["job_description"] = jd_input
            st.success("Job description saved!")

    st.subheader("3. Run evaluation")
    run_disabled = st.session_state["candidates_df"] is None or not st.session_state[
        "job_description"
    ].strip()
    if st.button("Run AI evaluation", disabled=run_disabled, type="primary"):
        _start_time = time.time()
        st.session_state["ranked_df"] = None

        # Stage 1: pre-test shortlisting. Deliberately does NOT merge test
        # scores here — resume_score + github_score + cgpa only, even if
        # test_la/test_code already exist on the uploaded sheet.
        candidates_only_df = st.session_state["candidates_df"]

        # Setup progress indicators
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        def progress_callback(msg: str, pct: float):
            status_text.text(msg)
            progress_bar.progress(pct)
            
        with st.spinner("Initializing AI Orchestrator..."):
            ranked_df, error = run_full_pipeline(
                candidates_only_df, 
                st.session_state["job_description"], 
                progress_callback=progress_callback
            )
            
        if error:
            st.error(error)
        else:
            status_text.text("Evaluation complete!")
            progress_bar.progress(1.0)
            st.session_state["ranked_df"] = ranked_df
            _elapsed = time.time() - _start_time
            st.success(f"Successfully ranked candidates in {_elapsed:.1f} seconds! Head over to the 'Ranked dashboard' tab to view results.")

    if run_disabled:
        st.caption("Upload a valid CSV/Excel and enter a job description to enable this.")

# --- Tab 2: Ranked dashboard ---------------------------------------------------
with tab_dashboard:
    ranked_df = st.session_state["ranked_df"]

    if st.session_state["candidates_df"] is None:
        st.info("⬅️ Go to **Upload & configure** tab to upload a candidate dataset first.")
    elif ranked_df is None:
        st.info("⬅️ Go to **Upload & configure** tab and click **Run AI evaluation** to rank candidates.")
    else:
        total = len(ranked_df)

        # ── STEP 1: Full leaderboard + shortlist selector ────────────────────
        st.subheader("📊 Step 1 — Ranked Leaderboard")

        display_cols = [c for c in [
            "pre_test_rank", "pre_test_score", "name", "email",
            "resume_score", "github_score", "cgpa",
            "resume_score_reason", "github_score_reason",
            "resume_eval_status", "github_eval_status",
        ] if c in ranked_df.columns]
        st.dataframe(ranked_df[display_cols], width="stretch")

        col_dl, col_space = st.columns([1, 3])
        with col_dl:
            csv_data = ranked_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_data,
                file_name="ranked_candidates.csv",
                mime="text/csv",
            )

        st.divider()

        # ── Shortlist selector ───────────────────────────────────────────────
        st.subheader("🎯 How many candidates to shortlist for this round?")
        top_n = st.slider(
            "Select top N candidates",
            min_value=1,
            max_value=total,
            value=min(5, total),
            key="shortlist_n",
            help="Only these candidates will be shown below and emailed.",
        )
        shortlisted = ranked_df.head(top_n)

        st.caption(f"✅ **{top_n} candidates shortlisted** (Rank 1 – {top_n})")

        shortlist_display_cols = [c for c in [
            "pre_test_rank", "pre_test_score", "name", "email", "cgpa",
        ] if c in shortlisted.columns]
        st.dataframe(
            shortlisted[shortlist_display_cols].reset_index(drop=True),
            width="stretch",
            hide_index=True,
        )

        # ── STEP 2: Send test emails to shortlisted candidates ───────────────
        st.divider()
        st.subheader(f"✉️ Step 2 — Send Test Link to Top {top_n} Candidates")

        with st.form("email_form"):
            sender_email = st.text_input(
                "Your Gmail Address",
                value=_ENV_SMTP_USER,
                placeholder="you@gmail.com",
            )

            with st.expander("📝 Customize Email Body", expanded=False):
                email_body_template = st.text_area(
                    "Email Template (use {name} for candidate's name)",
                    value="Hello {name},\n\nCongratulations! Based on our initial review of your resume and GitHub profile, you have been shortlisted for the next round of our hiring process.\n\nPlease complete the following coding assessment within the next 48 hours:\nhttps://hackerrank.com/test-link\n\nBest of luck!\nThe Hiring Team",
                    height=250,
                )

            st.markdown(
                f"**Preview:** This will send **{top_n} email(s)** to the following candidates:"
            )
            for _, row in shortlisted.iterrows():
                rank  = row.get("pre_test_rank", "?")
                name  = row.get("name", "Candidate")
                email = row.get("email", "(no email)")
                score = row.get("pre_test_score", 0)
                st.markdown(f"- Rank **{rank}** — {name} &nbsp;|&nbsp; `{email}` &nbsp;|&nbsp; Score: **{score:.1f}**")

            submit_email = st.form_submit_button(
                f"🚀 Send Test Link to {top_n} Candidates", type="primary"
            )

            if submit_email:
                if not sender_email or not _ENV_SMTP_PASS or not email_body_template:
                    st.error("Please fill in your Gmail address and Email Template. Ensure SMTP_APP_PASSWORD is set in your .env file.")
                else:
                    _start_time = time.time()
                    success_count = 0
                    fail_names = []
                    progress_bar = st.progress(0.0)

                    import concurrent.futures

                    completed_count = 0
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        future_to_name = {}
                        for _, row in shortlisted.iterrows():
                            c_name  = row.get("name", "Candidate")
                            c_email = row.get("email", "")

                            if c_email:
                                future = executor.submit(
                                    send_test_link_email,
                                    c_email, c_name, email_body_template, sender_email, _ENV_SMTP_PASS
                                )
                                future_to_name[future] = c_name
                            else:
                                fail_names.append(c_name)
                                completed_count += 1
                                progress_bar.progress(completed_count / top_n)

                        for future in concurrent.futures.as_completed(future_to_name):
                            c_name = future_to_name[future]
                            try:
                                if future.result():
                                    success_count += 1
                                else:
                                    fail_names.append(c_name)
                            except Exception:
                                fail_names.append(c_name)

                            completed_count += 1
                            progress_bar.progress(completed_count / top_n)

                    _elapsed = time.time() - _start_time
                    if success_count == top_n:
                        st.success(f"✅ All {success_count} emails sent successfully in {_elapsed:.1f} seconds!")
                    elif success_count > 0:
                        st.warning(
                            f"⚠️ Sent {success_count}/{top_n} emails in {_elapsed:.1f} seconds. "
                            f"Failed for: {', '.join(fail_names)}"
                        )
                    else:
                        st.error(
                            f"❌ All emails failed after {_elapsed:.1f} seconds. Check your App Password and Gmail address."
                        )

# --- Tab 3: Test results + Final Re-rank ------------------------------------------
with tab_tests:
    st.subheader("📥 Upload Test Results")
    st.caption(
        "Upload the test result sheet. "
        "Candidates are matched by **Sr. No. (s_no)**. "
        "If a candidate's s_no is not found, their test scores default to **0** (absent)."
    )

    test_file = st.file_uploader(
        "Test results (CSV or Excel — needs: s_no, test_la, test_code)",
        type=["csv", "xlsx"],
        key="test_results_uploader",
    )

    if test_file is not None:
        file_bytes  = test_file.getvalue()
        sheet_names = get_xlsx_sheet_names(file_bytes)   # [] for CSV

        # ── Always let the user choose if multiple sheets exist ──────────────
        if len(sheet_names) > 1:
            TEST_SHEET_CANDIDATES = ["test result", "test results", "testresult", "result"]
            detected_index = 0
            for idx, sname in enumerate(sheet_names):
                if sname.strip().lower() in TEST_SHEET_CANDIDATES:
                    detected_index = idx
                    st.info(f"💡 Auto-detected **'{sname}'** as the most likely test results sheet.")
                    break

            chosen_sheet = st.selectbox(
                "Multiple sheets found — pick the test result sheet:",
                options=sheet_names,
                index=detected_index,
            )
        else:
            chosen_sheet = 0   # CSV, single-sheet XLSX — use as-is, no name check


        result = validate_test_results_csv(file_bytes, sheet_name=chosen_sheet)
        if result.ok:
            st.session_state["test_results_df"] = result.dataframe
            st.success(f"✅ Loaded from sheet '{chosen_sheet}' — " + result.summary_text())
            with st.expander("Preview Test Results Data", expanded=False):
                st.dataframe(result.dataframe, width="stretch")
        else:
            st.error(
                "Missing required column(s): " + ", ".join(result.missing_required_columns)
            )


    st.divider()

    # ── Re-rank section ──────────────────────────────────────────────────────
    st.subheader("🏆 Final Re-rank (Stage 2)")

    stage1_df   = st.session_state["ranked_df"]
    test_res_df = st.session_state["test_results_df"]

    if stage1_df is None:
        st.info("⬅️ Run Stage 1 AI evaluation first (Upload & configure tab).")
    else:
        # Only re-rank candidates who were actually shortlisted and sent test links
        if "shortlist_n" in st.session_state:
            stage1_df = stage1_df.head(st.session_state["shortlist_n"])

        from src.stage2_posttest.score_merger import merge_test_scores, match_summary
        from src.stage2_posttest.ranking.post_test_ranker import rank_post_test

        # Show match summary before running
        st.info(match_summary(stage1_df, test_res_df))

        if st.button("🔄 Run Final Re-rank", type="primary", key="rerank_btn"):
            _start_time = time.time()
            merged = merge_test_scores(stage1_df, test_res_df)
            final  = rank_post_test(merged)
            st.session_state["final_ranked_df"] = final
            _elapsed = time.time() - _start_time
            st.success(f"✅ Final re-rank complete in {_elapsed:.1f} seconds! Go to **Scheduling** tab to schedule interviews.")

        if st.session_state["final_ranked_df"] is not None:
            final_df = st.session_state["final_ranked_df"]
            total_final = len(final_df)

            st.subheader("Final Ranked Leaderboard")
            show_cols = [c for c in [
                "rank", "final_score", "name", "email",
                "resume_score", "github_score",
                "test_code", "test_la", "cgpa",
                "test_score_source",
            ] if c in final_df.columns]
            st.dataframe(final_df[show_cols], width="stretch")
            col_dl2, _ = st.columns([1, 3])
            with col_dl2:
                csv_final = final_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Download Final Ranked CSV",
                    data=csv_final,
                    file_name="final_ranked_candidates.csv",
                    mime="text/csv",
                )

            st.divider()

            # ── Top-N selector for interviews ──────────────────────────────
            st.subheader("🎯 How many candidates to call for interviews?")
            final_n = st.slider(
                "Select top N for interview round",
                min_value=1,
                max_value=total_final,
                value=min(3, total_final),
                key="final_shortlist_n",
                help="These candidates will be scheduled in the Scheduling tab.",
            )

            interview_candidates = final_df.head(final_n)
            st.caption(f"✅ **{final_n} candidates selected** for interviews (Rank 1 – {final_n})")

            interview_cols = [c for c in [
                "rank", "final_score", "name", "email", "cgpa",
                "test_code", "test_la",
            ] if c in interview_candidates.columns]
            st.dataframe(
                interview_candidates[interview_cols].reset_index(drop=True),
                width="stretch",
                hide_index=True,
            )
            st.info("👉 Go to the **Scheduling** tab to book interview slots for these candidates.")

# --- Tab 4: Scheduling --------------------------------------------------------
with tab_schedule:
    st.header("Automated Interview Scheduling")

    # Use final re-ranked data if available, fall back to Stage 1 rank
    final_ranked = st.session_state["final_ranked_df"]
    stage1_ranked = st.session_state["ranked_df"]

    if final_ranked is not None:
        df_final      = final_ranked
        rank_col      = "rank"
        score_col     = "final_score"
        st.success("Using **final post-test ranking** for scheduling.")
    elif stage1_ranked is not None:
        df_final  = stage1_ranked
        rank_col  = "pre_test_rank"
        score_col = "pre_test_score"
        st.warning(
            "⚠️ Test results not yet re-ranked. Using **Stage 1 pre-test ranking**. "
            "Upload test results and run Re-rank in the Test Results tab first."
        )
    else:
        df_final = None

    if df_final is None:
        st.info("No candidates available. Run AI evaluation in Tab 1 first.")
    else:
        max_candidates = len(df_final)
        st.write(f"**{max_candidates}** candidates ready for scheduling.")

        # Default to the N chosen in Tab 3 if available
        default_n = min(
            st.session_state.get("final_shortlist_n", 3),
            max_candidates
        )
        top_n = st.slider(
            "Number of top candidates to schedule",
            min_value=1,
            max_value=max_candidates,
            value=default_n,
            key="schedule_n",
        )
        st.write(
            f"This will schedule back-to-back **30-minute** interviews "
            f"for the top **{top_n}** candidates."
        )

        col_d, col_t = st.columns(2)
        with col_d:
            start_date = st.date_input(
                "Starting Date",
                value=datetime.date.today() + datetime.timedelta(days=1),
            )
        with col_t:
            start_time = st.time_input("Starting Time", value=datetime.time(10, 0))

        if st.button("📅 Schedule Interviews & Send Invites", type="primary"):
            _start_timer = time.time()
            first_slot = datetime.datetime.combine(start_date, start_time)
            success_count  = 0
            progress_bar   = st.progress(0.0)
            status_text    = st.empty()
            results_container = st.container()

            for i in range(top_n):
                row        = df_final.iloc[i]
                cand_name  = row.get("name", f"Candidate {i+1}")
                cand_email = row.get("email")

                if pd.isna(cand_email) or not cand_email:
                    st.error(f"Skipping {cand_name}: No email address found.")
                    continue

                current_slot = first_slot + datetime.timedelta(minutes=30 * i)
                status_text.write(
                    f"Scheduling {cand_name} at {current_slot.strftime('%I:%M %p')}..."
                )

                try:
                    meet_link = create_interview_event(
                        candidate_email=cand_email,
                        candidate_name=cand_name,
                        start_time=current_slot,
                        duration_minutes=30,
                    )
                    with results_container:
                        st.success(
                            f"✅ Scheduled **{cand_name}** at "
                            f"{current_slot.strftime('%I:%M %p')}. "
                            f"[Join Meet]({meet_link})"
                        )
                    success_count += 1
                except Exception as e:
                    with results_container:
                        st.error(f"Failed to schedule {cand_name}: {e}")

                progress_bar.progress((i + 1) / top_n)

            _elapsed = time.time() - _start_timer
            status_text.write(
                f"Finished in {_elapsed:.1f} seconds! Successfully scheduled {success_count}/{top_n} interviews."
            )

