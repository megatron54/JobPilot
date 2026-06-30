//! Autopilot service lifecycle management.
//!
//! Spawns the Python automation service (FastAPI/uvicorn) as a child process,
//! polls its health endpoint, forwards LinkedIn cookies, and proxies control
//! requests. The child handle is retained so the service is terminated when the
//! Tauri app exits.
//!
//! Communication is plain HTTP on `127.0.0.1:<port>` (same pattern the app uses
//! for Ollama). See docs/AUTOPILOT_PLAN.md sections 4 and 12.

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

/// Default port for the autopilot service.
pub const DEFAULT_PORT: u16 = 8765;

/// Holds the running Python child process and its port.
pub struct AutopilotService {
    child: Mutex<Option<Child>>,
    port: Mutex<u16>,
}

impl Default for AutopilotService {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            port: Mutex::new(DEFAULT_PORT),
        }
    }
}

impl AutopilotService {
    pub fn port(&self) -> u16 {
        *self.port.lock().unwrap()
    }

    pub fn base_url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port())
    }

    pub fn is_spawned(&self) -> bool {
        self.child.lock().unwrap().is_some()
    }

    /// Spawn the Python automation service if not already running.
    /// `data_dir` and `ollama_url` are passed via environment variables.
    pub fn start(&self, data_dir: &str, ollama_url: &str) -> Result<(), String> {
        if self.is_spawned() {
            return Ok(());
        }

        let (python, backend_dir) = locate_python_backend()?;
        let port = pick_port(*self.port.lock().unwrap());
        *self.port.lock().unwrap() = port;

        let child = Command::new(&python)
            .args([
                "-m",
                "uvicorn",
                "app.automation.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                &port.to_string(),
            ])
            .current_dir(&backend_dir)
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("AUTOPILOT_DATA_DIR", data_dir)
            .env("AUTOPILOT_PORT", port.to_string())
            .env("AUTOPILOT_LLM_BASE_URL", ollama_url)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("Failed to spawn autopilot service: {e}"))?;

        *self.child.lock().unwrap() = Some(child);
        Ok(())
    }

    /// Kill the child process. Synchronous; safe to call from the exit handler.
    /// For a graceful HTTP shutdown first, call `graceful_shutdown` (async).
    pub fn stop(&self) {
        if let Some(mut child) = self.child.lock().unwrap().take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }

    /// Ask the service to shut down via HTTP, then kill the process.
    /// Async-safe (uses the async reqwest client).
    pub async fn graceful_shutdown(&self) {
        let base = self.base_url();
        if let Ok(c) = reqwest::Client::builder()
            .timeout(Duration::from_secs(2))
            .build()
        {
            let _ = c.post(format!("{base}/shutdown")).send().await;
        }
        tokio::time::sleep(Duration::from_millis(600)).await;
        self.stop();
    }
}

/// Locate the Python interpreter and the backend directory.
/// Prefers a project-local venv; falls back to system Python.
fn locate_python_backend() -> Result<(PathBuf, PathBuf), String> {
    let backend_dir = locate_backend_dir()?;

    // 1. Project-local venv
    let venv_python = backend_dir.join(".venv").join("Scripts").join("python.exe");
    if venv_python.exists() {
        return Ok((venv_python, backend_dir));
    }

    // 2. System Python on PATH
    if let Ok(p) = which::which("python") {
        return Ok((p, backend_dir));
    }
    if let Ok(p) = which::which("python3") {
        return Ok((p, backend_dir));
    }

    Err("Python not found. Install Python 3.12+ or create backend/.venv.".to_string())
}

/// Find the `backend` directory by walking up from known base locations.
fn locate_backend_dir() -> Result<PathBuf, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    // Current working directory and ancestors.
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("backend"));
        let mut dir = cwd.clone();
        while let Some(parent) = dir.parent() {
            candidates.push(parent.join("backend"));
            dir = parent.to_path_buf();
        }
    }

    // Executable directory and ancestors (for bundled/dev builds).
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().map(|p| p.to_path_buf());
        while let Some(d) = dir {
            candidates.push(d.join("backend"));
            dir = d.parent().map(|p| p.to_path_buf());
        }
    }

    for c in candidates {
        if c.join("app").join("automation").join("main.py").exists() {
            return Ok(c);
        }
    }

    Err("Could not locate the backend directory (app/automation/main.py).".to_string())
}

/// Return `preferred` if free, otherwise scan a small range, else preferred.
fn pick_port(preferred: u16) -> u16 {
    use std::net::TcpListener;
    if TcpListener::bind(("127.0.0.1", preferred)).is_ok() {
        return preferred;
    }
    for port in (preferred + 1)..(preferred + 50) {
        if TcpListener::bind(("127.0.0.1", port)).is_ok() {
            return port;
        }
    }
    preferred
}

/// Poll the health endpoint until ready or timeout (seconds).
pub async fn wait_until_ready(base_url: &str, timeout_secs: u64) -> Result<(), String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(1))
        .build()
        .map_err(|e| e.to_string())?;

    let deadline = std::time::Instant::now() + Duration::from_secs(timeout_secs);
    loop {
        if std::time::Instant::now() >= deadline {
            return Err(format!(
                "Autopilot service did not become ready within {timeout_secs}s"
            ));
        }
        if let Ok(resp) = client.get(format!("{base_url}/health")).send().await {
            if resp.status().is_success() {
                return Ok(());
            }
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
}

/// Check if the service is currently healthy.
pub async fn health_check(base_url: &str) -> bool {
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };
    client
        .get(format!("{base_url}/health"))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

/// Forward LinkedIn cookies to the autopilot service.
pub async fn send_cookies(base_url: &str, li_at: &str, jsessionid: &str) -> Result<(), String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()
        .map_err(|e| e.to_string())?;

    let resp = client
        .post(format!("{base_url}/autopilot/session"))
        .json(&serde_json::json!({ "li_at": li_at, "jsessionid": jsessionid }))
        .send()
        .await
        .map_err(|e| format!("Failed to send cookies to autopilot: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("Autopilot session endpoint returned {}", resp.status()));
    }
    Ok(())
}
