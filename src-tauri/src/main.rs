#![windows_subsystem = "windows"]

mod autopilot;
mod autopilot_bridge;
mod commands;
mod document;
mod linkedin;
mod llm;
mod ollama;
mod scraper;
mod state;

use autopilot::AutopilotService;
use state::AppState;

fn main() {
    let app_state = AppState::new();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .manage(app_state)
        .manage(AutopilotService::default())
        .invoke_handler(tauri::generate_handler![
            // Setup & Health
            commands::setup,
            commands::health,
            // Profile
            commands::get_profile,
            commands::save_profile,
            commands::reset_profile,
            // CVs
            commands::list_cvs,
            commands::upload_cv,
            commands::get_cv_content,
            commands::delete_cv,
            commands::extract_profile_from_cv,
            commands::extract_profile_from_linkedin,
            commands::extract_profile_from_linkedin_url,
            // Jobs
            commands::list_jobs,
            commands::add_job,
            commands::delete_job,
            commands::scrape_job_url_cmd,
            // Generation
            commands::generate_cover_letter,
            commands::generate_recruiter_message,
            commands::generate_interview_answer,
            commands::generate_interview_questions,
            // Autopilot
            autopilot_bridge::autopilot_start,
            autopilot_bridge::autopilot_stop,
            autopilot_bridge::autopilot_status,
            autopilot_bridge::autopilot_refresh_cookies,
            autopilot_bridge::autopilot_get,
            autopilot_bridge::autopilot_send,
        ])
        .build(tauri::generate_context!())
        .expect("error while building JobPilot")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                // Ensure the Python autopilot child process is terminated.
                use tauri::Manager;
                let service = app_handle.state::<AutopilotService>();
                service.stop();
            }
        });
}
