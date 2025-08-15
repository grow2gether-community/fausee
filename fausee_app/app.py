# import threading
# import webbrowser
# import os
# import time
# from logger_manager import LoggerManager
# from db_manager import DBManager
# from log_analyzer import LogAnalyzer
# from face_recognition_manager import FaceRecognitionManager
# from flask_app import app as flask_app
# from gui_app import DashboardApp

# def background_log_update(analyzer, interval_sec=900):
#     while True:
#         usage = analyzer.process_today()
#         if usage:
#             print(f"[Background] Usage DB updated: {usage}")
#         time.sleep(interval_sec)

# class MonitorAppController:
#     def __init__(self):
#         self.logger_manager = LoggerManager()
#         self.db_manager = DBManager()
#         self.analyzer = LogAnalyzer(self.logger_manager.get_log_dir(), self.db_manager)
#         image_dir = os.path.join(os.getenv('ProgramData') or '.', 'FaceVerificationApp', 'Images')
#         self.face_manager = FaceRecognitionManager(self.logger_manager, image_dir=image_dir)
#         self.monitor_thread = None
#         self.log_analyzer_thread = None

#     def start_monitoring_loop(self):
#         if self.monitor_thread and self.monitor_thread.is_alive():
#             self.logger_manager.log_event("Monitoring loop already running.")
#             return
#         self.logger_manager.log_event("Starting monitoring loop in background thread.")
#         self.face_manager.pause_recognition.clear()  # Clear pause before start
#         self.monitor_thread = threading.Thread(target=self.face_manager.monitor_loop, daemon=True)
#         self.monitor_thread.start()

#     def start_recognition_loop(self, ref_embedding):
#         if self.monitor_thread and self.monitor_thread.is_alive():
#             self.logger_manager.log_event("Monitoring loop already running.")
#             return
#         self.logger_manager.log_event("Starting recognition loop in background thread.")
#         self.face_manager.pause_recognition.clear()  # Clear pause before start
#         self.monitor_thread = threading.Thread(target=self.face_manager.recognition_loop, args=(ref_embedding,), daemon=True)
#         self.monitor_thread.start()

#     def start_log_analyzer_loop(self):
#         if self.log_analyzer_thread and self.log_analyzer_thread.is_alive():
#             self.logger_manager.log_event("Log analyzer thread already running.")
#             return
#         self.logger_manager.log_event("Starting log analyzer background thread.")
#         self.log_analyzer_thread = threading.Thread(target=background_log_update,
#                                                     args=(self.analyzer,),
#                                                     daemon=True)
#         self.log_analyzer_thread.start()

#     def trigger_log_analysis_now(self):
#         usage = self.analyzer.process_today()
#         if usage:
#             self.logger_manager.log_event(f"[Manual] Usage DB updated: {usage}")

#     def stop_monitoring(self):
#         self.face_manager.pause_recognition.set()  # Set pause flag to stop loops
#         self.logger_manager.log_event("Monitoring stopped by user.")

# def run_flask():
#     flask_app.run(host='127.0.0.1', port=5000, debug=False)

# def run_app():
#     controller = MonitorAppController()
#     controller.start_log_analyzer_loop()
#     flask_thread = threading.Thread(target=run_flask, daemon=True)
#     flask_thread.start()
#     webbrowser.open("http://127.0.0.1:5000/login")
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
        usage = analyzer.process_today()
        if usage:
            print(f"[Background] Usage DB updated: {usage}")
        time.sleep(interval_sec)

class MonitorAppController:
    """
    Manages the application's core logic, including starting and stopping
    monitoring threads and handling background tasks.
    """
    def __init__(self):
        self.logger_manager = LoggerManager()
        self.db_manager = DBManager()
        self.analyzer = LogAnalyzer(self.logger_manager.get_log_dir(), self.db_manager)
        image_dir = os.path.join(os.getenv('ProgramData') or '.', 'FaceVerificationApp', 'Images')
        self.face_manager = FaceRecognitionManager(self.logger_manager, image_dir=image_dir)
        
        self.monitor_thread = None
        self.log_analyzer_thread = None
        
        # **FIX**: Start the session event listener to detect system lock/unlock.
        # This needs to run in its own thread because it's a blocking call.
        self.session_listener_thread = threading.Thread(
            target=self.face_manager.start_session_event_listener, 
            daemon=True
        )
        self.session_listener_thread.start()
        self.logger_manager.log_event("Session event listener started.")

    def start_monitoring_loop(self):
        """
        Starts or resumes the monitoring loop. If the thread is already running
        (i.e., paused), it resumes it. Otherwise, it starts a new thread.
        """
        # **FIX**: If thread is alive (even if paused), just resume it.
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.logger_manager.log_event("Monitoring is already running. Resuming...")
            self.face_manager.pause_recognition.clear()
            return
        
        # If no thread exists or it has died, start a new one.
        self.logger_manager.log_event("Starting monitoring loop in background thread.")
        self.face_manager.pause_recognition.clear()
        self.monitor_thread = threading.Thread(target=self.face_manager.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def start_recognition_loop(self, ref_embedding):
        """
        Starts or resumes the recognition loop. If the thread is already running
        (i.e., paused), it resumes it. Otherwise, it starts a new thread.
        """
        # **FIX**: If thread is alive (even if paused), just resume it.
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.logger_manager.log_event("Recognition is already running. Resuming...")
            self.face_manager.pause_recognition.clear()
            return

        # If no thread exists or it has died, start a new one.
        self.logger_manager.log_event("Starting recognition loop in background thread.")
        self.face_manager.pause_recognition.clear()
        self.monitor_thread = threading.Thread(
            target=self.face_manager.recognition_loop, 
            args=(ref_embedding,), 
            daemon=True
        )
        self.monitor_thread.start()

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
        usage = self.analyzer.process_today()
        if usage:
            self.logger_manager.log_event(f"[Manual] Usage DB updated: {usage}")

    def stop_monitoring(self):
        """
        Pauses the monitoring/recognition loop by setting the pause event.
        The loop will wait until it is resumed.
        """
        self.face_manager.pause_recognition.set()
        self.logger_manager.log_event("Monitoring paused by user.")

def run_flask():
    """Runs the Flask web server."""
    flask_app.run(host='127.0.0.1', port=5000, debug=False)

def run_app():
    """Initializes the controller and runs the main application."""
    controller = MonitorAppController()
    controller.start_log_analyzer_loop()
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    webbrowser.open("http://127.0.0.1:5000/login")
    app = DashboardApp(controller)
    app.mainloop()

if __name__ == "__main__":
    run_app()
