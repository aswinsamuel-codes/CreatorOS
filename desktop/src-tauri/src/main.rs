// CreatorOS desktop app.
//
// Starts the bundled CreatorOS engine (a Python program packaged as a "sidecar"), shows the
// dashboard in a native window, and keeps running in the system tray.
//
// - Closing the window hides it to the tray; "Quit CreatorOS" in the tray menu really exits.
// - If an engine is already running on port 8787 (e.g. started with start_creatoros.bat or
//   Docker), the app simply uses it and won't stop it on exit.
// - Your data lives in the OS app-data folder (CREATOROS_HOME), so app updates never touch it.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{sync::Mutex, time::Duration};

use tauri::{
    menu::{CheckMenuItem, IsMenuItem, Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, RunEvent, WindowEvent, Wry,
};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

const PORT: u16 = 8787;

/// The engine process we started (None if we're using an engine that was already running).
struct Engine(Mutex<Option<CommandChild>>);

fn base_url() -> String {
    format!("http://127.0.0.1:{PORT}")
}

fn engine_running() -> bool {
    ureq::get(&format!("{}/api/status", base_url()))
        .timeout(Duration::from_secs(2))
        .call()
        .is_ok()
}

fn show_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
}

fn start_engine(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    if engine_running() {
        return Ok(()); // reuse the engine that's already running
    }
    let home = app.path().app_data_dir()?;
    std::fs::create_dir_all(&home)?;
    let (mut rx, child) = app
        .shell()
        .sidecar("creatoros-engine")?
        .env("CREATOROS_HOME", home.to_string_lossy().to_string())
        .env("CREATOROS_HOST", "127.0.0.1")
        .env("CREATOROS_PORT", PORT.to_string())
        .spawn()?;
    // Keep reading the engine's output so its log pipe never fills up and blocks it.
    tauri::async_runtime::spawn(async move { while rx.recv().await.is_some() {} });
    *app.state::<Engine>().0.lock().unwrap() = Some(child);
    Ok(())
}

fn stop_engine(app: &AppHandle) {
    let child = app.state::<Engine>().0.lock().unwrap().take();
    if let Some(child) = child {
        // Ask the engine to shut down cleanly, then make sure it's gone.
        let _ = ureq::post(&format!("{}/api/shutdown", base_url()))
            .timeout(Duration::from_secs(3))
            .call();
        std::thread::sleep(Duration::from_millis(800));
        let _ = child.kill();
    }
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Open CreatorOS", true, None::<&str>)?;
    let browser = MenuItem::with_id(app, "browser", "Open in browser", true, None::<&str>)?;
    let at_login = app.autolaunch().is_enabled().unwrap_or(false);
    let login = CheckMenuItem::with_id(app, "autostart", "Start at login", true, at_login, None::<&str>)?;
    let sep = PredefinedMenuItem::separator(app)?;
    let quit = MenuItem::with_id(app, "quit", "Quit CreatorOS", true, None::<&str>)?;
    let items: [&dyn IsMenuItem<Wry>; 5] = [&open, &browser, &login, &sep, &quit];
    let menu = Menu::with_items(app, &items)?;

    TrayIconBuilder::with_id("creatoros-tray")
        .icon(app.default_window_icon().cloned().expect("app icon"))
        .tooltip("CreatorOS")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "open" => show_window(app),
            "browser" => {
                let _ = tauri_plugin_shell::ShellExt::shell(app).open(base_url(), None);
            }
            "autostart" => {
                let launcher = app.autolaunch();
                if launcher.is_enabled().unwrap_or(false) {
                    let _ = launcher.disable();
                } else {
                    let _ = launcher.enable();
                }
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                show_window(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

fn main() {
    tauri::Builder::default()
        // A second launch just brings the existing window to the front.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_window(app)))
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, Some(vec!["--minimized"])))
        .manage(Engine(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            if let Err(e) = start_engine(&handle) {
                eprintln!("Could not start the CreatorOS engine: {e}");
            }
            build_tray(&handle)?;
            if std::env::args().any(|a| a == "--minimized") {
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.hide();
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // Closing the window keeps CreatorOS running in the tray.
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while starting CreatorOS")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                stop_engine(app);
            }
        });
}
