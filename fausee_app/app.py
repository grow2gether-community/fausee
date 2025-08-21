import threading
import webbrowser
import os
import time

from logger_manager import LoggerManager
from db_manager import DBManager
from log_analyzer import LogAnalyzer
from face_recognition_manager import FaceRecognitionManager
from flask_app import app as flask_app
from gui_app import DashboardApp  # kept for webless/Tk testing if needed
from controller_api import create_controller_api
from flask import send_from_directory, render_template_string

USE_ELECTRON = os.environ.get("ELECTRON", "1") != "0"  # default to Electron UI

def background_log_update(analyzer, interval_sec=900):
    while True:
        try:
            usage = analyzer.process_today()
            if usage:
                print(f"[Background] Usage DB updated: {usage}")
        except Exception as e:
            print(f"[Background] Log analyzer error: {e}")
        time.sleep(interval_sec)

class MonitorAppController:
    def __init__(self):
        self.logger_manager = LoggerManager()
        self.db_manager = DBManager()
        self.analyzer = LogAnalyzer(self.logger_manager.get_log_dir(), self.db_manager)
        image_dir = os.path.join(os.getenv('ProgramData') or '.', 'FaceVerificationApp', 'Images')
        self.face_manager = FaceRecognitionManager(self.logger_manager, image_dir=image_dir)

        self.authenticated = self.db_manager.get_user() is not None
        self.monitoring_active = False

        self.recognition_thread = None
        self.log_analyzer_thread = None

        self.session_listener_thread = threading.Thread(
            target=self.face_manager.start_session_event_listener,
            daemon=True
        )
        self.session_listener_thread.start()
        self.logger_manager.log_event("Session event listener started.")

    def refresh_auth_state(self):
        self.authenticated = self.db_manager.get_user() is not None
        return self.authenticated

    def start_auth_flow(self):
        try:
            webbrowser.open("http://127.0.0.1:5000/login")
            self.logger_manager.log_event("Opened browser for user sign-in.")
        except Exception as e:
            self.logger_manager.log_event(f"Failed to open browser for auth: {e}", level="error")

    def verify_password_only(self, password: str) -> bool:
        user = self.db_manager.get_user()
        if not user:
            self.logger_manager.log_event("No user found in DB. Cannot verify password.", level="error")
            return False
        username, _ = user
        return self.db_manager.verify_user(username, password)

    def update_reference_image(self, parent_window=None):
        self.face_manager.update_reference_image(parent_window=parent_window)

    def bootstrap_reference_embedding(self):
        emb = self.face_manager.ensure_reference_embedding()
        if emb is None:
            self.logger_manager.log_event(
                "Fatal: Could not initialize reference embedding. Recognition cannot start.",
                level="critical"
            )
        return emb

    def _loop_with_restart(self, loop_fn, *args):
        while True:
            try:
                loop_fn(*args)
            except Exception as e:
                self.logger_manager.log_event(f"Loop crashed: {e}. Restarting in 3s...", level="error")
                time.sleep(3)
                continue
            self.logger_manager.log_event("Loop ended unexpectedly. Restarting in 3s...", level="warning")
            time.sleep(3)

    def start_recognition_loop(self, parent_window=None, use_reference=True):
        if not self.refresh_auth_state():
            self.logger_manager.log_event("Blocked start: user not authenticated.", level="warning")
            return

        if self.recognition_thread and self.recognition_thread.is_alive():
            self.logger_manager.log_event("Recognition already running. Resuming...")
            self.face_manager.pause_recognition.clear()
            self.monitoring_active = True
            return

        self.face_manager.pause_recognition.clear()
        self.monitoring_active = True

        if use_reference:
            ref_embed = self.face_manager.ensure_reference_embedding()
            if ref_embed is None:
                self.logger_manager.log_event("No reference image found. Prompting user for capture.", level="info")
                self.face_manager.update_reference_image(parent_window=parent_window)
                ref_embed = self.face_manager.ensure_reference_embedding()
                if ref_embed is None:
                    self.logger_manager.log_event("Reference capture cancelled or failed. Monitoring not started.", level="warning")
                    self.monitoring_active = False
                    return

            self.logger_manager.log_event("Monitoring started by user (reference mode)")
            self.recognition_thread = threading.Thread(
                target=self._loop_with_restart,
                args=(self.face_manager.recognition_loop, ref_embed),
                daemon=True
            )
        else:
            self.logger_manager.log_event("Monitoring started by user (general presence mode)")
            self.recognition_thread = threading.Thread(
                target=self._loop_with_restart,
                args=(self.face_manager.monitor_loop,),
                daemon=True
            )

        self.recognition_thread.start()

    def stop_recognition(self):
        self.face_manager.pause_recognition.set()
        self.monitoring_active = False
        self.logger_manager.log_event("Monitoring stopped by user")

    def start_log_analyzer_loop(self):
        if self.log_analyzer_thread and self.log_analyzer_thread.is_alive():
            self.logger_manager.log_event("Log analyzer thread already running.")
            return
        self.logger_manager.log_event("Starting log analyzer background thread.")
        self.log_analyzer_thread = threading.Thread(
            target=background_log_update,
            args=(self.analyzer,),
            daemon=True
        )
        self.log_analyzer_thread.start()

    def trigger_log_analysis_now(self):
        try:
            usage = self.analyzer.process_today()
            if usage:
                self.logger_manager.log_event(f"[Manual] Usage DB updated: {usage}")
        except Exception as e:
            self.logger_manager.log_event(f"Manual log analysis failed: {e}", level="error")

# -------- Flask & App bootstrap --------

def run_flask(controller: MonitorAppController):
    # Register API blueprint
    api_bp = create_controller_api(controller)
    flask_app.register_blueprint(api_bp)

    # Serve a minimal UI (same for web & Electron)
    @flask_app.route("/ui")
    def ui_index():
        # Simple single page (feel free to swap with React build later)
        html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Monitoring Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto; background:#0f1224; color:#e6e8ef; margin:0; }
    header { padding:16px 24px; border-bottom:1px solid #252a44; display:flex; justify-content:space-between; align-items:center; }
    .btn { padding:10px 14px; border:0; border-radius:10px; background:#8ab4ff; color:#0f1224; font-weight:600; cursor:pointer; margin-right:8px; }
    .btn.alt { background:#eebbc3; color:#232946; }
    .btn.warn { background:#ffb4ab; color:#3b0a0a; }
    .row { display:flex; gap:12px; flex-wrap:wrap; align-items:center; }
    .status { margin:12px 24px; display:flex; gap:16px; flex-wrap:wrap; }
    .chip { background:#1b2040; border:1px solid #252a44; border-radius:999px; padding:8px 12px; }
    table { border-collapse:collapse; width:100%; }
    th, td { padding:10px 12px; border-bottom:1px solid #252a44; text-align:center; }
    .card { background:#111432; border:1px solid #252a44; border-radius:16px; padding:16px; margin:16px 24px; }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
    .muted { opacity:.8; }
    select { background: #1b2040; color: #e6e8ef; border: 1px solid #252a44; border-radius: 8px; padding: 6px 10px; }
    .refresh-btn { cursor: pointer; background: none; border: none; font-size: 20px; color: #e6e8ef; }
  </style>
</head>
<body>
  <header>
    <div class="row">
      <h3 style="margin:0;">Monitoring Dashboard</h3>
      <div id="auth" class="chip muted">Auth: …</div>
      <div id="mon" class="chip muted">Monitoring: …</div>
    </div>
    <div class="row">
      <button id="login" class="btn alt">Open Login</button>
      <button id="updateRef" class="btn">Update Reference Image</button>
      <button id="startRef" class="btn">Start (You)</button>
      <button id="startPresence" class="btn">Start (Presence)</button>
      <button id="stop" class="btn warn">Stop</button>
    </div>
  </header>

  <section class="status">
    <div id="statusMsg" class="chip">Ready.</div>
  </section>

  <section class="card">
    <div class="card-header">
      <h4 style="margin:0;">Usage Stats</h4>
      <div class="row">
        <select id="statsFilter">
          <option value="all">All</option>
          <option value="today">Today</option>
          <option value="week">This Week</option>
          <option value="month">This Month</option>
        </select>
        <button id="refreshStats" class="refresh-btn">&#x21bb;</button>
      </div>
    </div>
    <table>
      <thead><tr>
        <th>Date</th><th>Total Monitored</th><th>Screen Time</th><th>Active Time</th><th>Updated At</th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </section>

<script>
function fmt(sec) {
  sec = Number(sec||0);
  const h = Math.floor(sec/3600);
  const m = Math.floor((sec%3600)/60);
  const s = sec%60;
  return String(h).padStart(2,"0")+":"+String(m).padStart(2,"0")+":"+String(s).padStart(2,"0");
}
async function refresh() {
  setStatus("Refreshing stats...");
  // First, trigger a new log analysis to ensure data is up-to-date
  await fetch("/api/analyze-logs", { method: "POST" });

  // Now, fetch the latest status and stats data
  const st = await fetch("/api/status").then(r=>r.json());
  document.getElementById("auth").textContent = "Auth: " + (st.authenticated ? "Authenticated" : "Not authenticated");
  document.getElementById("mon").textContent = "Monitoring: " + (st.monitoring ? "ACTIVE" : "INACTIVE");
  
  const filter = document.getElementById("statsFilter").value;
  const data = await fetch(`/api/stats?filter=${filter}`).then(r=>r.json());
  const tb = document.getElementById("rows"); tb.innerHTML = "";
  for (const r of data.rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.date}</td>
      <td>${fmt(r.total_monitored)}</td>
      <td>${fmt(r.screen_time)}</td>
      <td>${fmt(r.active_time)}</td>
      <td>${r.updated_at}</td>`;
    tb.appendChild(tr);
  }
  setStatus("Dashboard refreshed.");
}
async function setStatus(msg){ document.getElementById("statusMsg").textContent = msg; }

document.getElementById("login").onclick = async () => {
  const u = await fetch("/api/login-url").then(r=>r.json());
  window.open(u.url, "_blank");
  setStatus("Opened login page.");
};
document.getElementById("updateRef").onclick = async () => {
  await fetch("/api/update-ref", {method:"POST"});
  setStatus("Reference image update requested.");
};
document.getElementById("startRef").onclick = async () => {
  await fetch("/api/start?mode=reference", {method:"POST"});
  setStatus("Started monitoring (reference mode).");
  refresh();
};
document.getElementById("startPresence").onclick = async () => {
  await fetch("/api/start?mode=presence", {method:"POST"});
  setStatus("Started monitoring (presence mode).");
  refresh();
};
document.getElementById("stop").onclick = async () => {
  await fetch("/api/stop", {method:"POST"});
  setStatus("Stopped monitoring.");
  refresh();
};
document.getElementById("statsFilter").onchange = refresh;
document.getElementById("refreshStats").onclick = refresh;

refresh();
setInterval(refresh, 30000); // refresh every 30 seconds to keep data fresh
</script>
</body>
</html>
        """
        return render_template_string(html)

    flask_app.run(host='127.0.0.1', port=5000, debug=False)

def run_app():
    controller = MonitorAppController()
    controller.start_log_analyzer_loop()

    # Start Flask in its own thread if we will still run Tkinter, else run here synchronously
    if USE_ELECTRON:
        # Electron will open /ui; run Flask on main thread
        run_flask(controller)
    else:
        # Legacy Tkinter mode (debug/testing) – Flask on background thread + Tk dashboard
        flask_thread = threading.Thread(target=run_flask, args=(controller,), daemon=True)
        flask_thread.start()

        app = DashboardApp(controller)
        try:
            app.mainloop()
        except KeyboardInterrupt:
            if controller.monitoring_active:
                controller.stop_recognition()
                controller.logger_manager.log_event("Monitoring stopped by user (Keyboard interrupt).")
            controller.logger_manager.stop_session()

if __name__ == "__main__":
    run_app()