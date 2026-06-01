use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::sync::RwLock;

/// Application state shared across commands
pub struct AppState {
    pub data_dir: RwLock<PathBuf>,
    pub ollama_url: RwLock<String>,
    pub llm_model: RwLock<String>,
    /// User profile data
    pub profile: RwLock<Profile>,
    /// Loaded CV texts (filename -> extracted text)
    pub cvs: RwLock<HashMap<String, String>>,
    /// Saved job offers (id -> job data)
    pub jobs: RwLock<HashMap<String, JobOffer>>,
}

#[derive(Default, Clone, Serialize, Deserialize)]
pub struct Profile {
    pub name: String,
    pub email: String,
    pub phone: String,
    pub linkedin_url: String,
    pub location: String,
    pub title: String,
    pub summary: String,
    pub key_skills: Vec<String>,
    pub years_experience: f32,
    pub languages: Vec<String>,
    pub preferred_language: String,
    pub tone: String,
}

#[derive(Clone, Serialize, Deserialize)]
pub struct JobOffer {
    pub id: String,
    pub company: String,
    pub position: String,
    pub location: String,
    pub raw_description: String,
    pub url: String,
    pub source: String,
    pub created_at: String,
    #[serde(default)]
    pub requirements: Vec<String>,
    #[serde(default)]
    pub tech_stack: Vec<String>,
}

impl AppState {
    pub fn new() -> Self {
        let data_dir = dirs::data_local_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("JobPilot");

        Self {
            data_dir: RwLock::new(data_dir),
            ollama_url: RwLock::new("http://localhost:11434".to_string()),
            llm_model: RwLock::new("llama3.2".to_string()),
            profile: RwLock::new(Profile::default()),
            cvs: RwLock::new(HashMap::new()),
            jobs: RwLock::new(HashMap::new()),
        }
    }
}
