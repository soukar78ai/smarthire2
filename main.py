"""
main.py
SmartHire2 - Streamlit entry point.

Run with:  streamlit run main.py
(Run from the SmartHire2 project root so the "app" package imports cleanly.)
"""
import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from app import feedback_loader, fitment, resume_parser, supabase_client, vector_store

RESUME_DIR = Path(__file__).parent / "data" / "resumes"
FEEDBACK_PATH = Path(__file__).parent / "data" / "feedback" / "Interview_Feedback_Sample.xlsx"
RESUME_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="SmartHire2", page_icon="🎯", layout="wide")
st.title("🎯 SmartHire2 — Resume ↔ JD Matcher")

tab_search, tab_admin = st.tabs(["🔍 Search by JD", "📥 Admin: Upload Resumes"])

# ---------------------------------------------------------------------------
# Admin: Upload
# ---------------------------------------------------------------------------
with tab_admin:
    st.subheader("Upload resumes (PDF, DOCX, or TXT)")
    st.caption(
        "Each uploaded resume is parsed, embedded locally (Chroma), and its metadata "
        "is optionally synced to Supabase. No cost, no external API calls for this step."
    )

    uploaded_files = st.file_uploader(
        "Choose resume files", type=["pdf", "docx", "txt"], accept_multiple_files=True
    )

    if uploaded_files and st.button("Ingest uploaded resumes", type="primary"):
        progress = st.progress(0.0, text="Starting...")
        for i, file in enumerate(uploaded_files):
            resume_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
            save_path = RESUME_DIR / file.name
            save_path.write_bytes(file.getbuffer())

            resume_text = resume_parser.extract_text(str(save_path))
            candidate_name = resume_parser.guess_candidate_name(str(save_path), resume_text)
            file_type = save_path.suffix.lstrip(".").lower()

            vector_store.add_resume(
                resume_id=resume_id,
                resume_text=resume_text,
                metadata={
                    "candidate_name": candidate_name,
                    "file_name": file.name,
                    "file_type": file_type,
                },
            )

            synced = supabase_client.upsert_resume_metadata(
                resume_id=resume_id,
                candidate_name=candidate_name,
                file_name=file.name,
                file_type=file_type,
            )

            progress.progress(
                (i + 1) / len(uploaded_files),
                text=f"Ingested {candidate_name} ({resume_id})"
                + (" — synced to Supabase" if synced else " — Supabase not configured, skipped"),
            )

        st.success(f"Ingested {len(uploaded_files)} resume(s). Total in database: {vector_store.count_resumes()}")

    st.divider()
    st.subheader("Currently ingested resumes")
    st.metric("Resumes in local vector database (Chroma)", vector_store.count_resumes())

    supa_rows = supabase_client.list_resume_metadata()
    if supa_rows:
        st.caption("Metadata synced to Supabase:")
        st.dataframe(supa_rows, use_container_width=True)
    else:
        st.caption(
            "Supabase not configured (or no rows yet) — this is optional. "
            "Search still works fully from the local Chroma database."
        )

# ---------------------------------------------------------------------------
# Search by JD
# ---------------------------------------------------------------------------
with tab_search:
    st.subheader("Paste a Job Description")

    total = vector_store.count_resumes()
    if total == 0:
        st.info("No resumes ingested yet — go to **Admin: Upload Resumes** first.")

    jd_text = st.text_area("Job Description", height=200, placeholder="Paste the JD here...")
    top_k = st.slider("Number of candidates to show", min_value=1, max_value=10, value=5)

    if st.button("Find best-fit resumes", type="primary", disabled=(total == 0)):
        if not jd_text.strip():
            st.warning("Please paste a job description first.")
        else:
            with st.spinner("Searching resumes and scoring fitment..."):
                candidates = vector_store.search(jd_text, top_k=top_k)
                results = [fitment.compute_fitment(jd_text, c) for c in candidates]
                results.sort(key=lambda r: r["fitment_score"], reverse=True)

            feedback_df = feedback_loader.load_feedback(str(FEEDBACK_PATH))

            if not results:
                st.warning("No matching resumes found.")

            for rank, r in enumerate(results, start=1):
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"### {rank}. {r['candidate_name']}")
                        st.caption(f"Resume ID: `{r['resume_id']}` · Scoring method: {r['method']}")
                    with col2:
                        st.metric("Fitment Score", f"{r['fitment_score']}/100")
                        st.caption(f"Confidence: {r['confidence']}")

                    if r["matching_skills"]:
                        st.markdown("**✅ Matching skills:** " + ", ".join(r["matching_skills"]))
                    if r["missing_or_weak_areas"]:
                        st.markdown("**⚠️ Missing / weak areas:** " + ", ".join(r["missing_or_weak_areas"]))
                    if r["rationale"]:
                        st.markdown(f"**Rationale:** {r['rationale']}")

                    # --- Feedback shown separately, NOT part of fitment_score ---
                    fb_rows = feedback_loader.get_feedback_for_candidate(
                        feedback_df, resume_id=None, candidate_name=r["candidate_name"]
                    )
                    with st.expander(
                        f"📋 Past interview feedback ({'available' if not fb_rows.empty else 'none on file'}) "
                        "— not factored into the score above"
                    ):
                        if fb_rows.empty:
                            st.caption("No prior interview feedback available for this candidate.")
                        else:
                            for _, row in fb_rows.iterrows():
                                st.markdown(
                                    f"- **{row['Interview_Round']}** ({row['Interview_Date']}, "
                                    f"interviewer: {row['Interviewer']}) — "
                                    f"Overall rating **{row['Overall_Rating (1-10)']}/10**, "
                                    f"recommendation: **{row['Recommendation']}**  \n"
                                    f"  _{row['Interviewer_Comments']}_"
                                )
