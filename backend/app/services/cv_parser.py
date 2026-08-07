"""CV and document parser service."""

from pathlib import Path

import pdfplumber
from markitdown import MarkItDown

from app.core.config import settings
from app.core.security import safe_join


def parse_cv(file_path: str) -> str:
    """Parse a CV file (PDF, DOCX, etc.) and return its text content."""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _parse_pdf(path)
    elif ext in (".md", ".txt"):
        return path.read_text(encoding="utf-8")
    else:
        # Use markitdown for docx, pptx, etc.
        md = MarkItDown()
        result = md.convert(str(path))
        return result.text_content


def _parse_pdf(path: Path) -> str:
    """Extract text from PDF."""
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)


def list_cvs() -> list[dict]:
    """List all CVs in the cv directory."""
    cv_dir = Path(settings.cv_dir)
    cv_dir.mkdir(parents=True, exist_ok=True)
    cvs = []
    supported = {".pdf", ".docx", ".doc", ".md", ".txt"}
    for f in cv_dir.iterdir():
        if f.is_file() and f.suffix.lower() in supported:
            cvs.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
            })
    return cvs


def get_cv_content(filename: str) -> str:
    """Get parsed content of a specific CV."""
    cv_dir = Path(settings.cv_dir)
    try:
        cv_path = safe_join(cv_dir, filename)
    except ValueError:
        raise FileNotFoundError(f"CV not found: {filename}") from None
    if not cv_path.exists():
        raise FileNotFoundError(f"CV not found: {filename}")
    return parse_cv(str(cv_path))
