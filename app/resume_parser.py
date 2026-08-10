"""
resume_parser.py
Extracts plain text from resumes in PDF, DOCX, or TXT format.
"""
from pathlib import Path

import pdfplumber
from docx import Document as DocxDocument


def extract_text(file_path: str) -> str:
    """Extract plain text from a resume file. Supports .pdf, .docx, .txt."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".docx":
        return _extract_docx(path)
    elif suffix == ".txt":
        return _extract_txt(path)
    else:
        raise ValueError(
            f"Unsupported file type '{suffix}'. Only .pdf, .docx, .txt are supported."
        )


def _extract_pdf(path: Path) -> str:
    text_parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def _extract_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also pull text out of any tables in the resume
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    paragraphs.append(cell.text.strip())
    return "\n".join(paragraphs).strip()


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def guess_candidate_name(file_path: str, resume_text: str) -> str:
    """
    Best-effort candidate name guess: prefer the first non-empty line of the
    resume (resumes conventionally open with the candidate's name), fall back
    to a cleaned-up filename.
    """
    for line in resume_text.splitlines():
        line = line.strip()
        if line and len(line.split()) <= 6 and not any(ch.isdigit() for ch in line):
            return line
    stem = Path(file_path).stem.replace("_", " ").replace("-", " ")
    return stem
