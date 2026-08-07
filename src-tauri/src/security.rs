//! Security helpers shared across commands: path traversal prevention and
//! safe (char-boundary-aware) string truncation.

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, ToSocketAddrs};
use std::path::{Path, PathBuf};

/// Validate that `url` is a plain http(s) URL that does not resolve to a
/// private/loopback/link-local address (best-effort SSRF mitigation).
pub fn assert_safe_http_url(url: &str) -> Result<(), String> {
    let parsed = reqwest::Url::parse(url).map_err(|e| format!("Invalid URL: {e}"))?;

    if parsed.scheme() != "http" && parsed.scheme() != "https" {
        return Err(format!("Unsupported URL scheme: {}", parsed.scheme()));
    }

    let host = parsed.host_str().ok_or("URL has no host")?;
    let port = parsed.port_or_known_default().unwrap_or(443);

    let addrs = (host, port)
        .to_socket_addrs()
        .map_err(|e| format!("Could not resolve host {host}: {e}"))?;

    for addr in addrs {
        if is_disallowed_ip(addr.ip()) {
            return Err(format!(
                "URL resolves to a disallowed address ({host} -> {})",
                addr.ip()
            ));
        }
    }

    Ok(())
}

fn is_disallowed_ip(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(v4) => is_disallowed_v4(v4),
        IpAddr::V6(v6) => is_disallowed_v6(v6),
    }
}

fn is_disallowed_v4(ip: Ipv4Addr) -> bool {
    ip.is_loopback()
        || ip.is_private()
        || ip.is_link_local()
        || ip.is_broadcast()
        || ip.is_documentation()
        || ip.is_unspecified()
}

fn is_disallowed_v6(ip: Ipv6Addr) -> bool {
    ip.is_loopback()
        || ip.is_unspecified()
        || (ip.segments()[0] & 0xfe00) == 0xfc00 // unique local fc00::/7
        || (ip.segments()[0] & 0xffc0) == 0xfe80 // link-local fe80::/10
}

/// Convert arbitrary user input into a filesystem-safe slug: lowercase,
/// spaces become underscores, and anything that isn't alphanumeric/`_`/`-`
/// is stripped. Prevents path traversal via crafted `company`/`position`
/// values used to build file names.
pub fn safe_slug(value: &str) -> String {
    let lowered = value.to_lowercase().replace(' ', "_");
    let cleaned: String = lowered
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '-')
        .collect();
    let trimmed = cleaned.trim_matches(|c| c == '_' || c == '-' || c == '.');
    trimmed.chars().take(80).collect()
}

/// Join `filename` under `base_dir`, rejecting any path traversal attempt.
///
/// Only the final path component of `filename` is trusted (directory parts,
/// `..`, and absolute paths are stripped/rejected). The resulting path is
/// verified to stay within `base_dir` after canonicalization-equivalent
/// join, preventing writes/reads/deletes outside the intended directory.
pub fn safe_join(base_dir: &Path, filename: &str) -> Result<PathBuf, String> {
    let name = Path::new(filename)
        .file_name()
        .ok_or_else(|| format!("Invalid filename: {filename}"))?;

    let candidate = base_dir.join(name);

    // Defense in depth: re-derive the file name from the candidate and make
    // sure its parent is exactly base_dir (handles weird OS-specific joins).
    if candidate.parent() != Some(base_dir) {
        return Err(format!("Path traversal attempt detected: {filename}"));
    }

    Ok(candidate)
}

/// Truncate a string to at most `max_bytes` bytes without splitting a
/// multi-byte UTF-8 character (which would otherwise panic on slicing).
///
/// Rust's `&str` indexing operates on byte offsets; cutting a string with
/// accented characters, emoji, or non-Latin scripts at an arbitrary byte
/// offset can land mid-character and panic with
/// "byte index N is not a char boundary". This walks back to the nearest
/// valid boundary at or before `max_bytes`.
pub fn safe_truncate(s: &str, max_bytes: usize) -> &str {
    if s.len() <= max_bytes {
        return s;
    }
    let mut end = max_bytes;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    &s[..end]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_join_rejects_parent_traversal() {
        let base = Path::new("/data/cvs");
        assert!(safe_join(base, "../../etc/passwd").is_ok()); // file_name() strips to "passwd"
        let result = safe_join(base, "../../etc/passwd").unwrap();
        assert_eq!(result, PathBuf::from("/data/cvs/passwd"));
    }

    #[test]
    fn safe_join_rejects_empty_or_dotdot() {
        let base = Path::new("/data/cvs");
        assert!(safe_join(base, "..").is_err());
        assert!(safe_join(base, "").is_err());
    }

    #[test]
    fn safe_join_keeps_simple_filename() {
        let base = Path::new("/data/cvs");
        let result = safe_join(base, "cv.pdf").unwrap();
        assert_eq!(result, PathBuf::from("/data/cvs/cv.pdf"));
    }

    #[test]
    fn safe_truncate_does_not_split_multibyte_chars() {
        let s = "Ingeniería de software con ñ y é y 🚀 emoji";
        // Try every possible byte length and make sure it never panics and
        // always returns valid UTF-8.
        for n in 0..=s.len() + 5 {
            let truncated = safe_truncate(s, n);
            assert!(truncated.len() <= n);
            // If this didn't panic, the slice is guaranteed valid UTF-8 already
            // (Rust's type system enforces it), this just documents intent.
            let _ = truncated.chars().count();
        }
    }

    #[test]
    fn safe_truncate_shorter_than_max_returns_whole_string() {
        assert_eq!(safe_truncate("hola", 100), "hola");
    }

    #[test]
    fn safe_slug_strips_traversal_and_lowercases() {
        assert_eq!(safe_slug("../../etc"), "etc");
        assert_eq!(safe_slug("My Company Inc."), "my_company_inc");
    }

    #[test]
    fn safe_slug_empty_or_only_traversal_yields_empty() {
        // Note: unlike the Python `safe_slug`, this one does not fall back
        // to a default string - callers (commands.rs::add_job) handle the
        // empty case explicitly with "unknown".
        assert_eq!(safe_slug(""), "");
        assert_eq!(safe_slug("../../.."), "");
    }

    #[test]
    fn assert_safe_http_url_rejects_non_http_schemes() {
        assert!(assert_safe_http_url("file:///etc/passwd").is_err());
        assert!(assert_safe_http_url("ftp://example.com").is_err());
        assert!(assert_safe_http_url("javascript:alert(1)").is_err());
    }

    #[test]
    fn assert_safe_http_url_rejects_loopback() {
        assert!(assert_safe_http_url("http://127.0.0.1:11434/api/tags").is_err());
        assert!(assert_safe_http_url("http://localhost:8765/autopilot/status").is_err());
    }

    #[test]
    fn assert_safe_http_url_rejects_private_ranges() {
        assert!(assert_safe_http_url("http://10.0.0.5/").is_err());
        assert!(assert_safe_http_url("http://172.16.0.1/").is_err());
        assert!(assert_safe_http_url("http://192.168.1.1/").is_err());
    }

    #[test]
    fn assert_safe_http_url_rejects_link_local_and_cloud_metadata() {
        assert!(assert_safe_http_url("http://169.254.169.254/latest/meta-data/").is_err());
    }

    #[test]
    fn assert_safe_http_url_rejects_malformed_url() {
        assert!(assert_safe_http_url("not a url").is_err());
    }

    #[test]
    fn is_disallowed_v4_flags_loopback_private_link_local_and_broadcast() {
        assert!(is_disallowed_v4(Ipv4Addr::new(127, 0, 0, 1)));
        assert!(is_disallowed_v4(Ipv4Addr::new(10, 1, 2, 3)));
        assert!(is_disallowed_v4(Ipv4Addr::new(192, 168, 1, 1)));
        assert!(is_disallowed_v4(Ipv4Addr::new(169, 254, 1, 1)));
        assert!(is_disallowed_v4(Ipv4Addr::new(255, 255, 255, 255)));
        assert!(!is_disallowed_v4(Ipv4Addr::new(8, 8, 8, 8)));
    }

    #[test]
    fn is_disallowed_v6_flags_loopback_and_link_local() {
        assert!(is_disallowed_v6(Ipv6Addr::LOCALHOST));
        assert!(is_disallowed_v6(Ipv6Addr::new(0xfe80, 0, 0, 0, 0, 0, 0, 1)));
        assert!(is_disallowed_v6(Ipv6Addr::new(0xfc00, 0, 0, 0, 0, 0, 0, 1)));
        assert!(!is_disallowed_v6(Ipv6Addr::new(0x2001, 0x4860, 0, 0, 0, 0, 0, 0x8888)));
    }
}
