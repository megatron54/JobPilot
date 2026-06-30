//! Tauri commands bridging the frontend to the Python autopilot service.
//!
//! The frontend calls these `invoke` commands; they manage the service
//! lifecycle and proxy control requests over local HTTP.

use crate::autopilot::{self, AutopilotService};
use crate::linkedin;
use crate::state::AppState;
use serde_json::Value;
use std::time::Duration;
use tauri::State;

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .map_err(|e| e.to_string())
}

/// Validate a proxy path to prevent SSRF / host-override via crafted paths.
/// Only relative paths under known autopilot prefixes are allowed.
fn validate_path(path: &str) -> Result<(), String> {
    if !path.starts_with('/') {
        return Err("Path must start with '/'".to_string());
    }
    // Reject anything that could change the authority component of the URL.
    if path.starts_with("//") || path.contains('@') || path.contains('\\') {
        return Err("Invalid path".to_string());
    }
    const ALLOWED: [&str; 3] = ["/autopilot/", "/health", "/shutdown"];
    if !ALLOWED.iter().any(|p| path == *p || path.starts_with(p)) {
        return Err("Path not allowed".to_string());
    }
    Ok(())
}

/// Start the autopilot service and forward LinkedIn cookies.
#[tauri::command]
pub async fn autopilot_start(
    app_state: State<'_, AppState>,
    service: State<'_, AutopilotService>,
) -> Result<Value, String> {
    let data_dir = app_state.data_dir.read().await.to_string_lossy().to_string();
    let ollama_url = app_state.ollama_url.read().await.clone();

    service.start(&data_dir, &ollama_url)?;
    let base = service.base_url();

    autopilot::wait_until_ready(&base, 20).await?;

    // Best-effort: extract and forward cookies (non-fatal if not logged in).
    let cookie_status = match linkedin::get_linkedin_cookies() {
        Ok(c) => match autopilot::send_cookies(&base, &c.li_at, &c.jsessionid).await {
            Ok(_) => "sent",
            Err(_) => "send_failed",
        },
        Err(_) => "no_cookies",
    };

    Ok(serde_json::json!({
        "running": true,
        "port": service.port(),
        "cookies": cookie_status,
    }))
}

/// Stop the autopilot service (graceful HTTP shutdown, then kill).
#[tauri::command]
pub async fn autopilot_stop(service: State<'_, AutopilotService>) -> Result<bool, String> {
    service.graceful_shutdown().await;
    Ok(true)
}

/// Get the service status (spawned + health + session).
#[tauri::command]
pub async fn autopilot_status(service: State<'_, AutopilotService>) -> Result<Value, String> {
    let base = service.base_url();
    let spawned = service.is_spawned();
    let healthy = if spawned {
        autopilot::health_check(&base).await
    } else {
        false
    };

    let mut session = serde_json::json!({ "has_session": false });
    if healthy {
        if let Ok(c) = client() {
            if let Ok(resp) = c.get(format!("{base}/autopilot/session")).send().await {
                if let Ok(json) = resp.json::<Value>().await {
                    session = json;
                }
            }
        }
    }

    Ok(serde_json::json!({
        "spawned": spawned,
        "healthy": healthy,
        "port": service.port(),
        "session": session,
    }))
}

/// Re-extract and forward LinkedIn cookies (e.g. after re-login).
#[tauri::command]
pub async fn autopilot_refresh_cookies(
    service: State<'_, AutopilotService>,
) -> Result<Value, String> {
    let base = service.base_url();
    let cookies = linkedin::get_linkedin_cookies()?;
    autopilot::send_cookies(&base, &cookies.li_at, &cookies.jsessionid).await?;
    Ok(serde_json::json!({
        "li_at_present": !cookies.li_at.is_empty(),
        "jsessionid_present": !cookies.jsessionid.is_empty(),
    }))
}

/// Generic proxy: GET a path on the autopilot service.
#[tauri::command]
pub async fn autopilot_get(
    service: State<'_, AutopilotService>,
    path: String,
) -> Result<Value, String> {
    validate_path(&path)?;
    let base = service.base_url();
    let c = client()?;
    let resp = c
        .get(format!("{base}{path}"))
        .send()
        .await
        .map_err(|e| format!("Autopilot request failed: {e}"))?;
    resp.json::<Value>()
        .await
        .map_err(|e| format!("Invalid JSON from autopilot: {e}"))
}

/// Generic proxy: send a JSON body with a given method to the autopilot service.
#[tauri::command]
pub async fn autopilot_send(
    service: State<'_, AutopilotService>,
    method: String,
    path: String,
    body: Option<Value>,
) -> Result<Value, String> {
    validate_path(&path)?;
    let base = service.base_url();
    let c = client()?;
    let url = format!("{base}{path}");

    let req = match method.to_uppercase().as_str() {
        "POST" => c.post(&url),
        "PUT" => c.put(&url),
        "PATCH" => c.patch(&url),
        "DELETE" => c.delete(&url),
        _ => return Err(format!("Unsupported method: {method}")),
    };

    let req = if let Some(b) = body { req.json(&b) } else { req };

    let resp = req
        .send()
        .await
        .map_err(|e| format!("Autopilot request failed: {e}"))?;
    resp.json::<Value>()
        .await
        .map_err(|e| format!("Invalid JSON from autopilot: {e}"))
}

#[cfg(test)]
mod tests {
    use super::validate_path;

    #[test]
    fn accepts_allowed_paths() {
        assert!(validate_path("/health").is_ok());
        assert!(validate_path("/autopilot/queue").is_ok());
        assert!(validate_path("/autopilot/settings/criteria").is_ok());
    }

    #[test]
    fn rejects_ssrf_and_unknown_paths() {
        assert!(validate_path("//evil.com/").is_err());
        assert!(validate_path("/autopilot/@evil.com").is_err());
        assert!(validate_path("http://evil.com").is_err());
        assert!(validate_path("/secrets").is_err());
        assert!(validate_path("autopilot/queue").is_err());
        assert!(validate_path("/autopilot\\x").is_err());
    }
}
