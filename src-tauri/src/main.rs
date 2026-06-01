#![windows_subsystem = "windows"]

mod commands;
mod document;
mod llm;
mod ollama;
mod scraper;
mod state;

use state::AppState;

fn main() {
    let app_state = AppState::new();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .manage(app_state)
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
        ])
        .run(tauri::generate_context!())
        .expect("error while running JobPilot");
}
