use std::path::Path;
use unicode_normalization::UnicodeNormalization;

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
    Ok(clean_text(&normalize_unicode(&raw)))
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
                // Extract hyperlink text and URLs
                if let docx_rs::ParagraphChild::Hyperlink(hl) = c {
                    for rc in &hl.children {
                        if let docx_rs::ParagraphChild::Run(run) = rc {
                            for tc in &run.children {
                                if let docx_rs::RunChild::Text(t) = tc {
                                    para_text.push_str(&t.text);
                                }
                            }
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
    Ok(clean_text(&normalize_unicode(&text)))
}

/// Normalize Unicode: NFC normalization + fix common pdf-extract issues
/// pdf-extract often outputs decomposed characters like:
///   ´i -> í,  ˜n -> ñ,  ´o -> ó, etc.
fn normalize_unicode(text: &str) -> String {
    // First: apply NFC normalization (composes decomposed chars)
    let normalized: String = text.nfc().collect();

    // Second: fix remaining broken patterns that pdf-extract produces
    // where combining characters appear BEFORE the base letter
    let fixed = normalized
        // Combining acute accent (U+0301) patterns - sometimes pdf-extract puts them wrong
        .replace("\u{00B4}a", "á")  // ´a -> á
        .replace("\u{00B4}e", "é")  // ´e -> é
        .replace("\u{00B4}i", "í")  // ´i -> í
        .replace("\u{00B4}o", "ó")  // ´o -> ó
        .replace("\u{00B4}u", "ú")  // ´u -> ú
        .replace("\u{00B4}A", "Á")
        .replace("\u{00B4}E", "É")
        .replace("\u{00B4}I", "Í")
        .replace("\u{00B4}O", "Ó")
        .replace("\u{00B4}U", "Ú")
        // Tilde patterns
        .replace("\u{02DC}n", "ñ")  // ˜n -> ñ
        .replace("\u{02DC}N", "Ñ")  // ˜N -> Ñ
        .replace("\u{007E}n", "ñ")  // ~n -> ñ
        .replace("\u{007E}N", "Ñ")
        .replace("\u{02DC}a", "ã")
        .replace("\u{02DC}o", "õ")
        // Grave accent
        .replace("\u{0060}a", "à")
        .replace("\u{0060}e", "è")
        .replace("\u{0060}u", "ù")
        // Circumflex
        .replace("\u{02C6}a", "â")
        .replace("\u{02C6}e", "ê")
        .replace("\u{02C6}o", "ô")
        // Diaeresis
        .replace("\u{00A8}u", "ü")
        .replace("\u{00A8}a", "ä")
        .replace("\u{00A8}o", "ö")
        // Cedilla
        .replace("\u{00B8}c", "ç")
        .replace("\u{00B8}C", "Ç")
        // Clean up any remaining standalone combining marks
        .replace('\u{00B4}', "'")   // lone acute -> apostrophe
        .replace('\u{02DC}', "")    // lone tilde modifier -> remove
        .replace('\u{0060}', "'");  // lone grave -> apostrophe

    fixed
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
