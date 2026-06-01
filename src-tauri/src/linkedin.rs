//! LinkedIn profile fetching using browser cookies (Chrome/Edge on Windows).
//!
//! Extracts the `li_at` session cookie from Chrome or Edge's cookie database,
//! then uses it to fetch LinkedIn profile pages as an authenticated user.

use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use base64::Engine;
use std::path::PathBuf;

/// Get the LinkedIn `li_at` session cookie from Chrome or Edge.
/// Tries Edge first (more common on Windows), then Chrome.
pub fn get_linkedin_cookie() -> Result<String, String> {
    // Try Edge first, then Chrome
    if let Ok(cookie) = get_cookie_from_browser(Browser::Edge) {
        return Ok(cookie);
    }
    if let Ok(cookie) = get_cookie_from_browser(Browser::Chrome) {
        return Ok(cookie);
    }
    Err("Could not find LinkedIn session cookie. Make sure you are logged into LinkedIn in Chrome or Edge.".to_string())
}

enum Browser {
    Chrome,
    Edge,
}

fn get_browser_paths(browser: &Browser) -> (PathBuf, PathBuf) {
    let local_app_data = std::env::var("LOCALAPPDATA").unwrap_or_default();
    match browser {
        Browser::Edge => {
            let base = PathBuf::from(&local_app_data).join("Microsoft").join("Edge").join("User Data");
            let local_state = base.join("Local State");
            let cookies = base.join("Default").join("Network").join("Cookies");
            (local_state, cookies)
        }
        Browser::Chrome => {
            let base = PathBuf::from(&local_app_data).join("Google").join("Chrome").join("User Data");
            let local_state = base.join("Local State");
            let cookies = base.join("Default").join("Network").join("Cookies");
            (local_state, cookies)
        }
    }
}

fn get_cookie_from_browser(browser: Browser) -> Result<String, String> {
    let (local_state_path, cookies_path) = get_browser_paths(&browser);

    if !local_state_path.exists() {
        return Err("Local State not found".to_string());
    }
    if !cookies_path.exists() {
        return Err("Cookies database not found".to_string());
    }

    // Read and decrypt the master key from Local State
    let master_key = get_master_key(&local_state_path)?;

    // Copy cookies DB to temp (browser may lock it)
    let temp_dir = std::env::temp_dir();
    let temp_cookies = temp_dir.join("jobpilot_cookies_tmp");
    std::fs::copy(&cookies_path, &temp_cookies)
        .map_err(|e| format!("Failed to copy cookies DB (browser may be locking it): {e}"))?;

    // Query for li_at cookie
    let result = query_linkedin_cookie(&temp_cookies, &master_key);

    // Clean up temp file
    let _ = std::fs::remove_file(&temp_cookies);

    result
}

fn get_master_key(local_state_path: &PathBuf) -> Result<Vec<u8>, String> {
    let data = std::fs::read_to_string(local_state_path)
        .map_err(|e| format!("Failed to read Local State: {e}"))?;

    let json: serde_json::Value = serde_json::from_str(&data)
        .map_err(|e| format!("Failed to parse Local State: {e}"))?;

    let encrypted_key_b64 = json["os_crypt"]["encrypted_key"]
        .as_str()
        .ok_or("No encrypted_key found in Local State")?;

    let encrypted_key = base64::engine::general_purpose::STANDARD
        .decode(encrypted_key_b64)
        .map_err(|e| format!("Failed to decode key: {e}"))?;

    // Remove "DPAPI" prefix (5 bytes)
    if encrypted_key.len() < 5 || &encrypted_key[..5] != b"DPAPI" {
        return Err("Invalid encrypted key format".to_string());
    }

    let key_bytes = &encrypted_key[5..];

    // Decrypt with Windows DPAPI
    decrypt_dpapi(key_bytes)
}

#[cfg(target_os = "windows")]
fn decrypt_dpapi(data: &[u8]) -> Result<Vec<u8>, String> {
    use winapi::um::dpapi::CryptUnprotectData;
    use winapi::um::wincrypt::CRYPTOAPI_BLOB;
    use std::ptr;

    unsafe {
        let mut input_blob = CRYPTOAPI_BLOB {
            cbData: data.len() as u32,
            pbData: data.as_ptr() as *mut u8,
        };
        let mut output_blob = CRYPTOAPI_BLOB {
            cbData: 0,
            pbData: ptr::null_mut(),
        };

        let result = CryptUnprotectData(
            &mut input_blob,
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            ptr::null_mut(),
            0,
            &mut output_blob,
        );

        if result == 0 {
            return Err("DPAPI decryption failed".to_string());
        }

        let decrypted = std::slice::from_raw_parts(output_blob.pbData, output_blob.cbData as usize).to_vec();

        // Free the allocated memory
        winapi::um::winbase::LocalFree(output_blob.pbData as *mut _);

        Ok(decrypted)
    }
}

#[cfg(not(target_os = "windows"))]
fn decrypt_dpapi(_data: &[u8]) -> Result<Vec<u8>, String> {
    Err("DPAPI is only available on Windows".to_string())
}

fn query_linkedin_cookie(db_path: &PathBuf, master_key: &[u8]) -> Result<String, String> {
    let conn = rusqlite::Connection::open_with_flags(
        db_path,
        rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY,
    )
    .map_err(|e| format!("Failed to open cookies DB: {e}"))?;

    let mut stmt = conn
        .prepare(
            "SELECT encrypted_value FROM cookies WHERE host_key LIKE '%linkedin.com' AND name = 'li_at' LIMIT 1",
        )
        .map_err(|e| format!("Failed to prepare query: {e}"))?;

    let encrypted_value: Vec<u8> = stmt
        .query_row([], |row| row.get(0))
        .map_err(|_| "LinkedIn session cookie (li_at) not found. Please log into LinkedIn in your browser first.".to_string())?;

    // Decrypt the cookie value
    decrypt_cookie_value(&encrypted_value, master_key)
}

fn decrypt_cookie_value(encrypted: &[u8], master_key: &[u8]) -> Result<String, String> {
    // Chrome v80+ format: "v10" or "v20" prefix (3 bytes) + 12-byte nonce + ciphertext + 16-byte tag
    if encrypted.len() < 3 + 12 + 16 {
        return Err("Cookie value too short to decrypt".to_string());
    }

    let prefix = &encrypted[..3];
    if prefix != b"v10" && prefix != b"v20" {
        // Try DPAPI directly (older Chrome versions)
        return decrypt_dpapi(encrypted).and_then(|v| {
            String::from_utf8(v).map_err(|e| format!("Cookie is not valid UTF-8: {e}"))
        });
    }

    let nonce_bytes = &encrypted[3..15];
    let ciphertext = &encrypted[15..];

    let cipher = Aes256Gcm::new_from_slice(master_key)
        .map_err(|e| format!("Failed to create cipher: {e}"))?;

    let nonce = Nonce::from_slice(nonce_bytes);

    let decrypted = cipher
        .decrypt(nonce, ciphertext)
        .map_err(|_| "Failed to decrypt cookie. The browser encryption key may have changed. Try closing and reopening your browser.".to_string())?;

    String::from_utf8(decrypted).map_err(|e| format!("Cookie is not valid UTF-8: {e}"))
}

/// Fetch a LinkedIn profile page using the li_at cookie.
/// Returns the HTML content.
pub async fn fetch_linkedin_profile(url: &str, li_at: &str) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::limited(5))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {e}"))?;

    let resp = client
        .get(url)
        .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        .header("Accept-Language", "es-ES,es;q=0.9,en;q=0.8")
        .header("Cookie", format!("li_at={li_at}"))
        .send()
        .await
        .map_err(|e| format!("Failed to fetch LinkedIn profile: {e}"))?;

    let status = resp.status();
    if status == reqwest::StatusCode::UNAUTHORIZED || status == reqwest::StatusCode::FORBIDDEN {
        return Err("LinkedIn session expired. Please log into LinkedIn in your browser again.".to_string());
    }
    if !status.is_success() {
        return Err(format!("LinkedIn returned status {status}. The profile may not exist or may be private."));
    }

    resp.text()
        .await
        .map_err(|e| format!("Failed to read LinkedIn response: {e}"))
}

/// Extract clean text from LinkedIn HTML (remove scripts, styles, etc.)
pub fn extract_text_from_html(html: &str) -> String {
    let document = scraper::Html::parse_document(html);

    // Try to get the main profile content
    let selectors_to_try = [
        "main",
        "section.artdeco-card",
        ".pv-top-card",
        "body",
    ];

    let mut text = String::new();

    for sel_str in &selectors_to_try {
        if let Ok(selector) = scraper::Selector::parse(sel_str) {
            let elements: Vec<_> = document.select(&selector).collect();
            if !elements.is_empty() {
                text = elements
                    .iter()
                    .flat_map(|el| el.text())
                    .collect::<Vec<_>>()
                    .join(" ");
                if text.len() > 200 {
                    break;
                }
            }
        }
    }

    if text.is_empty() {
        // Fallback: get all body text
        if let Ok(selector) = scraper::Selector::parse("body") {
            text = document
                .select(&selector)
                .flat_map(|el| el.text())
                .collect::<Vec<_>>()
                .join(" ");
        }
    }

    // Clean up whitespace
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}
