# AI-Powered Candidate Screening Platform

## What This Platform Does

An end-to-end AI-powered recruitment pipeline split into two explicit stages, matching the assignment workflow exactly:

```
STAGE 1 — Pre-Test
  Upload Candidate Dataset (XLSX/CSV)
    → Auto-detect "Response" sheet (multi-sheet XLSX supported)
    → Validate & normalize columns
    → AI evaluates resumes (Groq LLM + PDF parsing)
    → AI evaluates GitHub profiles (GitHub REST API + Groq LLM)
    → Pre-test ranking  (resume 53.8% + github 38.5% + cgpa 7.7%)
    → Shortlist N candidates  ← recruiter picks the number
    → Send test links via Gmail SMTP

STAGE 2 — Post-Test
  Upload Test Results (same XLSX → auto-detects "Test Result" sheet)
    → Merge by s_no (absent candidates → score = 0)
    → Final re-rank  (resume 35% + github 25% + test_code 20% + test_la 15% + cgpa 5%)
    → Schedule interviews via Google Calendar + Meet
    → Send interview invitations
```

---

## Project Structure

```
student_Evaluation_Platform/
├── app.py                          # Streamlit UI — 4 tabs
├── requirements.txt
├── .env                            # API keys (never commit)
├── jd.txt                          # Job description for local testing
│
├── test_pipeline.py                # ✅ Terminal test: runs Stage 1 end-to-end
├── test_stage2.py                  # ✅ Terminal test: runs Stage 2 merge + re-rank
├── send_emails.py                  # ✅ Terminal tool: emails from saved CSV (no LLM)
│
├── results/
│   ├── pipeline_output.csv         # Stage 1 output (saved by test_pipeline.py)
│   └── stage2_final_output.csv     # Stage 2 final ranked output
│
└── src/
    ├── common/
    │   ├── validators.py           # CSV/XLSX validation & column normalization
    │   ├── llm_client.py           # GroqLLMClient — key rotation + retry
    │   └── ranking_utils.py        # safe_float(), github_score_for_row()
    │
    ├── stage1_pretest/
    │   ├── orchestrator.py         # Coordinates resume → github → rank
    │   ├── resume_evaluation/
    │   │   ├── parser.py           # GDrive downloader, PDF extraction (3-tier fallback)
    │   │   ├── evaluator.py        # LLM resume scoring (injected client)
    │   │   └── pipeline.py         # Batch runner over all candidates
    │   ├── github_evaluation/
    │   │   ├── fetcher.py          # GitHub REST API — profile + top repos + READMEs
    │   │   ├── evaluator.py        # LLM GitHub scoring (injected client)
    │   │   └── pipeline.py         # Per-candidate orchestration
    │   ├── ranking/
    │   │   └── pre_test_ranker.py  # rank_pre_test() — resume/github/cgpa only
    │   └── emailing/
    │       └── sender.py           # send_test_link_email() via Gmail SMTP
    │
    └── stage2_posttest/
        ├── score_merger.py         # Merge test results by s_no onto Stage 1 df
        ├── ranking/
        │   └── post_test_ranker.py # rank_post_test() — full 5-weight formula
        └── scheduling/
            └── calendar.py         # Google Calendar OAuth + Meet event creation
```

---

## Stage 1 — Pre-Test Pipeline

### Ranking Formula (pre-test)

```
pre_test_score = (resume_score × 0.538)
              + (github_score  × 0.385)
              + (cgpa_norm     × 0.077)
```

> **Why these weights?** The 3 Stage 1 components are resume (35%),
> github (25%), cgpa (5%) — taken from the full 5-weight budget.
> Renormalized to sum to 1.0 so absent test dimensions don't silently
> drag every candidate down.

Output columns: `pre_test_score`, `pre_test_rank`

### GitHub Score Floor

Any candidate with no GitHub URL, or whose GitHub fetch/eval **failed or was skipped**
(`github_eval_status` ∈ `{skipped, error}`), gets a **floor of 30/100**
instead of 0.

> **Why:** Giving 0 would penalize 25% of the total score for missing
> a *non-required* field. 30 keeps the dimension roughly neutral rather
> than punishing — the LLM only scores candidates where real data exists.

### LLM Client — Key Rotation

`GroqLLMClient` accepts a comma-separated list of keys via `GROQ_API_KEYS`.
On a 429 (rate-limit) response it immediately rotates to the next key before
falling back to a wait-and-retry. The **same client instance is injected into
both** the resume evaluator and GitHub evaluator — they share one rotation pool.

> **Caution:** If you only supply 1 key, you will hit rate limits mid-pipeline
> for 10+ candidates. Provide at least 2 keys.

### Resume PDF Extraction — 3-Tier Fallback

```
1. PyMuPDF (fitz)    ← most reliable against custom/ligature fonts
2. pdfplumber         ← fallback if output looks garbled / empty
3. PyPDF2             ← last resort
```

If all three fail the candidate receives `resume_score = 0` with
`resume_eval_status = error` and the pipeline continues (does not crash).

### GitHub API

Fetches public repo count, followers, and the **top 5 most-recently pushed
original repos** (forks excluded), each with a cleaned README (max 1,000 chars,
markdown/HTML stripped) and topic tags.

> **Caution:** Each candidate requires ~10–12 API calls. For 10 candidates
> that's ~100–120 calls — well above the unauthenticated limit of 60/hour.
> `GITHUB_TOKEN` in `.env` is **required**, not optional, at real usage volume.

---

## Stage 2 — Post-Test Pipeline

### Merge Logic (`score_merger.py`)

**Primary key: `s_no`** — used for all joins. Email was ruled out because the
sample dataset uses a single placeholder email for all candidates.

```
For each candidate in Stage 1 output:
  Look up s_no in the Test Result sheet
  ├── Found + has scores   → use those scores   (test_score_source = "test_result_sheet")
  ├── Found + scores NaN   → treat as 0         (absent / did not attempt)
  └── Not found            → 0                  (test_score_source = "absent_zero")
```

> **Caution:** The Stage 1 DataFrame already carries `test_la` and `test_code`
> columns from the original Response sheet (they are optional columns in the
> validator). Before merging, the merger **drops those columns from the left
> side** to prevent pandas creating `test_la_x` / `test_la_y` pairs, which
> would make the lookup silently fall through to zeros for everyone.

### Ranking Formula (post-test — full 5-weight)

```
final_score = (resume_score × 0.35)
            + (github_score  × 0.25)
            + (test_code     × 0.20)
            + (test_la       × 0.15)
            + (cgpa_norm     × 0.05)
```

Output columns: `final_score`, `rank`, `test_score_source`

### Sheet Auto-Detection (Tab 3 Upload)

| File type | Sheets                             | Behaviour                   |
| --------- | ---------------------------------- | --------------------------- |
| CSV       | —                                 | Use directly                |
| XLSX      | 1 sheet                            | Use directly, no name check |
| XLSX      | 2+ sheets, one named "Test Result" | Auto-select it, show banner |
| XLSX      | 2+ sheets, none match              | Show dropdown to pick       |

---

## Terminal Test Scripts

These let you test without running the Streamlit UI:

| Script                      | Purpose                                                                                           |
| --------------------------- | ------------------------------------------------------------------------------------------------- |
| `python test_pipeline.py` | Full Stage 1: LLM + GitHub + rank → saves`results/pipeline_output.csv`                         |
| `python test_stage2.py`   | Stage 2: reads saved CSV + dataset → merge + re-rank → saves`results/stage2_final_output.csv` |
| `python send_emails.py`   | Email only: reads saved CSV, picks N, sends (no LLM, no pipeline)                                 |

---

## Environment Variables (`.env`)

```env
GROQ_API_KEYS=key1,key2          # Required. Comma-separated. Minimum 2 for 10+ candidates.
GITHUB_TOKEN=ghp_...             # Required at real usage volume (>60 calls/hour)
SMTP_USER=you@gmail.com          # Gmail address for sending test-link emails
SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password (not your login password)
```

> **Never commit `.env` to GitHub.** It is listed in `.gitignore`.

### How to get a Gmail App Password

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. **Security** → **2-Step Verification** → turn it **ON**
3. **Security** → search **"App Passwords"**
4. App name → anything → **Create**
5. Copy the 16-character password — shown only once

---

## Setup

```powershell
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API keys to .env (see above)

# 4. Run the app
streamlit run app.py
```

Opens at **http://localhost:8501**

---

## App Tabs — Current Status

| Tab                          | Status       | What it does                                                                   |
| ---------------------------- | ------------ | ------------------------------------------------------------------------------ |
| **Upload & configure** | ✅ Done      | Upload XLSX/CSV, auto-detect sheets, paste JD, run AI evaluation               |
| **Ranked dashboard**   | ✅ Done      | Full leaderboard, slider to pick top-N shortlist, send test emails             |
| **Test results**       | ✅ Done      | Auto-detects "Test Result" sheet, merge by s_no, final re-rank button          |
| **Scheduling**         | ⚠️ Partial | Works locally with Google Calendar OAuth; needs`st.secrets` for cloud deploy |

---

## What's Left To Do

| Item                                   | Priority | Notes                                                                                                                     |
| -------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Google Calendar cloud deploy** | High     | `run_local_server()` OAuth only works locally. Need `st.secrets` + pre-authorized token for Streamlit Community Cloud |
| **Public hosting**               | High     | Deploy to Streamlit Community Cloud and get a public URL (assignment deliverable)                                         |
| **Architecture document**        | Medium   | `ARCHITECTURE.md` with component diagram                                                                                |
| **Demo video**                   | Medium   | 5–10 min walkthrough (assignment deliverable)                                                                            |
| **GitHub repo cleanup**          | Low      | Remove test artifacts, ensure`.env` is gitignored, add proper commit history                                            |

---

## Deliverables Checklist (per assignment)

- [ ] Hosted application — public link via Streamlit Community Cloud
- [ ] GitHub repository with setup instructions
- [ ] Architecture document (`ARCHITECTURE.md`)
- [ ] Demo video (5–10 minutes)
