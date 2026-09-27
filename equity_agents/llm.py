"""
llm.py
Thin Groq wrapper shared by all agents. Every call asks for a JSON object and
returns a dict, or None when Groq isn't configured or the call fails - agents
then fall back to their rule-based logic, so nothing ever hard-depends on it.
"""
import json

from equity_agents import config


def chat_json(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict | None:
    if not config.groq_is_configured():
        return None
    try:
        from groq import Groq

        client = Groq(api_key=config.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:  # noqa: BLE001 - any Groq/JSON failure -> rule-based fallback
        print(f"[llm] Groq call failed, using rule-based fallback: {e}")
        return None


def clamp(value, lo: float, hi: float, default: float = 0.0) -> float:
    """Coerce an LLM-provided number into range, so bad output can't break scoring."""
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default
