# SmartHire2 — Resume ↔ JD Matcher

A Streamlit app that semantically matches resumes against a job description and
scores fitment with an LLM — built to run entirely on free-tier services.

Paste a JD, get back ranked candidates with a **Fitment Score**, matching/missing
skills, and a short rationale. Prior interview feedback (from an Excel sheet) is
looked up and shown separately, and never affects the score.

## Features

- Upload resumes (PDF, DOCX, TXT) — parsed and embedded locally, no external calls
- Paste a JD and get candidates ranked by **Fitment Score** (0–100)
- Fitment Score = 40% semantic similarity (Chroma) + 60% LLM judgment (Groq) —
  falls back to semantic-only (clearly labeled) if Groq isn't configured
- Past interview feedback shown as an independent panel, intentionally excluded
  from the score
- Optional Supabase sync for resume metadata — the app works fully without it

## Architecture

| Layer | Tool | Notes |
|---|---|---|
| Frontend + hosting | Streamlit / Streamlit Community Cloud | Free |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), local | CPU, $0, no rate limits |
| Vector database | ChromaDB, embedded on-disk | Right-sized for 50–500 resumes |
| LLM scoring | Groq — Llama 3.3 70B | Free tier, fast |
| Resume parsing | `pdfplumber`, `python-docx` | PDF / DOCX / TXT |
| Feedback parsing | `pandas` / `openpyxl` | Reads the interview feedback workbook |
| Metadata storage (optional) | Supabase Postgres | Resume metadata only — no vectors |

## Project structure

```
SmartHire2/
├── main.py                    # Streamlit entry point
├── app/
│   ├── config.py               # resolves secrets: st.secrets (Cloud) > .env (local)
│   ├── resume_parser.py        # PDF/DOCX/TXT text extraction
│   ├── vector_store.py         # Chroma embeddings + semantic search
│   ├── scorer.py                # Groq LLM scoring
│   ├── fitment.py               # blends similarity + LLM score
│   ├── feedback_loader.py       # interview feedback Excel lookup
│   └── supabase_client.py       # optional resume metadata sync
├── data/
│   ├── resumes/                 # uploaded resume files
│   ├── chroma_db/               # local vector DB (gitignored, rebuildable)
│   └── feedback/                # interview feedback workbook
├── supabase/schema.sql          # optional Postgres table for resume metadata
└── requirements.txt
```

## Setup (local development)

1. **Prerequisites:** Python 3.10+

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   ```

3. **Configure secrets:**
   ```bash
   cp .env.example .env
   ```
   Fill in:
   - `GROQ_API_KEY` — free at [console.groq.com/keys](https://console.groq.com/keys)
   - `SUPABASE_URL` / `SUPABASE_KEY` — optional, see below

   Both Groq and Supabase are optional: without Groq the app falls back to
   semantic-only scoring; without Supabase it just skips metadata sync. Local
   search works fully either way.

4. **(Optional) Supabase metadata table:** run `supabase/schema.sql` in your
   project's SQL Editor. It's safe to re-run.

5. **Run the app** (from the project root, so the `app` package imports cleanly):
   ```bash
   streamlit run main.py
   ```

## Usage

- **Admin: Upload Resumes** — upload resumes; each is parsed, embedded into the
  local Chroma DB, and (if configured) synced to Supabase.
- **Search by JD** — paste a job description and get a ranked shortlist with
  Fitment Score, matching/missing skills, rationale, and any past interview
  feedback for that candidate.

Sample data for quick testing lives in `data/resumes/` (5 resumes spanning
PDF/DOCX/TXT) and `data/feedback/Interview_Feedback_Sample.xlsx`. Try JDs like
*"Senior Data Scientist with GenAI/LLM fine-tuning experience"* or *"D2C
Marketing Manager with quick-commerce experience"* — the intended top match
should be unambiguous.

### Updating interview feedback

Edit `data/feedback/Interview_Feedback_Sample.xlsx` directly:
- Sheet must stay named **`Interview Feedback`**
- Required columns: `Resume_ID`, `Candidate_Name`, `Role_Applied`,
  `Interview_Round`, `Interview_Date`, `Interviewer`, `Overall_Rating (1-10)`,
  `Recommendation`, `Interviewer_Comments`
- Add one row per interview round

Candidates are matched primarily by **`Candidate_Name`** (case-insensitive) —
each upload through the Admin tab gets a fresh random `Resume_ID`, so a static
`Resume_ID` in the sheet rarely matches. No app restart needed; the sheet is
re-read on every search.

### Resetting local data

- **Vector DB:** delete `data/chroma_db/` — it's git-ignored and rebuilds
  automatically as resumes are re-ingested.
- **Supabase metadata:** re-run `supabase/schema.sql` to drop and recreate the
  `resumes` table.

## Deployment — Streamlit Community Cloud

1. Push this repo to GitHub (public — the free tier allows only one private app).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** →
   point it at `main.py`. Dependencies install automatically from
   `requirements.txt`.
3. In **Settings → Secrets**, add your keys in TOML format:
   ```toml
   GROQ_API_KEY = "..."
   GROQ_MODEL = "llama-3.3-70b-versatile"

   SUPABASE_URL = "https://your-project-ref.supabase.co"
   SUPABASE_KEY = "..."
   ```

The app sleeps after ~12 hours idle; the next visitor just sees a brief
wake-up page.

## Design notes

- **Fitment Score is JD-vs-resume only.** Interview feedback is deliberately
  excluded from scoring and shown as an independent panel — see the docstrings
  in `scorer.py` and `feedback_loader.py`.
- **Groq and Supabase are both optional.** Either being unconfigured degrades
  the relevant feature gracefully rather than breaking the app.

## Troubleshooting

- **`SSL: CERTIFICATE_VERIFY_FAILED` on Windows** (git, pip, or API calls) —
  usually antivirus/corporate TLS inspection intercepting HTTPS. For Python,
  `pip install pip-system-certs` routes certificate verification through the
  Windows certificate store instead of `certifi`. For `git`, use
  `git config --global http.sslBackend schannel`.
- **"Supabase not configured" despite keys being set** — confirm the running
  process is actually using this project's `.venv`, and that
  `supabase/schema.sql` has been applied to your Supabase project (the live
  `resumes` table must match the schema exactly, or upserts will fail with a
  missing-column error).

---

# Indian Equity Agents

A second, independent app in this repo: a small multi-agent system for the
Indian stock market (NSE/BSE) that produces a daily recommendation brief.
It reuses the same free-tier stack (Groq, Streamlit, `.env`/`st.secrets`).

| Agent | Reads | Produces |
|---|---|---|
| **Company News Agent** | Last 7 days of Google News (India) headlines for one company | Sentiment score, catalysts, risks, materiality |
| **Fundamentals Agent** | Yahoo Finance: ROE, margins, D/E, growth, P/E, P/B, 1Y trend, 50/200 DMA | Deterministic scorecard (quality, balance sheet, growth, valuation, trend) + narrative |
| **Market News Agent** | ET / Mint / Moneycontrol market feeds, RBI/FII/macro news, Nifty, Sensex, Bank Nifty, India VIX | Market mood, key themes, risks, sector tilts |
| **Daily Advisor** (orchestrator) | All of the above, for every stock on the watchlist | BUY / ACCUMULATE / HOLD / REDUCE / AVOID per stock + morning brief |

Each stock's action comes from a weighted blend — 55% fundamentals, 30%
company news, 15% market/sector view — so recommendations are reproducible.
The LLM writes the narrative but can't change actions or add stocks outside
the watchlist. Without `GROQ_API_KEY`, every agent falls back to rule-based
logic (keyword sentiment, scorecard only).

## Running it

```bash
pip install -r requirements.txt -r equity_agents/requirements.txt

python -m equity_agents.cli daily                  # brief for equity_agents/watchlist.txt
python -m equity_agents.cli daily -s INFY TCS      # brief for chosen stocks
python -m equity_agents.cli news RELIANCE          # one agent at a time
python -m equity_agents.cli fundamentals HDFCBANK
python -m equity_agents.cli market

streamlit run equity_app.py                        # dashboard
```

`daily` saves the brief to `reports/<date>.md` (git-ignored). Edit
`equity_agents/watchlist.txt` to change the stocks it scans.

**Daily delivery:** `.github/workflows/equity_daily_brief.yml` runs the brief
every weekday at 07:45 IST and attaches it to the Actions run (also shown in
the run summary). Add `GROQ_API_KEY` as a repository secret for the LLM
narrative.

Tests (offline, no network or keys needed): `python -m pytest tests`.

> **Not investment advice.** The agents use free, possibly delayed public
> data and are not a SEBI-registered adviser. Verify before acting.
