use futures_util::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};

#[derive(Serialize)]
struct ChatRequest {
    model: String,
    messages: Vec<ChatMessage>,
    stream: bool,
    options: ChatOptions,
}

#[derive(Serialize)]
struct ChatOptions {
    temperature: f64,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Deserialize)]
struct ChatChunk {
    message: Option<ChatChunkMessage>,
    done: Option<bool>,
}

#[derive(Deserialize)]
struct ChatChunkMessage {
    content: String,
}

/// Stream a chat completion from Ollama, emitting tokens via Tauri events
pub async fn stream_chat(
    app: &AppHandle,
    client: &Client,
    base_url: &str,
    model: &str,
    messages: Vec<ChatMessage>,
    temperature: f64,
    event_name: &str,
) -> Result<String, String> {
    let url = format!("{base_url}/api/chat");
    let body = ChatRequest {
        model: model.to_string(),
        messages,
        stream: true,
        options: ChatOptions { temperature },
    };

    let resp = client
        .post(&url)
        .json(&body)
        .send()
        .await
        .map_err(|e| format!("Chat request failed: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(format!("Ollama API error {status}: {text}"));
    }

    let mut stream = resp.bytes_stream();
    let mut buffer = String::new();
    let mut full_response = String::new();

    while let Some(chunk) = stream.next().await {
        let bytes = chunk.map_err(|e| format!("Stream error: {e}"))?;
        buffer.push_str(&String::from_utf8_lossy(&bytes));

        // Process complete JSON lines
        while let Some(newline_pos) = buffer.find('\n') {
            let line = buffer[..newline_pos].trim().to_string();
            buffer = buffer[newline_pos + 1..].to_string();

            if line.is_empty() {
                continue;
            }

            if let Ok(chunk) = serde_json::from_str::<ChatChunk>(&line) {
                if let Some(msg) = chunk.message {
                    if !msg.content.is_empty() {
                        full_response.push_str(&msg.content);
                        let _ = app.emit(event_name, &msg.content);
                    }
                }
                if chunk.done == Some(true) {
                    let done_event = format!("{}-done", event_name);
                    let _ = app.emit(&done_event, ());
                    return Ok(full_response);
                }
            }
        }
    }

    let done_event = format!("{}-done", event_name);
    let _ = app.emit(&done_event, ());
    Ok(full_response)
}

/// Non-streaming chat completion
pub async fn chat_completion(
    client: &Client,
    base_url: &str,
    model: &str,
    messages: Vec<ChatMessage>,
    temperature: f64,
) -> Result<String, String> {
    let url = format!("{base_url}/api/chat");

    #[derive(Serialize)]
    struct Req {
        model: String,
        messages: Vec<ChatMessage>,
        stream: bool,
        options: ChatOptions,
    }

    let body = Req {
        model: model.to_string(),
        messages,
        stream: false,
        options: ChatOptions { temperature },
    };

    let resp = client
        .post(&url)
        .json(&body)
        .timeout(std::time::Duration::from_secs(180))
        .send()
        .await
        .map_err(|e| format!("Chat request failed: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let text = resp.text().await.unwrap_or_default();
        return Err(format!("Ollama API error {status}: {text}"));
    }

    #[derive(Deserialize)]
    struct ChatResp {
        message: ChatRespMessage,
    }
    #[derive(Deserialize)]
    struct ChatRespMessage {
        content: String,
    }

    let data: ChatResp = resp
        .json()
        .await
        .map_err(|e| format!("Failed to parse response: {e}"))?;

    Ok(data.message.content)
}
