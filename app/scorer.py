"""
scorer.py
Calls Groq (free-tier LLM) to score how well a resume matches a JD.
Deliberately does NOT see interview feedback - fitment scoring is JD-vs-resume
ONLY. Feedback is looked up and displayed separately by the UI layer
(see feedback_loader.py + app.py), per the project's locked-in design.

If GROQ_API_KEY is missing or the call fails, callers should fall back to
a semantic-only score (see fitment.py) so the app keeps working.
"""
import json

from groq import Groq

from app import config

SYSTEM_PROMPT = """You are a recruitment screening assistant. You evaluate how well a \
candidate's resume matches a job description, using only the information provided. Be \
evidence-based - every claim in your rationale must trace to a specific line in the resume \
or JD. Do not invent skills or experience the resume does not state."""

USER_PROMPT_TEMPLATE = """### Job Description
{jd_text}

### Candidate Resume ({candidate_name})
{resume_text}

### Task
Evaluate this candidate against the job description ONLY. Return a JSON object with
exactly these fields and nothing else:
{{
  "fitment_score": <integer 0-100, based ONLY on JD-vs-resume match>,
  "confidence": "<Low | Medium | High>",
  "matching_skills": ["...", "..."],
  "missing_or_weak_areas": ["...", "..."],
  "rationale": "<2-3 sentence explanation citing specific resume/JD evidence>"
}}
Return ONLY the JSON object, no markdown fences, no other text."""


def _get_client() -> Groq | None:
    api_key = config.GROQ_API_KEY
    if not api_key or api_key == "your_groq_api_key_here":
        return None
    return Groq(api_key=api_key)


def score_resume_against_jd(jd_text: str, resume_text: str, candidate_name: str) -> dict | None:
    """
    Returns a dict with fitment_score, confidence, matching_skills,
    missing_or_weak_areas, rationale - or None if Groq isn't configured or
    the call fails (caller should fall back to semantic-only scoring).
    """
    client = _get_client()
    if client is None:
        return None

    model = config.GROQ_MODEL

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(
                        jd_text=jd_text, resume_text=resume_text, candidate_name=candidate_name
                    ),
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)

        # Basic sanity-checking so a malformed LLM response can't crash the UI
        parsed["fitment_score"] = int(max(0, min(100, parsed.get("fitment_score", 0))))
        parsed.setdefault("confidence", "Medium")
        parsed.setdefault("matching_skills", [])
        parsed.setdefault("missing_or_weak_areas", [])
        parsed.setdefault("rationale", "")
        return parsed

    except Exception as e:  # noqa: BLE001 - any Groq/JSON failure -> graceful fallback
        print(f"[scorer] Groq scoring failed, falling back to semantic-only: {e}")
        return None
