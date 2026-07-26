# 🚀 AI-Powered Candidate Screening Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-FF4B4B.svg)
![Groq](https://img.shields.io/badge/LLM-Groq_Llama_3-f57c00.svg)

An intelligent, end-to-end recruitment pipeline that leverages AI to automate candidate evaluation. By combining resume parsing, GitHub profile analysis, and automated email dispatching into a sleek Streamlit UI, this platform drastically reduces manual screening time while maintaining objective scoring.

*(For a deep-dive into the technical system design, data flow, and directory structure, please see the [Architecture Document](ARCHITECTURE.md))*

---

## ✨ Key Features

- 🧠 **AI Resume Evaluation:** Automatically parses PDF resumes and uses Groq's Llama 3 to rate candidates against a provided Job Description.
- 🐙 **GitHub Profile Analysis:** Scrapes pinned repositories, contribution stats, and README files, passing them through the LLM for a technical deep-dive.
- 📨 **Automated Shortlisting & Emailing:** Ranks candidates on a clean 100-point pre-test scale. Select your top candidates and dispatch external test links concurrently via Gmail SMTP.
- 📊 **Post-Test Merging:** Upload coding test results, merge them dynamically by candidate ID, and generate a final composite score.
- 📅 **Google Calendar Integration:** Automatically schedule technical interviews and generate Google Meet links for the final cohort.

---

## 🏗️ Pipeline Overview

The platform strictly enforces a chronological, two-stage evaluation process:

### STAGE 1 — Pre-Test
1. **Upload Dataset** (XLSX/CSV).
2. **AI Evaluation** (Resume parsing + GitHub scraping).
3. **Pre-Test Ranking:** (Resume: 50% | GitHub: 40% | CGPA: 10%).
4. **Shortlist & Dispatch:** Send coding test links via Gmail SMTP.

### STAGE 2 — Post-Test
1. **Upload Test Results** (XLSX/CSV auto-merges by `s_no`).
2. **Final Re-Rank:** (Resume: 35% | GitHub: 25% | Test Code: 20% | Test LA: 15% | CGPA: 5%).
3. **Schedule Interviews** via Google Calendar + Meet.

---

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.11 or higher
- A [Groq API Key](https://console.groq.com/keys)
- A [GitHub Personal Access Token](https://github.com/settings/tokens) (to prevent rate limits)
- A Gmail Account with an **App Password** (See [How to get an App Password](https://support.google.com/accounts/answer/185833))

### 2. Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/AmanKushwaha-17/ai-candidate-evaluator.git
cd student_Evaluation_Platform

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root directory (do not commit this to version control):

```env
# ── Groq LLM (Required) ──
GROQ_API_KEYS=your_key_1,your_key_2      # Comma-separated for rate-limit rotation

# ── GitHub (Required) ──
GITHUB_TOKEN=ghp_your_token_here         # Required for GitHub scraping

# ── Gmail SMTP (Required for emails) ──
SMTP_USER=youremail@gmail.com            # Gmail address for sending test-links
SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx    # 16-character Gmail App Password

# ── Google Calendar OAuth (Required for scheduling) ──
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your_client_secret
GOOGLE_REFRESH_TOKEN=1//your_refresh_token
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
```

### 4. Running the App

```bash
streamlit run app.py
```
*The app will automatically open in your browser at `http://localhost:8501`.*

---

## 🛠️ Technical Implementation Details

### LLM Client — Key Rotation
Because free-tier LLM APIs have strict Token-Per-Minute limits, the `GroqLLMClient` accepts a comma-separated list of keys. On a 429 (rate-limit) response, it immediately rotates to the next key before falling back to an exponential backoff.

### Resume PDF Extraction — 3-Tier Fallback
To ensure maximum compatibility against custom formatting and ligature fonts, the resume parser uses a tiered fallback system:
1. `PyMuPDF` (fitz) - Primary extractor
2. `pdfplumber` - Fallback for garbled text
3. `PyPDF2` - Last resort

### GitHub Score Floor
Any candidate without a GitHub URL, or whose GitHub fetch fails, receives a **neutral floor of 30/100** rather than a 0. This ensures candidates aren't heavily penalized for missing a non-required field.

