use crate::document::{extract_text, SUPPORTED_EXTENSIONS};
use crate::llm::{chat_completion, stream_chat, ChatMessage};
use crate::ollama;
use crate::scraper as job_scraper;
use crate::state::{AppState, JobOffer, Profile};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, State};

// ─── Data structures ───────────────────────────────────────────────────────────

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub ollama_status: String,
    pub llm_model: String,
    pub cvs_loaded: usize,
    pub jobs_count: usize,
}

#[derive(Serialize)]
pub struct SetupStatus {
    pub ollama_running: bool,
    pub llm_ready: bool,
    pub error: Option<String>,
}

#[derive(Serialize)]
pub struct CvInfo {
    pub filename: String,
    pub char_count: usize,
}

#[derive(Serialize)]
pub struct GeneratedContent {
    pub content: String,
    pub content_type: String,
}

#[derive(Deserialize)]
pub struct GenerateCoverLetterRequest {
    pub cv_filename: String,
    pub job_id: String,
    pub language: String,
    pub recruiter_name: Option<String>,
}

#[derive(Deserialize)]
pub struct GenerateMessageRequest {
    pub cv_filename: String,
    pub job_id: String,
    pub message_type: String,
    pub language: String,
    pub recruiter_name: Option<String>,
}

#[derive(Deserialize)]
pub struct GenerateAnswerRequest {
    pub question: String,
    pub cv_filename: String,
    pub job_id: String,
    pub language: String,
}

#[derive(Deserialize)]
pub struct AddJobRequest {
    pub raw_description: Option<String>,
    pub url: Option<String>,
    pub company: Option<String>,
    pub position: Option<String>,
    pub location: Option<String>,
}

#[derive(Deserialize)]
pub struct ScrapeRequest {
    pub url: String,
}

#[derive(Serialize)]
pub struct ScrapeResult {
    pub raw_text: String,
    pub title: String,
    pub company: String,
    pub source: String,
}

// ─── Setup & Health ────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn setup(state: State<'_, AppState>) -> Result<SetupStatus, String> {
    let url = state.ollama_url.read().await.clone();
    let llm_model = state.llm_model.read().await.clone();

    // Ensure data directories exist
    let data_dir = state.data_dir.read().await.clone();
    let _ = fs::create_dir_all(data_dir.join("cvs"));
    let _ = fs::create_dir_all(data_dir.join("jobs"));
    let _ = fs::create_dir_all(data_dir.join("outputs"));

    // Load existing data
    load_persisted_data(&state).await;

    if let Err(e) = ollama::ensure_running(&url).await {
        return Ok(SetupStatus {
            ollama_running: false,
            llm_ready: false,
            error: Some(e),
        });
    }

    let llm_ready = ollama::ensure_model(&url, &llm_model).await.is_ok();

    Ok(SetupStatus {
        ollama_running: true,
        llm_ready,
        error: None,
    })
}

#[tauri::command]
pub async fn health(state: State<'_, AppState>) -> Result<HealthResponse, String> {
    let url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();

    let ollama_status = if ollama::is_running(&url).await {
        "connected".to_string()
    } else {
        "disconnected".to_string()
    };

    let cvs = state.cvs.read().await;
    let jobs = state.jobs.read().await;

    Ok(HealthResponse {
        status: "ok".to_string(),
        ollama_status,
        llm_model: model,
        cvs_loaded: cvs.len(),
        jobs_count: jobs.len(),
    })
}

// ─── Profile ───────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn get_profile(state: State<'_, AppState>) -> Result<Profile, String> {
    let profile = state.profile.read().await.clone();
    Ok(profile)
}

#[tauri::command]
pub async fn save_profile(state: State<'_, AppState>, profile: Profile) -> Result<Profile, String> {
    let data_dir = state.data_dir.read().await.clone();

    // Save to disk
    let path = data_dir.join("profile.json");
    let json = serde_json::to_string_pretty(&profile).map_err(|e| e.to_string())?;
    fs::write(&path, &json).map_err(|e| format!("Failed to save profile: {e}"))?;

    // Update state
    let mut p = state.profile.write().await;
    *p = profile.clone();

    Ok(profile)
}

// ─── CVs ───────────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn list_cvs(state: State<'_, AppState>) -> Result<Vec<CvInfo>, String> {
    let cvs = state.cvs.read().await;
    let mut list: Vec<CvInfo> = cvs
        .iter()
        .map(|(name, text)| CvInfo {
            filename: name.clone(),
            char_count: text.len(),
        })
        .collect();
    list.sort_by(|a, b| a.filename.cmp(&b.filename));
    Ok(list)
}

#[tauri::command]
pub async fn upload_cv(state: State<'_, AppState>, path: String) -> Result<CvInfo, String> {
    let src = PathBuf::from(&path);
    if !src.exists() {
        return Err("File not found".to_string());
    }

    let ext = src
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    if !SUPPORTED_EXTENSIONS.contains(&ext.as_str()) {
        return Err(format!("Unsupported file type: .{ext}. Supported: pdf, docx, txt, md"));
    }

    let filename = src.file_name().unwrap().to_string_lossy().to_string();
    let data_dir = state.data_dir.read().await.clone();
    let cvs_dir = data_dir.join("cvs");
    fs::create_dir_all(&cvs_dir).map_err(|e| e.to_string())?;

    // Copy file
    let dest = cvs_dir.join(&filename);
    fs::copy(&src, &dest).map_err(|e| format!("Failed to copy file: {e}"))?;

    // Extract text
    let text = extract_text(&dest)?;
    let char_count = text.len();

    // Save extracted text
    let text_path = cvs_dir.join(format!("{}.txt", filename));
    let _ = fs::write(&text_path, &text);

    // Update state
    let mut cvs = state.cvs.write().await;
    cvs.insert(filename.clone(), text);

    Ok(CvInfo { filename, char_count })
}

#[tauri::command]
pub async fn get_cv_content(state: State<'_, AppState>, filename: String) -> Result<String, String> {
    let cvs = state.cvs.read().await;
    cvs.get(&filename)
        .cloned()
        .ok_or_else(|| format!("CV not found: {filename}"))
}

#[tauri::command]
pub async fn delete_cv(state: State<'_, AppState>, filename: String) -> Result<(), String> {
    let data_dir = state.data_dir.read().await.clone();
    let cvs_dir = data_dir.join("cvs");

    // Remove the file
    let file_path = cvs_dir.join(&filename);
    if file_path.exists() {
        fs::remove_file(&file_path).map_err(|e| format!("Failed to delete file: {e}"))?;
    }

    // Remove the extracted .txt
    let txt_path = cvs_dir.join(format!("{}.txt", filename));
    if txt_path.exists() {
        let _ = fs::remove_file(&txt_path);
    }

    // Remove from state
    let mut cvs = state.cvs.write().await;
    cvs.remove(&filename);

    Ok(())
}

#[tauri::command]
pub async fn reset_profile(state: State<'_, AppState>) -> Result<(), String> {
    let data_dir = state.data_dir.read().await.clone();
    let path = data_dir.join("profile.json");

    // Delete from disk
    if path.exists() {
        fs::remove_file(&path).map_err(|e| format!("Failed to delete profile: {e}"))?;
    }

    // Reset state to default
    let mut profile = state.profile.write().await;
    *profile = Profile::default();

    Ok(())
}

/// Extract profile information from a CV using AI
#[tauri::command]
pub async fn extract_profile_from_cv(state: State<'_, AppState>, filename: String) -> Result<Profile, String> {
    let ollama_url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();
    let client = Client::new();

    let cvs = state.cvs.read().await;
    let cv_text = cvs.get(&filename)
        .cloned()
        .ok_or_else(|| format!("CV not found: {filename}"))?;
    drop(cvs);

    let prompt = format!(
        r#"Analyze this CV/resume thoroughly and extract ALL information. Return ONLY valid JSON.

CV TEXT:
{}

INSTRUCTIONS:
- "title": The person's current professional title or degree/specialization (e.g. "Ingeniero de Telecomunicaciones", "Full Stack Developer"). Look at the header or first section.
- "linkedin_url": Extract the ACTUAL URL (https://linkedin.com/in/...), NOT the display text. If you only see the word "LinkedIn" as a link, leave empty "".
- "key_skills": Extract ALL technical and soft skills mentioned anywhere in the CV. Include programming languages, frameworks, tools, methodologies, certifications, areas of expertise. Be thorough - list at least 10-15 if present.
- "years_experience": Can be decimal (e.g. 0.5 for 6 months). If the person is a student with internships, use 0.5-1. Calculate from work experience dates if possible.
- "summary": Write a 2-3 sentence professional summary based on the CV content. Use the SAME language as the CV.
- "languages": Spoken languages (e.g. ["Español", "English", "Français"])
- Use proper accents and special characters (á, é, í, ó, ú, ñ, ü, ç)

Return this exact JSON structure:
{{
  "name": "",
  "email": "",
  "phone": "",
  "linkedin_url": "",
  "location": "",
  "title": "",
  "summary": "",
  "key_skills": [],
  "years_experience": 0,
  "languages": []
}}

CRITICAL: Return ONLY the JSON object. No markdown, no explanation."#,
        &cv_text[..cv_text.len().min(6000)]
    );

    let messages = vec![
        ChatMessage { role: "system".to_string(), content: "You are a CV parser. Extract structured data from resumes. Return ONLY valid JSON with proper Unicode characters (accents, ñ, etc). Be thorough with skills extraction.".to_string() },
        ChatMessage { role: "user".to_string(), content: prompt },
    ];

    let response = chat_completion(&client, &ollama_url, &model, messages, 0.1).await?;

    // Parse JSON from response
    let clean = response.trim().trim_start_matches("```json").trim_start_matches("```").trim_end_matches("```").trim();
    
    let extracted: serde_json::Value = serde_json::from_str(clean)
        .map_err(|e| format!("Failed to parse AI response as JSON: {e}\nRaw: {clean}"))?;

    // Build profile from extracted data, preserving existing tone/language preferences
    let current_profile = state.profile.read().await.clone();
    
    let profile = Profile {
        name: extracted["name"].as_str().unwrap_or("").to_string(),
        email: extracted["email"].as_str().unwrap_or("").to_string(),
        phone: extracted["phone"].as_str().unwrap_or("").to_string(),
        linkedin_url: extracted["linkedin_url"].as_str().unwrap_or("").to_string(),
        location: extracted["location"].as_str().unwrap_or("").to_string(),
        title: extracted["title"].as_str().unwrap_or("").to_string(),
        summary: extracted["summary"].as_str().unwrap_or("").to_string(),
        key_skills: extracted["key_skills"].as_array()
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default(),
        years_experience: extracted["years_experience"].as_f64().unwrap_or(0.0) as f32,
        languages: extracted["languages"].as_array()
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default(),
        // Preserve user preferences
        preferred_language: if current_profile.preferred_language.is_empty() { "es".to_string() } else { current_profile.preferred_language },
        tone: if current_profile.tone.is_empty() { "professional".to_string() } else { current_profile.tone },
    };

    // Auto-save the extracted profile
    let data_dir = state.data_dir.read().await.clone();
    let path = data_dir.join("profile.json");
    let json = serde_json::to_string_pretty(&profile).map_err(|e| e.to_string())?;
    fs::write(&path, &json).map_err(|e| format!("Failed to save profile: {e}"))?;

    // Update state
    *state.profile.write().await = profile.clone();

    Ok(profile)
}

/// Extract profile from pasted LinkedIn profile text
#[tauri::command]
pub async fn extract_profile_from_linkedin(state: State<'_, AppState>, text: String) -> Result<Profile, String> {
    let ollama_url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();
    let client = Client::new();

    if text.trim().len() < 50 {
        return Err("Not enough text. Copy all the text from your LinkedIn profile page and paste it here.".to_string());
    }

    let clean_text = text.trim().to_string();

    let prompt = format!(
        r#"Extract professional information from this LinkedIn profile text. Return ONLY valid JSON.

LINKEDIN PROFILE TEXT:
{}

INSTRUCTIONS:
- "title": Their headline/current position
- "linkedin_url": If you find a linkedin.com URL in the text, use it. Otherwise leave empty "".
- "key_skills": Extract ALL skills, technologies, tools, areas of expertise mentioned. Be thorough.
- "years_experience": Calculate from work experience dates. Can be decimal (0.5 = 6 months)
- "summary": Their About section or a summary based on their experience
- "languages": Spoken languages listed
- Use proper accents and special characters (á, é, í, ó, ú, ñ, ü, ç)

Return this exact JSON:
{{
  "name": "",
  "email": "",
  "phone": "",
  "linkedin_url": "",
  "location": "",
  "title": "",
  "summary": "",
  "key_skills": [],
  "years_experience": 0,
  "languages": []
}}

CRITICAL: Return ONLY the JSON. No explanation."#,
        &clean_text[..clean_text.len().min(8000)]
    );

    let messages = vec![
        ChatMessage { role: "system".to_string(), content: "You parse LinkedIn profiles into structured data. Return ONLY valid JSON with proper Unicode characters (accents, ñ, etc). Be very thorough extracting skills.".to_string() },
        ChatMessage { role: "user".to_string(), content: prompt },
    ];

    let response = chat_completion(&client, &ollama_url, &model, messages, 0.1).await?;

    let clean = response.trim().trim_start_matches("```json").trim_start_matches("```").trim_end_matches("```").trim();
    
    let extracted: serde_json::Value = serde_json::from_str(clean)
        .map_err(|e| format!("Failed to parse AI response: {e}\nRaw: {clean}"))?;

    let current_profile = state.profile.read().await.clone();
    
    let profile = Profile {
        name: extracted["name"].as_str().unwrap_or("").to_string(),
        email: if extracted["email"].as_str().unwrap_or("").is_empty() { current_profile.email.clone() } else { extracted["email"].as_str().unwrap_or("").to_string() },
        phone: if extracted["phone"].as_str().unwrap_or("").is_empty() { current_profile.phone.clone() } else { extracted["phone"].as_str().unwrap_or("").to_string() },
        linkedin_url: extracted["linkedin_url"].as_str().unwrap_or("").to_string(),
        location: extracted["location"].as_str().unwrap_or("").to_string(),
        title: extracted["title"].as_str().unwrap_or("").to_string(),
        summary: extracted["summary"].as_str().unwrap_or("").to_string(),
        key_skills: {
            let mut skills: Vec<String> = extracted["key_skills"].as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                .unwrap_or_default();
            // Merge with existing skills
            for s in &current_profile.key_skills {
                if !skills.contains(s) {
                    skills.push(s.clone());
                }
            }
            skills
        },
        years_experience: extracted["years_experience"].as_f64().unwrap_or(0.0) as f32,
        languages: extracted["languages"].as_array()
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default(),
        preferred_language: if current_profile.preferred_language.is_empty() { "es".to_string() } else { current_profile.preferred_language },
        tone: if current_profile.tone.is_empty() { "professional".to_string() } else { current_profile.tone },
    };

    // Auto-save
    let data_dir = state.data_dir.read().await.clone();
    let path = data_dir.join("profile.json");
    let json = serde_json::to_string_pretty(&profile).map_err(|e| e.to_string())?;
    fs::write(&path, &json).map_err(|e| format!("Failed to save profile: {e}"))?;

    *state.profile.write().await = profile.clone();

    Ok(profile)
}

/// Extract profile from a LinkedIn URL using browser cookies for authentication
#[tauri::command]
pub async fn extract_profile_from_linkedin_url(state: State<'_, AppState>, url: String) -> Result<Profile, String> {
    use crate::linkedin;

    let ollama_url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();
    let client = Client::new();

    // Validate URL
    if !url.contains("linkedin.com/in/") {
        return Err("Please provide a valid LinkedIn profile URL (e.g., https://www.linkedin.com/in/username)".to_string());
    }

    // Get li_at cookie from browser
    let li_at = linkedin::get_linkedin_cookie()?;

    // Fetch the profile page
    let html = linkedin::fetch_linkedin_profile(&url, &li_at).await?;

    // Extract text from HTML
    let clean_text = linkedin::extract_text_from_html(&html);

    if clean_text.len() < 100 {
        return Err("Could not extract enough text from the LinkedIn profile. The page may be empty or require different permissions.".to_string());
    }

    let prompt = format!(
        r#"Extract professional information from this LinkedIn profile page content. Return ONLY valid JSON.

LINKEDIN PROFILE TEXT:
{}

The LinkedIn profile URL is: {}

INSTRUCTIONS:
- "name": Full name of the person
- "title": Their headline/current position
- "linkedin_url": Use the URL provided above
- "key_skills": Extract ALL skills, technologies, tools, areas of expertise mentioned. Be very thorough (aim for 10-20+ skills).
- "years_experience": Calculate from work experience dates. Can be decimal (0.5 = 6 months)
- "summary": Their About section or a summary based on their experience
- "languages": Spoken languages listed
- Use proper accents and special characters (á, é, í, ó, ú, ñ, ü, ç)

Return this exact JSON:
{{
  "name": "",
  "email": "",
  "phone": "",
  "linkedin_url": "{}",
  "location": "",
  "title": "",
  "summary": "",
  "key_skills": [],
  "years_experience": 0,
  "languages": []
}}

CRITICAL: Return ONLY the JSON. No explanation."#,
        &clean_text[..clean_text.len().min(8000)],
        url,
        url
    );

    let messages = vec![
        ChatMessage { role: "system".to_string(), content: "You parse LinkedIn profiles into structured data. Return ONLY valid JSON with proper Unicode characters (accents, ñ, etc). Be very thorough extracting skills.".to_string() },
        ChatMessage { role: "user".to_string(), content: prompt },
    ];

    let response = chat_completion(&client, &ollama_url, &model, messages, 0.1).await?;

    let clean = response.trim().trim_start_matches("```json").trim_start_matches("```").trim_end_matches("```").trim();
    
    let extracted: serde_json::Value = serde_json::from_str(clean)
        .map_err(|e| format!("Failed to parse AI response: {e}\nRaw: {clean}"))?;

    let current_profile = state.profile.read().await.clone();
    
    let profile = Profile {
        name: extracted["name"].as_str().unwrap_or("").to_string(),
        email: if extracted["email"].as_str().unwrap_or("").is_empty() { current_profile.email.clone() } else { extracted["email"].as_str().unwrap_or("").to_string() },
        phone: if extracted["phone"].as_str().unwrap_or("").is_empty() { current_profile.phone.clone() } else { extracted["phone"].as_str().unwrap_or("").to_string() },
        linkedin_url: extracted["linkedin_url"].as_str().unwrap_or("").to_string(),
        location: extracted["location"].as_str().unwrap_or("").to_string(),
        title: extracted["title"].as_str().unwrap_or("").to_string(),
        summary: extracted["summary"].as_str().unwrap_or("").to_string(),
        key_skills: {
            let mut skills: Vec<String> = extracted["key_skills"].as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                .unwrap_or_default();
            // Merge with existing skills
            for s in &current_profile.key_skills {
                if !skills.contains(s) {
                    skills.push(s.clone());
                }
            }
            skills
        },
        years_experience: extracted["years_experience"].as_f64().unwrap_or(0.0) as f32,
        languages: extracted["languages"].as_array()
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default(),
        preferred_language: if current_profile.preferred_language.is_empty() { "es".to_string() } else { current_profile.preferred_language },
        tone: if current_profile.tone.is_empty() { "professional".to_string() } else { current_profile.tone },
    };

    // Auto-save
    let data_dir = state.data_dir.read().await.clone();
    let path = data_dir.join("profile.json");
    let json = serde_json::to_string_pretty(&profile).map_err(|e| e.to_string())?;
    fs::write(&path, &json).map_err(|e| format!("Failed to save profile: {e}"))?;

    *state.profile.write().await = profile.clone();

    Ok(profile)
}

// ─── Jobs ──────────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn list_jobs(state: State<'_, AppState>) -> Result<Vec<JobOffer>, String> {
    let jobs = state.jobs.read().await;
    let mut list: Vec<JobOffer> = jobs.values().cloned().collect();
    list.sort_by(|a, b| b.created_at.cmp(&a.created_at));
    Ok(list)
}

#[tauri::command]
pub async fn add_job(state: State<'_, AppState>, request: AddJobRequest) -> Result<JobOffer, String> {
    let mut raw_description = request.raw_description.unwrap_or_default();
    let mut company = request.company.unwrap_or_default();
    let mut position = request.position.unwrap_or_default();
    let location = request.location.unwrap_or_default();
    let url = request.url.unwrap_or_default();
    let mut source = "manual".to_string();

    // If URL provided but no description, scrape it
    if !url.is_empty() && raw_description.is_empty() {
        let scraped = job_scraper::scrape_job_url(&url).await?;
        raw_description = scraped.raw_text;
        source = scraped.source;
        if company.is_empty() {
            company = scraped.company;
        }
        if position.is_empty() {
            position = scraped.title;
        }
    }

    if raw_description.is_empty() {
        return Err("Either a job description or URL must be provided".to_string());
    }

    // Generate ID
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let company_slug = company.to_lowercase().replace(' ', "_");
    let position_slug = position.to_lowercase().replace(' ', "_");
    let id = format!("{}_{}_{}",
        if company_slug.is_empty() { "unknown" } else { &company_slug },
        if position_slug.is_empty() { "unknown" } else { &position_slug },
        timestamp
    );

    let job = JobOffer {
        id: id.clone(),
        company,
        position,
        location,
        raw_description,
        url,
        source,
        created_at: chrono_now(),
        requirements: vec![],
        tech_stack: vec![],
    };

    // Persist to disk
    let data_dir = state.data_dir.read().await.clone();
    let jobs_dir = data_dir.join("jobs");
    fs::create_dir_all(&jobs_dir).map_err(|e| e.to_string())?;
    let job_path = jobs_dir.join(format!("{}.json", &id));
    let json = serde_json::to_string_pretty(&job).map_err(|e| e.to_string())?;
    fs::write(&job_path, &json).map_err(|e| format!("Failed to save job: {e}"))?;

    // Update state
    let mut jobs = state.jobs.write().await;
    jobs.insert(id, job.clone());

    Ok(job)
}

#[tauri::command]
pub async fn delete_job(state: State<'_, AppState>, job_id: String) -> Result<(), String> {
    let data_dir = state.data_dir.read().await.clone();
    let job_path = data_dir.join("jobs").join(format!("{}.json", &job_id));
    if job_path.exists() {
        fs::remove_file(&job_path).map_err(|e| e.to_string())?;
    }

    let mut jobs = state.jobs.write().await;
    jobs.remove(&job_id);
    Ok(())
}

#[tauri::command]
pub async fn scrape_job_url_cmd(request: ScrapeRequest) -> Result<ScrapeResult, String> {
    let scraped = job_scraper::scrape_job_url(&request.url).await?;
    Ok(ScrapeResult {
        raw_text: scraped.raw_text,
        title: scraped.title,
        company: scraped.company,
        source: scraped.source,
    })
}

// ─── Generation ────────────────────────────────────────────────────────────────

#[tauri::command]
pub async fn generate_cover_letter(
    app: AppHandle,
    state: State<'_, AppState>,
    request: GenerateCoverLetterRequest,
) -> Result<(), String> {
    let ollama_url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();
    let client = Client::new();

    let cv_text = get_cv_text(&state, &request.cv_filename).await?;
    let job = get_job_data(&state, &request.job_id).await?;
    let profile = state.profile.read().await.clone();

    let lang = match request.language.as_str() {
        "es" => "Spanish (use proper accents: á, é, í, ó, ú, ñ, ü)",
        "fr" => "French (use proper accents: é, è, ê, ë, à, ç, ô, î, ù)",
        "de" => "German (use proper umlauts: ä, ö, ü, ß)",
        "pt" => "Portuguese (use proper accents: ã, õ, á, é, ç, â, ê)",
        _ => "English",
    };
    let recruiter = request.recruiter_name.unwrap_or_default();

    let system = format!(
        "You are an expert professional cover letter writer. Write personalized, effective cover letters.\n\
         STRUCTURE:\n\
         1. Personalized greeting (to recruiter by name if available)\n\
         2. Brief profile summary\n\
         3. Connection to the role and company\n\
         4. Value proposition based on experience\n\
         5. Professional closing\n\n\
         RULES:\n\
         - Always personalize for the company and role\n\
         - Highlight CV skills matching requirements\n\
         - Be concise (max 4 paragraphs)\n\
         - DO NOT invent experience not in the CV\n\
         - Write ENTIRELY in {lang}\n\
         - Use correct diacritics and special characters for the language"
    );

    let user_prompt = format!(
        "Generate a cover letter based on:\n\n\
         --- CV ---\n{cv_text}\n\n\
         --- JOB ---\nCompany: {company}\nPosition: {position}\nDescription: {desc}\n\n\
         --- CANDIDATE ---\nName: {name}\nTitle: {title}\nSkills: {skills}\nExperience: {exp} years\n\
         {recruiter_line}\n\
         Write ONLY the letter, no meta-commentary.",
        cv_text = &cv_text[..cv_text.len().min(4000)],
        company = job.company,
        position = job.position,
        desc = &job.raw_description[..job.raw_description.len().min(2000)],
        name = profile.name,
        title = profile.title,
        skills = profile.key_skills.join(", "),
        exp = profile.years_experience,
        recruiter_line = if recruiter.is_empty() { String::new() } else { format!("Recruiter name: {recruiter}") },
    );

    let messages = vec![
        ChatMessage { role: "system".to_string(), content: system },
        ChatMessage { role: "user".to_string(), content: user_prompt },
    ];

    stream_chat(&app, &client, &ollama_url, &model, messages, 0.7, "generate-token").await?;
    Ok(())
}

#[tauri::command]
pub async fn generate_recruiter_message(
    app: AppHandle,
    state: State<'_, AppState>,
    request: GenerateMessageRequest,
) -> Result<(), String> {
    let ollama_url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();
    let client = Client::new();

    let cv_text = get_cv_text(&state, &request.cv_filename).await?;
    let job = get_job_data(&state, &request.job_id).await?;
    let profile = state.profile.read().await.clone();

    let lang = match request.language.as_str() {
        "es" => "Spanish (use proper accents: á, é, í, ó, ú, ñ, ü)",
        "fr" => "French (use proper accents: é, è, ê, ë, à, ç, ô, î, ù)",
        "de" => "German (use proper umlauts: ä, ö, ü, ß)",
        "pt" => "Portuguese (use proper accents: ã, õ, á, é, ç, â, ê)",
        _ => "English",
    };
    let recruiter = request.recruiter_name.unwrap_or_default();

    let system = format!(
        "You are an expert in professional networking.\n\
         Create effective direct messages for recruiters on LinkedIn.\n\
         RULES:\n\
         - Max 300 words (LinkedIn limit)\n\
         - Be direct but respectful\n\
         - Show you researched the company\n\
         - End with a question or clear CTA\n\
         - Write ENTIRELY in {lang}\n\
         - Use correct diacritics and special characters for the language"
    );

    let user_prompt = format!(
        "Generate a {msg_type} message for a recruiter.\n\n\
         --- CANDIDATE ---\nName: {name}\nTitle: {title}\nSkills: {skills}\n\n\
         --- CV HIGHLIGHTS ---\n{cv_text}\n\n\
         --- JOB ---\nCompany: {company}\nPosition: {position}\nDescription: {desc}\n\
         {recruiter_line}\n\
         Write ONLY the message.",
        msg_type = request.message_type.replace('_', " "),
        name = profile.name,
        title = profile.title,
        skills = profile.key_skills.join(", "),
        cv_text = &cv_text[..cv_text.len().min(2000)],
        company = job.company,
        position = job.position,
        desc = &job.raw_description[..job.raw_description.len().min(1000)],
        recruiter_line = if recruiter.is_empty() { String::new() } else { format!("Recruiter name: {recruiter}") },
    );

    let messages = vec![
        ChatMessage { role: "system".to_string(), content: system },
        ChatMessage { role: "user".to_string(), content: user_prompt },
    ];

    stream_chat(&app, &client, &ollama_url, &model, messages, 0.7, "generate-token").await?;
    Ok(())
}

#[tauri::command]
pub async fn generate_interview_answer(
    app: AppHandle,
    state: State<'_, AppState>,
    request: GenerateAnswerRequest,
) -> Result<(), String> {
    let ollama_url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();
    let client = Client::new();

    let cv_text = get_cv_text(&state, &request.cv_filename).await?;
    let job = get_job_data(&state, &request.job_id).await?;
    let profile = state.profile.read().await.clone();

    let lang = match request.language.as_str() {
        "es" => "Spanish (use proper accents: á, é, í, ó, ú, ñ, ü)",
        "fr" => "French (use proper accents: é, è, ê, ë, à, ç, ô, î, ù)",
        "de" => "German (use proper umlauts: ä, ö, ü, ß)",
        "pt" => "Portuguese (use proper accents: ã, õ, á, é, ç, â, ê)",
        _ => "English",
    };

    let system = format!(
        "You are an expert interview coach.\n\
         Use STAR method when applicable.\n\
         Base answers on REAL experience from the CV.\n\
         DO NOT invent experiences.\n\
         Include delivery tips after the answer.\n\
         Write ENTIRELY in {lang}\n\
         Use correct diacritics and special characters for the language"
    );

    let user_prompt = format!(
        "Answer this interview question:\n\nQUESTION: \"{question}\"\n\n\
         --- CV ---\n{cv_text}\n\n\
         --- CANDIDATE ---\nName: {name}\nTitle: {title}\nSkills: {skills}\nExperience: {exp} years\n\n\
         --- TARGET POSITION ---\nCompany: {company}\nPosition: {position}\n\n\
         Provide:\n1. A structured answer\n2. Delivery tips",
        question = request.question,
        cv_text = &cv_text[..cv_text.len().min(3000)],
        name = profile.name,
        title = profile.title,
        skills = profile.key_skills.join(", "),
        exp = profile.years_experience,
        company = job.company,
        position = job.position,
    );

    let messages = vec![
        ChatMessage { role: "system".to_string(), content: system },
        ChatMessage { role: "user".to_string(), content: user_prompt },
    ];

    stream_chat(&app, &client, &ollama_url, &model, messages, 0.7, "generate-token").await?;
    Ok(())
}

#[tauri::command]
pub async fn generate_interview_questions(
    state: State<'_, AppState>,
) -> Result<GeneratedContent, String> {
    let ollama_url = state.ollama_url.read().await.clone();
    let model = state.llm_model.read().await.clone();
    let client = Client::new();
    let profile = state.profile.read().await.clone();

    // Get first job and cv if available
    let jobs = state.jobs.read().await;
    let job = jobs.values().next().cloned().unwrap_or(JobOffer {
        id: String::new(), company: "Unknown".to_string(), position: "Unknown".to_string(),
        location: String::new(), raw_description: String::new(), url: String::new(),
        source: String::new(), created_at: String::new(), requirements: vec![], tech_stack: vec![],
    });
    drop(jobs);

    let prompt = format!(
        "Generate 10 likely interview questions for this position:\n\n\
         Company: {company}\nPosition: {position}\nDescription: {desc}\n\n\
         Candidate: {title}, {exp} years experience\n\n\
         Include:\n- 3 technical questions\n- 3 behavioral (STAR)\n- 2 motivation/culture fit\n- 2 tricky questions\n\n\
         Format as numbered list with brief note on why they'd ask each.",
        company = job.company,
        position = job.position,
        desc = &job.raw_description[..job.raw_description.len().min(2000)],
        title = profile.title,
        exp = profile.years_experience,
    );

    let messages = vec![
        ChatMessage { role: "system".to_string(), content: "You are an expert interview coach.".to_string() },
        ChatMessage { role: "user".to_string(), content: prompt },
    ];

    let content = chat_completion(&client, &ollama_url, &model, messages, 0.7).await?;
    Ok(GeneratedContent { content, content_type: "interview_questions".to_string() })
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

async fn get_cv_text(state: &State<'_, AppState>, filename: &str) -> Result<String, String> {
    let cvs = state.cvs.read().await;
    cvs.get(filename)
        .cloned()
        .ok_or_else(|| format!("CV not found: {filename}. Upload it first."))
}

async fn get_job_data(state: &State<'_, AppState>, job_id: &str) -> Result<JobOffer, String> {
    let jobs = state.jobs.read().await;
    jobs.get(job_id)
        .cloned()
        .ok_or_else(|| format!("Job not found: {job_id}"))
}

async fn load_persisted_data(state: &State<'_, AppState>) {
    let data_dir = state.data_dir.read().await.clone();

    // Load profile
    let profile_path = data_dir.join("profile.json");
    if profile_path.exists() {
        if let Ok(content) = fs::read_to_string(&profile_path) {
            if let Ok(profile) = serde_json::from_str::<Profile>(&content) {
                *state.profile.write().await = profile;
            }
        }
    }

    // Load CVs (read extracted text files)
    let cvs_dir = data_dir.join("cvs");
    if cvs_dir.exists() {
        let mut cvs = state.cvs.write().await;
        if let Ok(entries) = fs::read_dir(&cvs_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                let path = entry.path();
                if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
                    if ext == "txt" {
                        // This is an extracted text file
                        if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                            // Only load if the original file exists
                            let has_original = SUPPORTED_EXTENSIONS.iter().any(|e| {
                                cvs_dir.join(format!("{}", stem.trim_end_matches(".txt"))).with_extension(e).exists()
                                    || stem.ends_with(&format!(".{e}"))
                            });
                            if has_original || stem.contains('.') {
                                if let Ok(text) = fs::read_to_string(&path) {
                                    // Key is the original filename (stem without .txt)
                                    cvs.insert(stem.to_string(), text);
                                }
                            }
                        }
                    } else if SUPPORTED_EXTENSIONS.contains(&ext.to_lowercase().as_str()) {
                        // Original CV file - extract if no .txt exists
                        let filename = path.file_name().unwrap().to_string_lossy().to_string();
                        let text_path = cvs_dir.join(format!("{}.txt", filename));
                        if !text_path.exists() {
                            if let Ok(text) = extract_text(&path) {
                                let _ = fs::write(&text_path, &text);
                                cvs.insert(filename, text);
                            }
                        }
                    }
                }
            }
        }
    }

    // Load jobs
    let jobs_dir = data_dir.join("jobs");
    if jobs_dir.exists() {
        let mut jobs = state.jobs.write().await;
        if let Ok(entries) = fs::read_dir(&jobs_dir) {
            for entry in entries.filter_map(|e| e.ok()) {
                let path = entry.path();
                if path.extension().and_then(|e| e.to_str()) == Some("json") {
                    if let Ok(content) = fs::read_to_string(&path) {
                        if let Ok(job) = serde_json::from_str::<JobOffer>(&content) {
                            jobs.insert(job.id.clone(), job);
                        }
                    }
                }
            }
        }
    }
}

fn chrono_now() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    // Simple ISO-ish format without chrono crate
    format!("{}", secs)
}
