const API_BASE = '/api';

export interface Profile {
  name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  location: string;
  title: string;
  summary: string;
  key_skills: string[];
  years_experience: number;
  education: Record<string, string>[];
  languages: string[];
  preferred_language: string;
  tone: string;
}

export interface CvFile {
  filename: string;
  path: string;
  size: number;
}

export interface JobOffer {
  id: string;
  company: string;
  position: string;
  location: string;
  raw_description: string;
  url?: string;
  source?: string;
  created_at: string;
  requirements?: string[];
  tech_stack?: string[];
}

export interface GeneratedContent {
  content: string;
  type: string;
}

// ─── Profile ───────────────────────────────────────────────────────

export async function getProfile(): Promise<Profile> {
  const res = await fetch(`${API_BASE}/profile`);
  return res.json();
}

export async function updateProfile(data: Partial<Profile>): Promise<Profile> {
  const res = await fetch(`${API_BASE}/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

// ─── CVs ───────────────────────────────────────────────────────────

export async function listCvs(): Promise<{ cvs: CvFile[] }> {
  const res = await fetch(`${API_BASE}/cvs`);
  return res.json();
}

export async function uploadCv(file: File): Promise<{ filename: string; status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/cvs/upload`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

// ─── Jobs ──────────────────────────────────────────────────────────

export async function listJobs(): Promise<{ jobs: JobOffer[] }> {
  const res = await fetch(`${API_BASE}/jobs`);
  return res.json();
}

export async function createJob(data: {
  raw_description?: string;
  url?: string;
  company?: string;
  position?: string;
  location?: string;
}): Promise<JobOffer> {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to create job');
  }
  return res.json();
}

export async function scrapeJob(url: string, useBrowser = false): Promise<{ scraped: Record<string, string>; message: string }> {
  const res = await fetch(`${API_BASE}/jobs/scrape`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, use_browser: useBrowser }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to scrape URL');
  }
  return res.json();
}

export async function deleteJob(jobId: string): Promise<void> {
  await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' });
}

// ─── Generation ────────────────────────────────────────────────────

export async function generateCoverLetter(data: {
  cv_filename: string;
  job_id: string;
  language?: string;
  recruiter_name?: string;
}): Promise<GeneratedContent> {
  const res = await fetch(`${API_BASE}/generate/cover-letter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to generate cover letter');
  return res.json();
}

export async function generateRecruiterMessage(data: {
  cv_filename: string;
  job_id: string;
  message_type?: string;
  language?: string;
  recruiter_name?: string;
}): Promise<GeneratedContent> {
  const res = await fetch(`${API_BASE}/generate/recruiter-message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to generate message');
  return res.json();
}

export async function generateInterviewAnswer(data: {
  question: string;
  cv_filename: string;
  job_id: string;
  language?: string;
}): Promise<GeneratedContent> {
  const res = await fetch(`${API_BASE}/generate/interview-answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to generate answer');
  return res.json();
}

export async function generateInterviewQuestions(data: {
  cv_filename: string;
  job_id: string;
  language?: string;
}): Promise<GeneratedContent> {
  const res = await fetch(`${API_BASE}/generate/interview-questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to generate questions');
  return res.json();
}

// ─── Health ────────────────────────────────────────────────────────

export async function getHealth(): Promise<{
  status: string;
  ollama_status: string;
  llm_model: string;
  available_models: string[];
}> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}
