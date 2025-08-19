import os
import logging
from datetime import datetime

class LoggerManager:
    def __init__(self, app_name="FaceVerificationApp"):
        self.log_dir = os.path.join(os.getenv('ProgramData'), app_name, 'Logs')
        os.makedirs(self.log_dir, exist_ok=True)

        log_filename = f"log_{datetime.now().strftime('%Y-%m-%d')}.log"
        logging.basicConfig(
            filename=os.path.join(self.log_dir, log_filename),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='a'
        )

    def start_session(self):
        logging.info("Application starting new session...")

    def stop_session(self):
        logging.info("Application shutting down.")

    def log_event(self, message, level="info"):
        getattr(logging, level)(message)

    def get_log_dir(self):
        return self.log_dir
    
    def start_session(self):
        logging.info("Application starting new session")

    def stop_session(self):
        logging.info("Application shutting down")

    def monitoring_started(self):
        logging.info("Monitoring started by user")

    def monitoring_stopped(self):
        logging.info("Monitoring stopped by user")

    def system_locked(self):
        logging.info("System locked")

    def system_unlocked(self):
        logging.info("System unlocked")

    def camera_inaccessible(self):
        logging.info("Camera inaccessible")

    def camera_accessible(self):
        logging.info("Camera accessible again")
