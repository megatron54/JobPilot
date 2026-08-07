use reqwest::Client;
use serde::Deserialize;
use std::process::Command;
use std::time::Duration;

#[derive(Deserialize)]
struct TagsResponse {
    models: Vec<ModelInfo>,
}

#[derive(Deserialize)]
struct ModelInfo {
    name: String,
}

/// Check if Ollama is reachable
pub async fn is_running(base_url: &str) -> bool {
    let client = match Client::builder().timeout(Duration::from_secs(2)).build() {
        Ok(c) => c,
        Err(_) => return false,
    };
    client
        .get(format!("{base_url}/api/tags"))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

/// Try to start Ollama if not running (Windows)
pub fn try_start() -> bool {
    // Common install locations on Windows
    let paths = [
        std::env::var("LOCALAPPDATA")
            .map(|p| format!("{p}\\Programs\\Ollama\\ollama.exe"))
            .unwrap_or_default(),
        "C:\\Program Files\\Ollama\\ollama.exe".to_string(),
        "ollama".to_string(), // PATH
    ];

    for path in &paths {
        if path.is_empty() {
            continue;
        }
        if let Ok(_child) = Command::new(path)
            .arg("serve")
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .spawn()
        {
            return true;
        }
    }
    false
}

/// Ensure Ollama is running — start it if needed, wait for it
pub async fn ensure_running(base_url: &str) -> Result<(), String> {
    if is_running(base_url).await {
        return Ok(());
    }

    // Try to start
    if !try_start() {
        return Err(
            "Ollama is not installed. Please install it from https://ollama.com".to_string(),
        );
    }

    // Wait up to 15 seconds for it to be ready
    for _ in 0..30 {
        tokio::time::sleep(Duration::from_millis(500)).await;
        if is_running(base_url).await {
            return Ok(());
        }
    }

    Err("Ollama was started but failed to respond. Please check your installation.".to_string())
}

/// Check if a model is available, pull it if not
pub async fn ensure_model(base_url: &str, model: &str) -> Result<(), String> {
    let client = Client::new();

    // Check if model exists
    let resp = client
        .get(format!("{base_url}/api/tags"))
        .send()
        .await
        .map_err(|e| format!("Failed to check models: {e}"))?;

    let tags: TagsResponse = resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse model list: {e}"))?;

    let model_base = model.split(':').next().unwrap_or(model);
    let has_model = tags.models.iter().any(|m| {
        let m_base = m.name.split(':').next().unwrap_or(&m.name);
        m_base == model_base
    });

    if has_model {
        return Ok(());
    }

    // Pull the model
    let pull_resp = client
        .post(format!("{base_url}/api/pull"))
        .json(&serde_json::json!({"name": model, "stream": false}))
        .timeout(Duration::from_secs(600))
        .send()
        .await
        .map_err(|e| format!("Failed to pull model {model}: {e}"))?;

    if !pull_resp.status().is_success() {
        let body = pull_resp.text().await.unwrap_or_default();
        return Err(format!("Failed to pull model {model}: {body}"));
    }

    Ok(())
}
