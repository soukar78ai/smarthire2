"""
feedback_loader.py
Loads the interview feedback Excel sheet and exposes a lookup by Resume_ID
or candidate name. Feedback is intentionally kept separate from the fitment
scoring pipeline - see scorer.py for why.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

REQUIRED_COLUMNS = {
    "Resume_ID",
    "Candidate_Name",
    "Role_Applied",
    "Interview_Round",
    "Interview_Date",
    "Interviewer",
    "Overall_Rating (1-10)",
    "Recommendation",
    "Interviewer_Comments",
}


def load_feedback(xlsx_path: str, sheet_name: str = "Interview Feedback") -> pd.DataFrame:
    """Load feedback rows from the sample/production Excel workbook."""
    path = Path(xlsx_path)
    if not path.exists():
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))

    df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Feedback sheet is missing expected columns: {sorted(missing)}. "
            "Update the sheet or adjust REQUIRED_COLUMNS in feedback_loader.py."
        )
    return df


def get_feedback_for_candidate(
    feedback_df: pd.DataFrame,
    resume_id: Optional[str] = None,
    candidate_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Return all feedback rows for a candidate, matched first by Resume_ID
    (exact, preferred) and falling back to a case-insensitive name match.
    Returns an empty DataFrame if no feedback exists - this is expected and
    should be handled gracefully by the UI ("No prior interview feedback").
    """
    if feedback_df.empty:
        return feedback_df

    if resume_id:
        matches = feedback_df[feedback_df["Resume_ID"] == resume_id]
        if not matches.empty:
            return matches

    if candidate_name:
        matches = feedback_df[
            feedback_df["Candidate_Name"].str.strip().str.lower()
            == candidate_name.strip().lower()
        ]
        return matches

    return feedback_df.iloc[0:0]  # empty, same columns
