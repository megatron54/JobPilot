import { invoke } from '@tauri-apps/api/core';

// ─── Types ─────────────────────────────────────────────────────────

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
  languages: string[];
  preferred_language: string;
  tone: string;
}

export interface CvInfo {
  filename: string;
  char_count: number;
}

export interface JobOffer {
  id: string;
  company: string;
  position: string;
  location: string;
  raw_description: string;
  url: string;
  source: string;
  created_at: string;
  requirements: string[];
  tech_stack: string[];
}

export interface HealthResponse {
  status: string;
  ollama_status: string;
  llm_model: string;
  cvs_loaded: number;
  jobs_count: number;
}

export interface SetupStatus {
  ollama_running: boolean;
  llm_ready: boolean;
  error: string | null;
}

export interface ScrapeResult {
  raw_text: string;
  title: string;
  company: string;
  source: string;
}

export interface GeneratedContent {
  content: string;
  content_type: string;
}

// ─── Setup & Health ────────────────────────────────────────────────

export async function setup(): Promise<SetupStatus> {
  return invoke('setup');
}

export async function getHealth(): Promise<HealthResponse> {
  return invoke('health');
}

// ─── Profile ───────────────────────────────────────────────────────

export async function getProfile(): Promise<Profile> {
  return invoke('get_profile');
}

export async function saveProfile(profile: Profile): Promise<Profile> {
  return invoke('save_profile', { profile });
}

export async function resetProfile(): Promise<void> {
  return invoke('reset_profile');
}

// ─── CVs ───────────────────────────────────────────────────────────

export async function listCvs(): Promise<CvInfo[]> {
  return invoke('list_cvs');
}

export async function uploadCv(path: string): Promise<CvInfo> {
  return invoke('upload_cv', { path });
}

export async function getCvContent(filename: string): Promise<string> {
  return invoke('get_cv_content', { filename });
}

export async function deleteCv(filename: string): Promise<void> {
  return invoke('delete_cv', { filename });
}

export async function extractProfileFromCv(filename: string): Promise<Profile> {
  return invoke('extract_profile_from_cv', { filename });
}

// ─── Jobs ──────────────────────────────────────────────────────────

export async function listJobs(): Promise<JobOffer[]> {
  return invoke('list_jobs');
}

export async function addJob(request: {
  raw_description?: string;
  url?: string;
  company?: string;
  position?: string;
  location?: string;
}): Promise<JobOffer> {
  return invoke('add_job', { request });
}

export async function deleteJob(jobId: string): Promise<void> {
  return invoke('delete_job', { jobId });
}

export async function scrapeJobUrl(url: string): Promise<ScrapeResult> {
  return invoke('scrape_job_url_cmd', { request: { url } });
}

// ─── Generation (streaming via Tauri events) ───────────────────────

export async function generateCoverLetter(request: {
  cv_filename: string;
  job_id: string;
  language: string;
  recruiter_name?: string;
}): Promise<void> {
  return invoke('generate_cover_letter', { request });
}

export async function generateRecruiterMessage(request: {
  cv_filename: string;
  job_id: string;
  message_type: string;
  language: string;
  recruiter_name?: string;
}): Promise<void> {
  return invoke('generate_recruiter_message', { request });
}

export async function generateInterviewAnswer(request: {
  question: string;
  cv_filename: string;
  job_id: string;
  language: string;
}): Promise<void> {
  return invoke('generate_interview_answer', { request });
}

export async function generateInterviewQuestions(): Promise<GeneratedContent> {
  return invoke('generate_interview_questions');
}
