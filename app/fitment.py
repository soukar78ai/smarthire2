"""
fitment.py
Combines vector similarity (Chroma) and LLM judgment (Groq) into one
Fitment Score. If Groq is unavailable, falls back to a semantic-only score
and flags that clearly so results don't silently look more "AI-reviewed"
than they are.

Feedback is intentionally NOT an input here - see scorer.py / feedback_loader.py.
Weights: 40% semantic similarity, 60% LLM judgment (tune SIMILARITY_WEIGHT
below if you want the vector search to count for more or less).
"""
from app import scorer

SIMILARITY_WEIGHT = 0.4
LLM_WEIGHT = 0.6


def compute_fitment(jd_text: str, candidate: dict) -> dict:
    """
    candidate: one result dict from vector_store.search()
      {resume_id, similarity, resume_text, metadata}

    Returns a result dict ready for display:
      {resume_id, candidate_name, fitment_score, method,
       matching_skills, missing_or_weak_areas, rationale, similarity}
    """
    similarity = candidate["similarity"]  # 0-1
    candidate_name = candidate["metadata"].get("candidate_name", candidate["resume_id"])

    llm_result = scorer.score_resume_against_jd(
        jd_text=jd_text,
        resume_text=candidate["resume_text"],
        candidate_name=candidate_name,
    )

    if llm_result is not None:
        llm_score_0_1 = llm_result["fitment_score"] / 100.0
        blended = SIMILARITY_WEIGHT * similarity + LLM_WEIGHT * llm_score_0_1
        return {
            "resume_id": candidate["resume_id"],
            "candidate_name": candidate_name,
            "fitment_score": round(blended * 100),
            "method": "semantic + LLM (Groq)",
            "confidence": llm_result["confidence"],
            "matching_skills": llm_result["matching_skills"],
            "missing_or_weak_areas": llm_result["missing_or_weak_areas"],
            "rationale": llm_result["rationale"],
            "similarity": round(similarity * 100),
        }

    # Fallback: Groq unavailable or failed - semantic-only score, clearly labeled
    return {
        "resume_id": candidate["resume_id"],
        "candidate_name": candidate_name,
        "fitment_score": round(similarity * 100),
        "method": "semantic-only (Groq unavailable - configure GROQ_API_KEY for LLM scoring)",
        "confidence": "Low",
        "matching_skills": [],
        "missing_or_weak_areas": [],
        "rationale": "LLM scoring was unavailable, so this score reflects text similarity only.",
        "similarity": round(similarity * 100),
    }
