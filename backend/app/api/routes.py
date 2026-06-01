"""FastAPI routes for JobPilot."""

import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.cover_letter import generate_cover_letter
from app.agents.recruiter_message import generate_recruiter_message
from app.agents.interview_qa import generate_answer, generate_common_questions
from app.agents.job_analyzer import analyze_job_posting
from app.services.cv_parser import list_cvs, get_cv_content
from app.services.job_manager import save_job_offer, list_jobs, get_job, delete_job
from app.services.profile_manager import get_profile, save_profile
from app.services.scraper import scrape_job_url
from app.core.config import settings

router = APIRouter(prefix="/api")


# ─── Profile ───────────────────────────────────────────────────────────

class ProfileRequest(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    location: str = ""
    title: str = ""
    summary: str = ""
    key_skills: list[str] = []
    years_experience: int = 0
    education: list[dict] = []
    languages: list[str] = []
    preferred_language: str = "es"
    tone: str = "professional"


@router.get("/profile")
async def get_user_profile():
    """Get user profile."""
    return get_profile()


@router.post("/profile")
async def update_profile(req: ProfileRequest):
    """Update user profile."""
    return save_profile(req.model_dump(exclude_unset=True))


# ─── CVs ───────────────────────────────────────────────────────────────

@router.get("/cvs")
async def list_user_cvs():
    """List uploaded CVs."""
    return {"cvs": list_cvs()}


@router.post("/cvs/upload")
async def upload_cv(file: UploadFile = File(...)):
    """Upload a CV file."""
    cv_dir = Path(settings.cv_dir)
    cv_dir.mkdir(parents=True, exist_ok=True)

    supported = {".pdf", ".docx", ".doc", ".md", ".txt"}
    ext = Path(file.filename).suffix.lower()
    if ext not in supported:
        raise HTTPException(400, f"Unsupported file type: {ext}. Supported: {supported}")

    dest = cv_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"filename": file.filename, "status": "uploaded"}


@router.get("/cvs/{filename}/content")
async def get_cv_text(filename: str):
    """Get parsed text content of a CV."""
    try:
        content = get_cv_content(filename)
        return {"filename": filename, "content": content}
    except FileNotFoundError:
        raise HTTPException(404, f"CV not found: {filename}")


# ─── Jobs ──────────────────────────────────────────────────────────────

class JobOfferRequest(BaseModel):
    raw_description: str = ""
    url: str = ""
    company: str = ""
    position: str = ""
    location: str = ""


class ScrapeJobRequest(BaseModel):
    url: str
    use_browser: bool = False


@router.get("/jobs")
async def list_job_offers():
    """List all saved job offers."""
    return {"jobs": list_jobs()}


@router.post("/jobs/scrape")
async def scrape_job(req: ScrapeJobRequest):
    """Scrape a job posting URL and return extracted content (preview, not saved yet)."""
    if not req.url:
        raise HTTPException(400, "URL is required")
    
    scraped = await scrape_job_url(req.url, use_browser=req.use_browser)
    
    if scraped.get("error"):
        raise HTTPException(502, f"Could not scrape URL: {scraped['error']}")
    
    if not scraped.get("raw_text"):
        raise HTTPException(502, "Could not extract content from the page")
    
    return {
        "scraped": scraped,
        "message": "Content extracted. Use POST /api/jobs to save it.",
    }


@router.post("/jobs/scrape-and-save")
async def scrape_and_save_job(req: ScrapeJobRequest):
    """Scrape a job posting URL, analyze with AI, and save it directly."""
    if not req.url:
        raise HTTPException(400, "URL is required")
    
    # Step 1: Scrape the page
    scraped = await scrape_job_url(req.url)
    
    if scraped.get("error"):
        raise HTTPException(502, f"Could not scrape URL: {scraped['error']}")
    
    if not scraped.get("raw_text"):
        raise HTTPException(502, "Could not extract content from the page")
    
    # Step 2: Use AI to analyze the raw text
    analyzed = await analyze_job_posting(scraped["raw_text"])
    
    # Step 3: Merge scraped metadata with AI analysis
    job_data = {
        "raw_description": scraped["raw_text"],
        "url": req.url,
        "source": scraped.get("source", "web"),
    }
    
    # Use scraped title/company as fallback, AI analysis takes priority
    for key in ("company", "position", "location"):
        job_data[key] = analyzed.get(key) or scraped.get(key, "")
    
    # Add all AI-extracted fields
    for key, value in analyzed.items():
        if key not in job_data:
            job_data[key] = value
    
    # Step 4: Save
    saved = save_job_offer(job_data)
    return saved


@router.post("/jobs")
async def create_job_offer(req: JobOfferRequest):
    """Save a new job offer manually or from a URL.
    
    - If `url` is provided and `raw_description` is empty: scrapes the URL first
    - If `raw_description` is provided: uses it directly (manual input)
    - In both cases, AI analyzes the content if company/position are missing
    """
    job_data = req.model_dump()

    # If URL provided but no description, scrape it
    if job_data.get("url") and not job_data.get("raw_description"):
        scraped = await scrape_job_url(job_data["url"])
        if scraped.get("error"):
            raise HTTPException(502, f"Could not scrape URL: {scraped['error']}")
        job_data["raw_description"] = scraped.get("raw_text", "")
        job_data["source"] = scraped.get("source", "web")
        # Use scraped metadata as hints
        if not job_data.get("company"):
            job_data["company"] = scraped.get("company", "")
        if not job_data.get("position"):
            job_data["position"] = scraped.get("title", "")
        if not job_data.get("location"):
            job_data["location"] = scraped.get("location", "")

    if not job_data.get("raw_description"):
        raise HTTPException(400, "Either raw_description or url must be provided")

    # If basic fields are missing, use AI to extract them
    if not job_data.get("company") or not job_data.get("position"):
        analyzed = await analyze_job_posting(job_data["raw_description"])
        # Merge AI analysis with provided data (user data takes priority)
        for key, value in analyzed.items():
            if key not in job_data or not job_data[key]:
                job_data[key] = value

    saved = save_job_offer(job_data)
    return saved


@router.get("/jobs/{job_id}")
async def get_job_offer(job_id: str):
    """Get a specific job offer."""
    try:
        return get_job(job_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Job not found: {job_id}")


@router.delete("/jobs/{job_id}")
async def remove_job_offer(job_id: str):
    """Delete a job offer."""
    if delete_job(job_id):
        return {"status": "deleted"}
    raise HTTPException(404, f"Job not found: {job_id}")


# ─── Generation ────────────────────────────────────────────────────────

class GenerateCoverLetterRequest(BaseModel):
    cv_filename: str
    job_id: str
    language: str = "es"
    recruiter_name: str = ""


class GenerateMessageRequest(BaseModel):
    cv_filename: str
    job_id: str
    message_type: str = "first_contact"  # first_contact, follow_up, networking
    language: str = "es"
    recruiter_name: str = ""


class GenerateAnswerRequest(BaseModel):
    question: str
    cv_filename: str
    job_id: str
    language: str = "es"


class GenerateQuestionsRequest(BaseModel):
    cv_filename: str
    job_id: str
    language: str = "es"


@router.post("/generate/cover-letter")
async def gen_cover_letter(req: GenerateCoverLetterRequest):
    """Generate a cover letter (non-streaming)."""
    try:
        result = await generate_cover_letter(
            cv_filename=req.cv_filename,
            job_id=req.job_id,
            language=req.language,
            recruiter_name=req.recruiter_name,
            stream=False,
        )
        return {"content": result, "type": "cover_letter"}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/generate/cover-letter/stream")
async def gen_cover_letter_stream(req: GenerateCoverLetterRequest):
    """Generate a cover letter (streaming)."""
    try:
        generator = await generate_cover_letter(
            cv_filename=req.cv_filename,
            job_id=req.job_id,
            language=req.language,
            recruiter_name=req.recruiter_name,
            stream=True,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/generate/recruiter-message")
async def gen_recruiter_message(req: GenerateMessageRequest):
    """Generate a recruiter message (non-streaming)."""
    try:
        result = await generate_recruiter_message(
            cv_filename=req.cv_filename,
            job_id=req.job_id,
            message_type=req.message_type,
            language=req.language,
            recruiter_name=req.recruiter_name,
            stream=False,
        )
        return {"content": result, "type": "recruiter_message", "message_type": req.message_type}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/generate/recruiter-message/stream")
async def gen_recruiter_message_stream(req: GenerateMessageRequest):
    """Generate a recruiter message (streaming)."""
    try:
        generator = await generate_recruiter_message(
            cv_filename=req.cv_filename,
            job_id=req.job_id,
            message_type=req.message_type,
            language=req.language,
            recruiter_name=req.recruiter_name,
            stream=True,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/generate/interview-answer")
async def gen_interview_answer(req: GenerateAnswerRequest):
    """Generate an answer to an interview question."""
    try:
        result = await generate_answer(
            question=req.question,
            cv_filename=req.cv_filename,
            job_id=req.job_id,
            language=req.language,
            stream=False,
        )
        return {"content": result, "type": "interview_answer", "question": req.question}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/generate/interview-answer/stream")
async def gen_interview_answer_stream(req: GenerateAnswerRequest):
    """Generate an answer to an interview question (streaming)."""
    try:
        generator = await generate_answer(
            question=req.question,
            cv_filename=req.cv_filename,
            job_id=req.job_id,
            language=req.language,
            stream=True,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/generate/interview-questions")
async def gen_interview_questions(req: GenerateQuestionsRequest):
    """Generate likely interview questions for a job."""
    try:
        result = await generate_common_questions(
            cv_filename=req.cv_filename,
            job_id=req.job_id,
            language=req.language,
        )
        return {"content": result, "type": "interview_questions"}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


# ─── Health ────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check - also verifies Ollama connection."""
    import httpx

    ollama_status = "unknown"
    available_models = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.llm_base_url}/api/tags")
            if resp.status_code == 200:
                ollama_status = "connected"
                data = resp.json()
                available_models = [m["name"] for m in data.get("models", [])]
    except Exception:
        ollama_status = "disconnected"

    return {
        "status": "ok",
        "version": "0.1.0",
        "ollama_status": ollama_status,
        "llm_model": settings.llm_model,
        "available_models": available_models,
    }
