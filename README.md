# Resume–JD Matching System — Requirements & Prompt Spec

## 1. Elaborated requirement (what you described, structured)

Build a web-hosted tool where:
1. Resumes (PDF, DOCX, TXT) live in a database/storage, and can be added over time.
2. A user pastes/uploads a **Job Description (JD)**.
3. The system searches **all** stored resumes and returns the most suitable one(s), ranked.
4. Wherever an **interview feedback Excel sheet** exists for a candidate, it's factored into the ranking.
5. Each result shows a **fitment / confidence score** with a short rationale.
6. Everything should run on **free-tier** LLM, database, and hosting services.

## 2. Recommended free-tier architecture — **locked in for a 50–500 resume database**

| Layer | Recommended free option | Notes |
|---|---|---|
| LLM (reasoning/scoring) | **Groq** — Llama 3.3 70B | Free, no credit card, fast enough to score a top-k shortlist per query without feeling slow |
| Embeddings (semantic search) | **Local `sentence-transformers` (`all-MiniLM-L6-v2`)** | Runs on CPU, $0, no rate limits. Embed all 50–500 resumes locally; only the shortlisted top-k get sent to Groq — this keeps LLM usage low and free-tier-safe |
| Vector database | **ChromaDB** (embedded in your app, free) | Right-sized for 50–500 resumes; no need for a hosted DB server at this scale. Revisit Supabase pgvector only if you cross a few thousand resumes |
| Resume/file storage | Supabase Storage (free tier) or just the local/app filesystem for MVP | Store original PDF/DOCX/TXT + extracted text |
| Resume parsing | `pdfplumber`/`pypdf` (PDF), `python-docx` (DOCX), plain read (TXT) | Extract clean text before embedding |
| Feedback sheet parsing | `openpyxl` / `pandas` | Read Excel, match rows to resumes by candidate name or a Resume_ID |
| Backend | Python (logic lives inside the Streamlit app itself) | No separate backend needed for this scale |
| Frontend + hosting | **Streamlit, deployed on Streamlit Community Cloud** | Free for unlimited public apps, ~1 GB RAM, deploys straight from GitHub with normal `pip install` — see note below |

**Why not Hugging Face Spaces:** as of mid-2026, HF changed its free tier — Spaces that run real server-side compute (Gradio or Docker, which is what a Python/Streamlit backend needs) now require a paid PRO plan. Only Static Spaces (browser-only, via Pyodide) stay free, and Pyodide can't install compiled packages like `chromadb`, `sentence-transformers`, or `torch` — which is what caused the `micropip`/wheel error earlier. **Streamlit Community Cloud remains genuinely free** and is a more natural fit anyway since the app is already built in Streamlit, so that's the hosting target going forward.

**Why this combination:** every piece has a genuinely free tier with no credit card requirement (Groq, Streamlit Community Cloud, Chroma), so you can build and demo the whole pipeline at $0. If usage grows later, only the LLM calls and hosting resources would need to move to paid tiers — the architecture doesn't need to change.

**One limitation to plan around:** Streamlit Community Cloud sleeps an app after ~12 hours without traffic; the next visitor sees a brief wake-up page. This doesn't affect functionality, only cold-start time — not something to design around for an MVP/demo tool.

## 3. End-to-end matching logic

1. **Ingest** — On upload, extract text from each resume (PDF/DOCX/TXT), chunk it, generate embeddings, and store the vector + metadata (candidate name, file type, source path, Resume_ID) in the vector DB.
2. **Ingest feedback** — Parse the feedback Excel; store rows keyed by Resume_ID or candidate name so they can be looked up later. Not every resume will have feedback — that's expected and should be handled gracefully.
3. **Query** — User enters a JD. Embed the JD text.
4. **Retrieve** — Vector-search the resume DB for the top-k (e.g., 5) most semantically similar resumes.
5. **Score** — For each of the top-k, send the JD + resume text + any matching feedback rows to the LLM using the prompt template below. The LLM returns a fitment score (0–100), a short rationale, and key matching/missing skills.
6. **Combine (JD-match only)** — Combine the vector-similarity score and the LLM's judgment score into one **Fitment Score** (e.g., `fitment = 0.4 × similarity + 0.6 × LLM_score`). This score reflects JD-vs-resume match **only**.
7. **Attach feedback separately** — If interview feedback exists for a candidate, look it up and attach it as its own block: round(s), overall rating, recommendation (Select/Hold/Reject), interviewer comments. **Do not fold this into the Fitment Score** — it's shown alongside it as an independent signal, so a recruiter can see "strong JD match, but was rejected in a prior round" without the two being tangled together.
8. **Display** — Show a ranked list (ranked by Fitment Score) with two clearly separated sections per candidate: (a) Fitment Score + rationale + matching/missing skills, and (b) Past Interview Feedback, if any, labeled "not factored into the score above."

## 4. Ready-to-use LLM prompt (scoring step)

This is the prompt template your backend would send to the LLM for each candidate once resumes are shortlisted by vector search:

```
SYSTEM:
You are a recruitment screening assistant. You evaluate how well a candidate's resume
matches a job description, using only the information provided. Be evidence-based —
every claim in your rationale must trace to a specific line in the resume or JD.
Do not invent skills or experience the resume does not state.

USER:
### Job Description
{jd_text}

### Candidate Resume ({candidate_name})
{resume_text}

### Past Interview Feedback (if any)
{feedback_text_or_"No prior interview feedback available for this candidate."}

### Task
Evaluate this candidate against the job description ONLY — do not let interview feedback
change your score. Interview feedback is shown to you only so you can summarise it
factually; it must have zero effect on fitment_score. Return a JSON object with
exactly these fields:
{
  "fitment_score": <integer 0-100, based ONLY on JD-vs-resume match>,
  "confidence": "<Low | Medium | High>",
  "matching_skills": ["...", "..."],
  "missing_or_weak_areas": ["...", "..."],
  "rationale": "<2-3 sentence explanation citing specific resume/JD evidence, no mention of interview feedback>"
}
Return ONLY the JSON object, no other text.
```

Interview feedback (when present) is rendered by the **application layer**, not the LLM — pull the matching row(s) from the feedback sheet by Resume_ID and display them in a separate "Past Interview Feedback" panel, clearly labeled as independent of the score above.

**Scoring guidance to embed in the system prompt (tune as needed):**
- Weight *must-have* JD requirements more heavily than *nice-to-have* ones.
- Treat years of directly relevant experience as a stronger signal than keyword overlap alone.
- Never fabricate skills, dates, or outcomes not present in the source text.

## 5. Sample files created for testing (see attached)

- **5 sample resumes** spanning your required formats:
  - `Ananya_Sharma_Data_Scientist.pdf`, `Rahul_Verma_Backend_Engineer.pdf` (PDF)
  - `Priya_Nair_Digital_Marketing_Manager.docx`, `Karan_Mehta_Business_Analyst.docx` (DOCX)
  - `Sneha_Iyer_HR_Manager.txt` (TXT)
- **`Interview_Feedback_Sample.xlsx`** — feedback rows for 4 of the 5 candidates (Sneha Iyer intentionally has none, to test how the system handles missing feedback), with an "Interview Feedback" sheet and a "Legend" sheet explaining each column.

Try JDs like *"Senior Data Scientist with GenAI/LLM fine-tuning experience"* or *"D2C Marketing Manager with quick-commerce experience"* against this set — the correct top match should be unambiguous, which makes it easy to sanity-check your pipeline before scaling up the resume database.

## 6. Deploying to Streamlit Community Cloud

1. Push the `SmartHire2` folder to a GitHub repo (public — the free tier allows only one private app).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, click **New app**, and point it at your repo's `app.py`. It installs everything from `requirements.txt` automatically with normal `pip` — no wheel restrictions like Hugging Face's Static Spaces had.
3. In the app's **Settings → Secrets**, add your keys in **TOML format** (different syntax from a local `.env` file):

```toml
GROQ_API_KEY = "your_groq_api_key_here"
GROQ_MODEL = "llama-3.3-70b-versatile"

SUPABASE_URL = "https://msvlpmeetfismwwrlpeg.supabase.co"
SUPABASE_KEY = "your_supabase_secret_or_service_role_key_here"
```

4. In code, these are read via `st.secrets["GROQ_API_KEY"]` etc. (instead of `os.getenv(...)` used for local `.env` loading) — the app code should check `st.secrets` first and fall back to `.env`/`os.environ` for local development, so the same codebase works in both places without edits.

## 7. Open questions

See the questions asked separately — your answers will shape the embedding model choice, scoring weights, and how strictly the feedback sheet should influence ranking.
