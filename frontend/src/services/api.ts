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

export async function extractProfileFromLinkedin(text: string): Promise<Profile> {
  return invoke('extract_profile_from_linkedin', { text });
}

export async function extractProfileFromLinkedinUrl(url: string): Promise<Profile> {
  return invoke('extract_profile_from_linkedin_url', { url });
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

// ─── Autopilot ─────────────────────────────────────────────────────

export interface AutopilotStatus {
  spawned: boolean;
  healthy: boolean;
  port: number;
  session: {
    has_session: boolean;
    li_at_present?: boolean;
    jsessionid_present?: boolean;
    valid?: boolean | null;
  };
}

export interface SearchCriteria {
  keywords: string[];
  location: string;
  geo_id: string;
  remote: boolean;
  hybrid: boolean;
  onsite: boolean;
  experience_levels: string[];
  job_types: string[];
  posted_within_hours: number;
  excluded_companies: string[];
  required_keywords: string[];
  excluded_keywords: string[];
}

export interface AutopilotConfig {
  enabled: boolean;
  schedule_hour: number;
  schedule_minute: number;
  schedule_days: number[];
  max_connections_per_day: number;
  max_messages_per_day: number;
  max_applies_per_day: number;
  score_threshold: number;
  top_n_generate: number;
}

export interface QueueAction {
  id: number;
  job_id: string;
  action_type: 'apply_easy' | 'apply_external' | 'connect' | 'message';
  status: string;
  priority: number;
  content_draft: string;
  content_final: string;
  target_profile_url: string;
}

// Lifecycle
export async function autopilotStart(): Promise<{ running: boolean; port: number; cookies: string }> {
  return invoke('autopilot_start');
}

export async function autopilotStop(): Promise<boolean> {
  return invoke('autopilot_stop');
}

export async function autopilotStatus(): Promise<AutopilotStatus> {
  return invoke('autopilot_status');
}

export async function autopilotRefreshCookies(): Promise<{
  li_at_present: boolean;
  jsessionid_present: boolean;
}> {
  return invoke('autopilot_refresh_cookies');
}

// Generic proxy helpers to the Python service
export async function autopilotGet<T = unknown>(path: string): Promise<T> {
  return invoke('autopilot_get', { path });
}

export async function autopilotSend<T = unknown>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown
): Promise<T> {
  return invoke('autopilot_send', { method, path, body });
}

// Typed convenience wrappers
export async function getSearchCriteria(): Promise<SearchCriteria> {
  return autopilotGet<SearchCriteria>('/autopilot/settings/criteria');
}

export async function saveSearchCriteria(criteria: SearchCriteria): Promise<void> {
  await autopilotSend('PUT', '/autopilot/settings/criteria', criteria);
}

export async function getAutopilotConfig(): Promise<AutopilotConfig> {
  return autopilotGet<AutopilotConfig>('/autopilot/settings/config');
}

export async function saveAutopilotConfig(config: AutopilotConfig): Promise<void> {
  await autopilotSend('PUT', '/autopilot/settings/config', config);
}

export async function getQueue(): Promise<{ actions: QueueAction[] }> {
  return autopilotGet<{ actions: QueueAction[] }>('/autopilot/queue');
}

export interface DiscoveredJobRow {
  job_id: string;
  title: string;
  company: string;
  location: string;
  workplace_type: string;
  apply_method: string;
  external_url: string;
  score: number | null;
  recommendation: string;
  recruiter_name: string;
  recruiter_url: string;
  status: string;
  discovered_at?: string;
}

export interface DiscoveryResult {
  fetched: number;
  new: number;
  detailed: number;
  errors: number;
  stopped_reason: string;
}

export async function autopilotDiscover(): Promise<DiscoveryResult> {
  return autopilotSend<DiscoveryResult>('POST', '/autopilot/discover');
}

export async function getDiscoveredJobs(
  limit = 50,
  scoredOnly = false
): Promise<{ jobs: DiscoveredJobRow[]; total: number }> {
  const params = `?limit=${limit}&scored_only=${scoredOnly}`;
  return autopilotGet<{ jobs: DiscoveredJobRow[]; total: number }>(
    `/autopilot/jobs${params}`
  );
}

export interface PipelineStatusInfo {
  run_id: string | null;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';
  stage: string;
  progress: number;
  total: number;
  message: string;
  jobs_fetched: number;
  jobs_filtered: number;
  jobs_scored: number;
  jobs_queued: number;
}

export async function runPipeline(): Promise<{ started: boolean; status: PipelineStatusInfo }> {
  return autopilotSend('POST', '/autopilot/pipeline/run');
}

export async function cancelPipeline(): Promise<void> {
  await autopilotSend('POST', '/autopilot/pipeline/cancel');
}

export async function getPipelineStatus(): Promise<PipelineStatusInfo> {
  return autopilotGet<PipelineStatusInfo>('/autopilot/status');
}

export interface ExecutionResult {
  job_id: string;
  kind: string;
  status: string;
  detail: string;
  ats: string;
}

export async function executeApply(
  jobId: string,
  autoSubmit = false
): Promise<ExecutionResult> {
  return autopilotSend<ExecutionResult>('POST', '/autopilot/execute/apply', {
    job_id: jobId,
    auto_submit: autoSubmit,
  });
}
