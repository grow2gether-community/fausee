# import threading
# import webbrowser
# import os
# import time
# import tkinter as tk
# from tkinter import messagebox

# from logger_manager import LoggerManager
# from db_manager import DBManager
# from log_analyzer import LogAnalyzer
# from face_recognition_manager import FaceRecognitionManager
# from flask_app import app as flask_app
# from gui_app import DashboardApp

# def background_log_update(analyzer, interval_sec=900):
#     """Periodically processes logs in a background thread."""
#     while True:
#         try:
#             usage = analyzer.process_today()
#             if usage:
#                 print(f"[Background] Usage DB updated: {usage}")
#         except Exception as e:
#             print(f"[Background] Log analyzer error: {e}")
#         time.sleep(interval_sec)

# class MonitorAppController:
#     """
#     Orchestrates auth state, recognition lifecycle, session listener, and background jobs.
#     """
#     def __init__(self):
#         self.logger_manager = LoggerManager()
#         self.db_manager = DBManager()
#         self.analyzer = LogAnalyzer(self.logger_manager.get_log_dir(), self.db_manager)
#         image_dir = os.path.join(os.getenv('ProgramData') or '.', 'FaceVerificationApp', 'Images')
#         self.face_manager = FaceRecognitionManager(self.logger_manager, image_dir=image_dir)

#         # Session/application flags
#         self.authenticated = False          # set True once the user completes login
#         self.monitoring_active = False      # True while recognition loop is running (not paused by user)

#         self.recognition_thread = None
#         self.log_analyzer_thread = None

#         # Start Windows session lock/unlock listener
#         self.session_listener_thread = threading.Thread(
#             target=self.face_manager.start_session_event_listener,
#             daemon=True
#         )
#         self.session_listener_thread.start()
#         self.logger_manager.log_event("Session event listener started.")

#     # -------- Auth helpers --------

#     def start_auth_flow(self):
#         """Open login page in the browser."""
#         try:
#             webbrowser.open("http://127.0.0.1:5000/login")
#             self.logger_manager.log_event("Opened browser for user sign-in.")
#         except Exception as e:
#             self.logger_manager.log_event(f"Failed to open browser for auth: {e}", level="error")

#     def set_authenticated(self, value: bool):
#         """Called after user confirms they've completed login."""
#         self.authenticated = bool(value)
#         self.logger_manager.log_event(f"Authenticated flag set to {self.authenticated}.")

#     def verify_password_only(self, password: str) -> bool:
#         """
#         Verify the provided password against the stored user in the DB.
#         Since only one user exists, we fetch its username and compare.
#         """
#         user = self.db_manager.get_user()
#         if not user:
#             self.logger_manager.log_event("No user found in DB. Cannot verify password.", level="error")
#             return False
#         username, _ = user
#         return self.db_manager.verify_user(username, password)

#     # -------- Bootstrap for ref embedding --------

#     def bootstrap_reference_embedding(self):
#         """
#         Ensure we have a valid ref embedding. If not cached, capture an image and compute one.
#         """
#         emb = self.face_manager.ensure_reference_embedding()
#         if emb is None:
#             self.logger_manager.log_event(
#                 "Fatal: Could not initialize reference embedding. Recognition cannot start.",
#                 level="critical"
#             )
#         return emb

#     # -------- Loop lifecycle --------

#     def _loop_with_restart(self, loop_fn, *args):
#         """Run loop; if it returns or crashes, restart after a small delay."""
#         while True:
#             try:
#                 loop_fn(*args)
#             except Exception as e:
#                 self.logger_manager.log_event(f"Loop crashed: {e}. Restarting in 3s...", level="error")
#                 time.sleep(3)
#                 continue
#             self.logger_manager.log_event("Loop ended unexpectedly. Restarting in 3s...", level="warning")
#             time.sleep(3)

#     def start_recognition_loop(self):
#         """
#         Start/resume recognition loop if authenticated.
#         """
#         if not self.authenticated:
#             self.logger_manager.log_event("Blocked start: user not authenticated.", level="warning")
#             return

#         ref_embed = self.bootstrap_reference_embedding()
#         if ref_embed is None:
#             return

#         # If thread exists & alive, just resume
#         if self.recognition_thread and self.recognition_thread.is_alive():
#             self.logger_manager.log_event("Recognition already running. Resuming...")
#             self.face_manager.pause_recognition.clear()
#             self.monitoring_active = True
#             return

#         # Start fresh thread
#         self.logger_manager.log_event("Starting recognition loop in background thread.")
#         self.face_manager.pause_recognition.clear()
#         self.recognition_thread = threading.Thread(
#             target=self._loop_with_restart,
#             args=(self.face_manager.recognition_loop, ref_embed),
#             daemon=True
#         )
#         self.recognition_thread.start()
#         self.monitoring_active = True

#     def stop_recognition(self):
#         """
#         User-initiated stop: pause the recognition loop (thread stays alive, waiting for resume).
#         """
#         self.face_manager.pause_recognition.set()
#         self.monitoring_active = False
#         self.logger_manager.log_event("Recognition paused by user.")

#     # Backwards-compat alias (if GUI still calls stop_monitoring)
#     def stop_monitoring(self):
#         self.stop_recognition()

#     # -------- Background log analyzer --------

#     def start_log_analyzer_loop(self):
#         """Starts the background thread for periodic log analysis."""
#         if self.log_analyzer_thread and self.log_analyzer_thread.is_alive():
#             self.logger_manager.log_event("Log analyzer thread already running.")
#             return
#         self.logger_manager.log_event("Starting log analyzer background thread.")
#         self.log_analyzer_thread = threading.Thread(
#             target=background_log_update,
#             args=(self.analyzer,),
#             daemon=True
#         )
#         self.log_analyzer_thread.start()

#     def trigger_log_analysis_now(self):
#         """Manually triggers an immediate log analysis."""
#         try:
#             usage = self.analyzer.process_today()
#             if usage:
#                 self.logger_manager.log_event(f"[Manual] Usage DB updated: {usage}")
#         except Exception as e:
#             self.logger_manager.log_event(f"Manual log analysis failed: {e}", level="error")

# # -------- Flask & App bootstrap --------

# def run_flask():
#     """Runs the Flask web server."""
#     flask_app.run(host='127.0.0.1', port=5000, debug=False)

# def run_app():
#     """Initializes the controller and runs the main application."""
#     controller = MonitorAppController()

#     # Start log analyzer + Flask
#     controller.start_log_analyzer_loop()
#     flask_thread = threading.Thread(target=run_flask, daemon=True)
#     flask_thread.start()

#     # Prompt user to sign in first (open browser)
#     controller.start_auth_flow()

#     # DO NOT auto-start recognition if sign-in not completed.
#     # Proceed to dashboard; Start button will handle auth gating.

#     app = DashboardApp(controller)
#     app.mainloop()

# if __name__ == "__main__":
#     run_app()


import threading
import webbrowser
import os
import time

from logger_manager import LoggerManager
from db_manager import DBManager
from log_analyzer import LogAnalyzer
from face_recognition_manager import FaceRecognitionManager
from flask_app import app as flask_app
from gui_app import DashboardApp

def background_log_update(analyzer, interval_sec=900):
    """Periodically processes logs in a background thread."""
    while True:
        try:
            usage = analyzer.process_today()
            if usage:
                print(f"[Background] Usage DB updated: {usage}")
        except Exception as e:
            print(f"[Background] Log analyzer error: {e}")
        time.sleep(interval_sec)

class MonitorAppController:
    """
    Orchestrates auth state, recognition lifecycle, session listener, and background jobs.
    """
    def __init__(self):
        self.logger_manager = LoggerManager()
        self.db_manager = DBManager()
        self.analyzer = LogAnalyzer(self.logger_manager.get_log_dir(), self.db_manager)
        image_dir = os.path.join(os.getenv('ProgramData') or '.', 'FaceVerificationApp', 'Images')
        self.face_manager = FaceRecognitionManager(self.logger_manager, image_dir=image_dir)

        # Session/application flags
        self.authenticated = self.db_manager.get_user() is not None
        self.monitoring_active = False

        self.recognition_thread = None
        self.log_analyzer_thread = None

        # Start Windows session lock/unlock listener
        self.session_listener_thread = threading.Thread(
            target=self.face_manager.start_session_event_listener,
            daemon=True
        )
        self.session_listener_thread.start()
        self.logger_manager.log_event("Session event listener started.")

    # -------- Auth helpers --------

    def refresh_auth_state(self):
        """Refresh authenticated flag based on DB user existence."""
        self.authenticated = self.db_manager.get_user() is not None
        return self.authenticated

    def start_auth_flow(self):
        """Open login page in the browser."""
        try:
            webbrowser.open("http://127.0.0.1:5000/login")
            self.logger_manager.log_event("Opened browser for user sign-in.")
        except Exception as e:
            self.logger_manager.log_event(f"Failed to open browser for auth: {e}", level="error")

    def verify_password_only(self, password: str) -> bool:
        """Verify provided password against the stored user in DB."""
        user = self.db_manager.get_user()
        if not user:
            self.logger_manager.log_event("No user found in DB. Cannot verify password.", level="error")
            return False
        username, _ = user
        return self.db_manager.verify_user(username, password)

    def update_reference_image(self, parent_window=None):
        """Wrapper to call the face manager's update method, passing the GUI parent."""
        self.face_manager.update_reference_image(parent_window=parent_window)
        
    # -------- Bootstrap for ref embedding --------

    def bootstrap_reference_embedding(self):
        """Ensure we have a valid ref embedding (capture if missing)."""
        emb = self.face_manager.ensure_reference_embedding()
        if emb is None:
            self.logger_manager.log_event(
                "Fatal: Could not initialize reference embedding. Recognition cannot start.",
                level="critical"
            )
        return emb

    # -------- Loop lifecycle --------

    def _loop_with_restart(self, loop_fn, *args):
        """Run loop; if it returns or crashes, restart after delay."""
        while True:
            try:
                loop_fn(*args)
            except Exception as e:
                self.logger_manager.log_event(f"Loop crashed: {e}. Restarting in 3s...", level="error")
                time.sleep(3)
                continue
            self.logger_manager.log_event("Loop ended unexpectedly. Restarting in 3s...", level="warning")
            time.sleep(3)

    def start_recognition_loop(self, parent_window=None):
        if not self.refresh_auth_state():
            self.logger_manager.log_event("Blocked start: user not authenticated.", level="warning")
            return

        ref_embed = self.face_manager.ensure_reference_embedding()
        
        if ref_embed is None:
            self.logger_manager.log_event("No reference image found. Prompting user for capture.", level="info")
            # Pass the parent window to the update method
            self.face_manager.update_reference_image(parent_window=parent_window)
            
            ref_embed = self.face_manager.ensure_reference_embedding()

            if ref_embed is None:
                self.logger_manager.log_event("Reference image capture cancelled or failed. Recognition not started.", level="warning")
                return

        # If thread exists & alive, just resume
        if self.recognition_thread and self.recognition_thread.is_alive():
            self.logger_manager.log_event("Recognition already running. Resuming...")
            self.face_manager.pause_recognition.clear()
            self.monitoring_active = True
            return

        # Start fresh thread
        self.logger_manager.log_event("Starting recognition loop in background thread.")
        self.face_manager.pause_recognition.clear()
        self.recognition_thread = threading.Thread(
            target=self._loop_with_restart,
            args=(self.face_manager.recognition_loop, ref_embed),
            daemon=True
        )
        self.recognition_thread.start()
        self.monitoring_active = True

    def stop_recognition(self):
        """Pause the recognition loop."""
        self.face_manager.pause_recognition.set()
        self.monitoring_active = False
        self.logger_manager.log_event("Recognition paused by user.")

    # -------- Background log analyzer --------

    def start_log_analyzer_loop(self):
        """Starts the background thread for periodic log analysis."""
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
        """Manually triggers an immediate log analysis."""
        try:
            usage = self.analyzer.process_today()
            if usage:
                self.logger_manager.log_event(f"[Manual] Usage DB updated: {usage}")
        except Exception as e:
            self.logger_manager.log_event(f"Manual log analysis failed: {e}", level="error")

# -------- Flask & App bootstrap --------

def run_flask():
    """Runs the Flask web server."""
    flask_app.run(host='127.0.0.1', port=5000, debug=False)

def run_app():
    """Initializes the controller and runs the main application."""
    controller = MonitorAppController()

    # Start log analyzer + Flask
    controller.start_log_analyzer_loop()
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Launch GUI dashboard (Start button handles auth gating)
    app = DashboardApp(controller)
    app.mainloop()

if __name__ == "__main__":
    run_app()