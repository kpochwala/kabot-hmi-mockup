use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;
use tauri::Manager;

struct BackendPort(u16);

#[tauri::command]
fn get_backend_port(port: tauri::State<'_, BackendPort>) -> u16 {
    port.0
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Find an open port
            let port = std::net::TcpListener::bind("127.0.0.1:0")
                .map(|listener| listener.local_addr().unwrap().port())
                .unwrap_or(8000);
            
            app.manage(BackendPort(port));

            // Launch sidecar
            let sidecar_command = app.shell().sidecar("kabot_backend")
                .expect("failed to create `kabot_backend` binary command")
                .env("KABOT_BACKEND_PORT", port.to_string());
                
            let (mut rx, child) = sidecar_command
                .spawn()
                .expect("Failed to spawn sidecar");

            struct BackendProcess(Option<tauri_plugin_shell::process::CommandChild>);
            impl Drop for BackendProcess {
                fn drop(&mut self) {
                    if let Some(child) = self.0.take() {
                        let _ = child.kill();
                    }
                }
            }
            app.manage(BackendProcess(Some(child)));

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(line) = event {
                        println!("backend: {}", String::from_utf8_lossy(&line));
                    } else if let CommandEvent::Stderr(line) = event {
                        println!("backend err: {}", String::from_utf8_lossy(&line));
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
