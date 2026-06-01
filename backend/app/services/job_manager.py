"""Job offer parser and manager."""

import json
from pathlib import Path
from datetime import datetime

from app.core.config import settings


def save_job_offer(job_data: dict) -> dict:
    """Save a job offer to the jobs directory."""
    jobs_dir = Path(settings.jobs_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from company and position
    company = job_data.get("company", "unknown").replace(" ", "_").lower()
    position = job_data.get("position", "unknown").replace(" ", "_").lower()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{company}_{position}_{timestamp}.json"

    job_data["created_at"] = datetime.now().isoformat()
    job_data["id"] = filename.replace(".json", "")

    filepath = jobs_dir / filename
    filepath.write_text(json.dumps(job_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return job_data


def list_jobs() -> list[dict]:
    """List all saved job offers."""
    jobs_dir = Path(settings.jobs_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for f in sorted(jobs_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            jobs.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return jobs


def get_job(job_id: str) -> dict:
    """Get a specific job offer by ID."""
    jobs_dir = Path(settings.jobs_dir)
    filepath = jobs_dir / f"{job_id}.json"
    if not filepath.exists():
        raise FileNotFoundError(f"Job not found: {job_id}")
    return json.loads(filepath.read_text(encoding="utf-8"))


def delete_job(job_id: str) -> bool:
    """Delete a job offer."""
    jobs_dir = Path(settings.jobs_dir)
    filepath = jobs_dir / f"{job_id}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False


def parse_linkedin_job(raw_text: str) -> dict:
    """Parse raw LinkedIn job posting text into structured data."""
    # Basic extraction - the AI agent will do the heavy lifting
    lines = raw_text.strip().split("\n")
    job_data = {
        "raw_description": raw_text,
        "company": "",
        "position": "",
        "location": "",
        "requirements": [],
        "responsibilities": [],
        "source": "linkedin",
    }

    # Try to extract basic info from first lines
    if lines:
        job_data["position"] = lines[0].strip()
    if len(lines) > 1:
        job_data["company"] = lines[1].strip()
    if len(lines) > 2:
        job_data["location"] = lines[2].strip()

    return job_data
