import threading
import time
import os
import sys
from logger_manager import LoggerManager
from db_manager import DBManager
from log_analyzer import LogAnalyzer
from face_recognition_manager import FaceRecognitionManager

def background_log_update(analyzer, interval_sec=3600):
    while True:
        usage = analyzer.process_today()
        if usage:
            print(f"[Background] Usage DB updated: {usage}")
        time.sleep(interval_sec)

if __name__ == "__main__":
    image_dir = os.path.join(os.getenv('ProgramData'), 'FaceVerificationApp', 'Images')

    logger_manager = LoggerManager()
    db_manager = DBManager()
    analyzer = LogAnalyzer(logger_manager.get_log_dir(), db_manager)
    face_recognition = FaceRecognitionManager(logger_manager, image_dir=image_dir)
    logger_manager.start_session()

    # Start system session event listener in a separate thread
    threading.Thread(target=face_recognition.start_session_event_listener, daemon=True).start()

    # Start background thread for periodic log analytics updates
    threading.Thread(target=background_log_update, args=(analyzer,), daemon=True).start()

    # Get reference embedding
    ref_embedding = face_recognition.ref_embedding
    if ref_embedding is None:
        logger_manager.log_event("Reference embedding unavailable. Exiting.", level="critical")
        sys.exit(1)

    try:

        logger_manager.log_event("Starting continuous employee verification...")

        face_recognition.recognition_loop(ref_embedding)

    except KeyboardInterrupt:
        logger_manager.log_event("Application interrupted by user.", level="warning")

    finally:
        logger_manager.stop_session()
        logger_manager.log_event("Application shutting down.")
