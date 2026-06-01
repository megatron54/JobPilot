use reqwest::Client;
use scraper::{Html, Selector};
use std::time::Duration;

/// Scrape a job posting URL and return the raw text content
pub async fn scrape_job_url(url: &str) -> Result<ScrapedJob, String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .redirect(reqwest::redirect::Policy::limited(5))
        .build()
        .map_err(|e| format!("HTTP client error: {e}"))?;

    let resp = client
        .get(url)
        .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        .header("Accept-Language", "es-ES,es;q=0.9,en;q=0.8")
        .send()
        .await
        .map_err(|e| format!("Failed to fetch URL: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("HTTP error: {}", resp.status()));
    }

    let html = resp.text().await.map_err(|e| format!("Failed to read response: {e}"))?;
    let document = Html::parse_document(&html);

    // Detect source from URL
    let source = detect_source(url);

    // Extract content based on source
    let (title, company, description) = match source.as_str() {
        "linkedin" => parse_linkedin(&document),
        "infojobs" => parse_infojobs(&document),
        "indeed" => parse_indeed(&document),
        _ => parse_generic(&document),
    };

    let raw_text = format!("{}\n{}\n\n{}", title, company, description);

    Ok(ScrapedJob {
        raw_text: clean_text(&raw_text),
        title,
        company,
        source,
        url: url.to_string(),
    })
}

pub struct ScrapedJob {
    pub raw_text: String,
    pub title: String,
    pub company: String,
    pub source: String,
    pub url: String,
}

fn detect_source(url: &str) -> String {
    let lower = url.to_lowercase();
    if lower.contains("linkedin.com") {
        "linkedin".to_string()
    } else if lower.contains("infojobs") {
        "infojobs".to_string()
    } else if lower.contains("indeed") {
        "indeed".to_string()
    } else {
        "web".to_string()
    }
}

fn parse_linkedin(doc: &Html) -> (String, String, String) {
    let title = extract_first(doc, "h1")
        .or_else(|| extract_first(doc, "h2"))
        .unwrap_or_default();

    let company = extract_by_class(doc, "a", "company")
        .unwrap_or_default();

    let description = extract_by_class(doc, "div", "description")
        .or_else(|| extract_by_class(doc, "div", "show-more-less-html"))
        .or_else(|| extract_by_class(doc, "section", "description"))
        .or_else(|| extract_first(doc, "main"))
        .unwrap_or_default();

    (title, company, description)
}

fn parse_infojobs(doc: &Html) -> (String, String, String) {
    let title = extract_first(doc, "h1").unwrap_or_default();
    let company = extract_by_class(doc, "a", "company-name")
        .or_else(|| extract_by_class(doc, "span", "empresa"))
        .unwrap_or_default();
    let description = extract_first(doc, "article")
        .or_else(|| extract_first(doc, "main"))
        .unwrap_or_default();

    (title, company, description)
}

fn parse_indeed(doc: &Html) -> (String, String, String) {
    let title = extract_by_class(doc, "h1", "jobTitle")
        .or_else(|| extract_first(doc, "h1"))
        .unwrap_or_default();
    let company = extract_by_class(doc, "div", "companyName")
        .or_else(|| extract_by_class(doc, "span", "company"))
        .unwrap_or_default();
    let description = extract_by_id(doc, "jobDescriptionText")
        .or_else(|| extract_by_class(doc, "div", "jobDescription"))
        .unwrap_or_default();

    (title, company, description)
}

fn parse_generic(doc: &Html) -> (String, String, String) {
    let title = extract_first(doc, "h1").unwrap_or_default();
    let company = String::new();
    let description = extract_first(doc, "main")
        .or_else(|| extract_first(doc, "article"))
        .or_else(|| extract_first(doc, "body"))
        .unwrap_or_default();

    (title, company, description)
}

// ─── Helper functions ──────────────────────────────────────────────────────────

fn extract_first(doc: &Html, tag: &str) -> Option<String> {
    let selector = Selector::parse(tag).ok()?;
    doc.select(&selector)
        .next()
        .map(|el| el.text().collect::<Vec<_>>().join(" "))
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
}

fn extract_by_class(doc: &Html, tag: &str, class_fragment: &str) -> Option<String> {
    let selector = Selector::parse(tag).ok()?;
    for el in doc.select(&selector) {
        if let Some(class_attr) = el.value().attr("class") {
            if class_attr.to_lowercase().contains(&class_fragment.to_lowercase()) {
                let text = el.text().collect::<Vec<_>>().join(" ");
                let trimmed = text.trim().to_string();
                if !trimmed.is_empty() {
                    return Some(trimmed);
                }
            }
        }
    }
    None
}

fn extract_by_id(doc: &Html, id: &str) -> Option<String> {
    let selector_str = format!("#{id}");
    let selector = Selector::parse(&selector_str).ok()?;
    doc.select(&selector)
        .next()
        .map(|el| el.text().collect::<Vec<_>>().join(" "))
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
}

fn clean_text(text: &str) -> String {
    let mut result = String::new();
    let mut prev_empty = false;

    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            if !prev_empty {
                result.push('\n');
                prev_empty = true;
            }
        } else {
            result.push_str(trimmed);
            result.push('\n');
            prev_empty = false;
        }
    }
    result.trim().to_string()
}
