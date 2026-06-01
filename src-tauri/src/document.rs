use std::path::Path;

/// Supported file extensions
pub const SUPPORTED_EXTENSIONS: &[&str] = &["pdf", "docx", "txt", "md"];

/// Extract text from any supported file
pub fn extract_text(path: &Path) -> Result<String, String> {
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    match ext.as_str() {
        "pdf" => extract_pdf(path),
        "docx" => extract_docx(path),
        "txt" | "md" => {
            let content = std::fs::read_to_string(path)
                .map_err(|e| format!("Failed to read text file: {e}"))?;
            Ok(clean_text(&content))
        }
        _ => Err(format!("Unsupported file type: .{ext}")),
    }
}

/// Extract text from a PDF file
fn extract_pdf(path: &Path) -> Result<String, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("Failed to read file: {e}"))?;
    let raw = pdf_extract::extract_text_from_mem(&bytes)
        .map_err(|e| format!("PDF extraction failed: {e}"))?;
    Ok(clean_text(&raw))
}

/// Extract text from a DOCX file
fn extract_docx(path: &Path) -> Result<String, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("Failed to read file: {e}"))?;
    let doc = docx_rs::read_docx(&bytes).map_err(|e| format!("DOCX parse failed: {e}"))?;

    let mut text = String::new();
    for child in doc.document.children {
        if let docx_rs::DocumentChild::Paragraph(p) = child {
            let mut para_text = String::new();
            for c in &p.children {
                if let docx_rs::ParagraphChild::Run(run) = c {
                    for rc in &run.children {
                        if let docx_rs::RunChild::Text(t) = rc {
                            para_text.push_str(&t.text);
                        }
                    }
                }
            }
            if !para_text.trim().is_empty() {
                text.push_str(para_text.trim());
                text.push('\n');
            }
        }
    }
    Ok(clean_text(&text))
}

/// Clean extracted text: normalize whitespace
fn clean_text(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
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

    result
}
