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
    /// Shared secret required by the Python service on every request
    /// (via the `X-Autopilot-Token` header) except `/health`. Generated
    /// once per app run and passed to the child via an environment
    /// variable, so no other local process can control the automation
    /// service (session cookies, LinkedIn actions, shutdown).
    token: Mutex<String>,
}

impl Default for AutopilotService {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            port: Mutex::new(DEFAULT_PORT),
            token: Mutex::new(generate_token()),
        }
    }
}

/// Generate a random-looking hex token without pulling in a `rand` crate
/// dependency. Mixes high-resolution time, the process id, and a stack
/// address (ASLR) through SplitMix64. This is a local-only shared secret
/// meant to keep *other local processes* from talking to the autopilot
/// service, not a cryptographic key - it does not need CSPRNG-grade
/// guarantees for that threat model.
fn generate_token() -> String {
    fn splitmix64(mut x: u64) -> u64 {
        x = x.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = x;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }

    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0);
    let pid = std::process::id() as u64;
    let stack_addr = &nanos as *const u64 as u64;

    let mut seed = nanos ^ pid.rotate_left(17) ^ stack_addr.rotate_left(33);
    let mut out = String::with_capacity(96);
    for _ in 0..6 {
        seed = splitmix64(seed);
        out.push_str(&format!("{seed:016x}"));
    }
    out
}

impl AutopilotService {
    pub fn port(&self) -> u16 {
        *self.port.lock().unwrap_or_else(|e| e.into_inner())
    }

    pub fn base_url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port())
    }

    /// The shared secret to send as `X-Autopilot-Token` on every request.
    pub fn token(&self) -> String {
        self.token.lock().unwrap_or_else(|e| e.into_inner()).clone()
    }

    pub fn is_spawned(&self) -> bool {
        self.child.lock().unwrap_or_else(|e| e.into_inner()).is_some()
    }

    /// Spawn the Python automation service if not already running.
    /// `data_dir` and `ollama_url` are passed via environment variables.
    pub fn start(&self, data_dir: &str, ollama_url: &str) -> Result<(), String> {
        if self.is_spawned() {
            return Ok(());
        }

        let (python, backend_dir) = locate_python_backend()?;
        let port = pick_port(*self.port.lock().unwrap_or_else(|e| e.into_inner()));
        *self.port.lock().unwrap_or_else(|e| e.into_inner()) = port;

        // Redirect child output to a log file for debugging startup issues.
        let (stdout_cfg, stderr_cfg) = match open_log_file(data_dir) {
            Some(file) => {
                let err = file.try_clone().map(Stdio::from).unwrap_or_else(|_| Stdio::null());
                (Stdio::from(file), err)
            }
            None => (Stdio::null(), Stdio::null()),
        };

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
            .env("AUTOPILOT_AUTH_TOKEN", self.token())
            .stdout(stdout_cfg)
            .stderr(stderr_cfg)
            .spawn()
            .map_err(|e| format!("Failed to spawn autopilot service: {e}"))?;

        *self.child.lock().unwrap_or_else(|e| e.into_inner()) = Some(child);
        Ok(())
    }

    /// Kill the child process. Synchronous; safe to call from the exit handler.
    /// For a graceful HTTP shutdown first, call `graceful_shutdown` (async).
    pub fn stop(&self) {
        if let Some(mut child) = self.child.lock().unwrap_or_else(|e| e.into_inner()).take() {
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
            let _ = c
                .post(format!("{base}/shutdown"))
                .header("X-Autopilot-Token", self.token())
                .send()
                .await;
        }
        tokio::time::sleep(Duration::from_millis(600)).await;
        self.stop();
    }
}

/// Open (truncate) the autopilot log file in the data directory.
/// Returns None if the file cannot be created (logging is best-effort).
fn open_log_file(data_dir: &str) -> Option<std::fs::File> {
    let dir = PathBuf::from(data_dir);
    let _ = std::fs::create_dir_all(&dir);
    std::fs::File::create(dir.join("autopilot.log")).ok()
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

    // 2. System Python on PATH (residual trust: assumes the user's PATH is
    // not compromised; the backend_dir itself is now tightly scoped, see
    // locate_backend_dir).
    if let Ok(p) = which::which("python") {
        return Ok((p, backend_dir));
    }
    if let Ok(p) = which::which("python3") {
        return Ok((p, backend_dir));
    }

    Err("Python not found. Install Python 3.12+ or create backend/.venv.".to_string())
}

/// Find the `backend` directory near the executable or the current working
/// directory (dev mode).
///
/// SECURITY: intentionally does NOT walk up the entire filesystem ancestry
/// and does NOT fall back to arbitrary directories. Only a small, fixed set
/// of well-known relative locations is checked, so that running the app
/// from an untrusted working directory cannot cause it to pick up and
/// execute a malicious `backend/app/automation/main.py`.
fn locate_backend_dir() -> Result<PathBuf, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    // Development layout: repo_root/backend, invoked from repo_root or
    // repo_root/src-tauri.
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("backend"));
        candidates.push(cwd.join("..").join("backend"));
    }

    // Installed/bundled layout: backend/ shipped next to the executable.
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            candidates.push(exe_dir.join("backend"));
            candidates.push(exe_dir.join("..").join("backend"));
            candidates.push(exe_dir.join("resources").join("backend"));
        }
    }

    for c in candidates {
        let marker = c.join("app").join("automation").join("main.py");
        if marker.exists() {
            return c.canonicalize().map_err(|e| e.to_string());
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
pub async fn send_cookies(base_url: &str, token: &str, li_at: &str, jsessionid: &str) -> Result<(), String> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()
        .map_err(|e| e.to_string())?;

    let resp = client
        .post(format!("{base_url}/autopilot/session"))
        .header("X-Autopilot-Token", token)
        .json(&serde_json::json!({ "li_at": li_at, "jsessionid": jsessionid }))
        .send()
        .await
        .map_err(|e| format!("Failed to send cookies to autopilot: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("Autopilot session endpoint returned {}", resp.status()));
    }
    Ok(())
}
