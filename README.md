# JobPilot

AI-powered job application assistant that uses local LLMs (via Ollama) to generate personalized cover letters, recruiter messages, and interview preparation content.

## Features

- **Cover Letter Generation**: Personalized cover letters based on your CV and the specific job offer
- **Recruiter Messages**: LinkedIn DMs and emails tailored for first contact, follow-ups, or networking
- **Interview Q&A**: AI-generated answers to likely interview questions using the STAR method
- **Job Analysis**: Automatic extraction of key information from job postings
- **Multi-language**: Generate content in any language (Spanish, English, etc.)
- **100% Local**: All AI processing runs locally via Ollama - your data never leaves your machine

## Architecture

```
JobPilot/
├── backend/          # Python FastAPI server
│   └── app/
│       ├── agents/   # AI generation agents (cover letter, messages, Q&A)
│       ├── api/      # REST API routes
│       ├── core/     # Config, LLM client
│       └── services/ # CV parser, job manager, profile
├── frontend/         # React + Vite + TailwindCSS
│   └── src/
├── data/
│   ├── cvs/          # Your CV files (PDF, DOCX, etc.)
│   ├── jobs/         # Saved job offers
│   └── outputs/      # Generated content
└── docker-compose.yml
```

## Quick Start

### Prerequisites

- [Ollama](https://ollama.com) installed and running
- Python 3.12+ (for local dev) or Docker

### Option 1: Docker (recommended)

```bash
docker compose up
```

This will:
1. Start Ollama and pull the `llama3.2` model
2. Start the backend API on port 8000
3. Start the frontend on port 3000

### Option 2: Local development

```bash
# Start Ollama
ollama serve

# Pull the model
ollama pull llama3.2

# Backend
cd backend
pip install -e .
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Usage

### 1. Set up your profile

Configure your personal information (name, skills, experience) via the API or UI.

### 2. Upload your CV(s)

Upload one or more CV files (PDF, DOCX, TXT, MD).

### 3. Add job offers

Paste LinkedIn job descriptions - the AI will automatically extract company, position, requirements, etc.

### 4. Generate content

- **Cover Letter**: Personalized for each job, mentioning the company, position, and matching skills
- **Recruiter Message**: Short, impactful DM for LinkedIn or email
- **Interview Prep**: Get likely questions and AI-suggested answers based on your real experience

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check + Ollama status |
| GET/POST | `/api/profile` | Get/update user profile |
| GET | `/api/cvs` | List uploaded CVs |
| POST | `/api/cvs/upload` | Upload a CV file |
| GET | `/api/jobs` | List saved job offers |
| POST | `/api/jobs` | Add a new job offer (manual text or URL) |
| POST | `/api/jobs/scrape` | Scrape a job URL (preview only) |
| POST | `/api/jobs/scrape-and-save` | Scrape + AI analyze + save in one step |
| DELETE | `/api/jobs/{job_id}` | Delete a job offer |
| POST | `/api/generate/cover-letter` | Generate cover letter |
| POST | `/api/generate/recruiter-message` | Generate recruiter DM |
| POST | `/api/generate/interview-answer` | Generate interview answer |
| POST | `/api/generate/interview-questions` | Generate likely questions |

## Web Scraping

JobPilot can automatically scrape job postings from URLs:

- **LinkedIn**: Public job posts (may require Playwright for full content)
- **InfoJobs**: Full support
- **Indeed**: Full support
- **Any website**: Generic parser that extracts main content

### Two ways to add jobs:

```bash
# Option 1: Paste the URL and let JobPilot scrape it
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.linkedin.com/jobs/view/123456789"}'

# Option 2: Paste the description manually
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"raw_description": "...", "company": "ACME", "position": "Developer"}'

# Option 3: Scrape first (preview), then save
curl -X POST http://localhost:8000/api/jobs/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.infojobs.net/...", "use_browser": false}'
```

### Advanced scraping (Playwright)

For JavaScript-heavy sites (LinkedIn), install Playwright:

```bash
pip install jobpilot[scraping]
playwright install chromium
```

## Tech Stack

- **Backend**: Python, FastAPI, httpx, BeautifulSoup4
- **LLM**: Ollama (llama3.2 by default)
- **Scraping**: httpx + BeautifulSoup (basic), Playwright (advanced)
- **Frontend**: React, Vite, TailwindCSS
- **Infrastructure**: Docker Compose

## Based on

Architecture inspired by [DocuMind](https://github.com/miguelglez8/DocuMind) - same Ollama integration pattern, no LangChain, pure httpx calls.
