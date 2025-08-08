# components.py
import os
import time
import uuid
import psycopg2
import requests
import cv2
from datetime import datetime, timedelta

class Recorder:
    """A simple, continuous webcam recorder."""
    def __init__(self, output_dir="video_captures", duration=30):
        self.output_dir = output_dir
        self.duration = duration
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def run(self):
        print("✅ Recorder process started. Saving clips to 'video_captures'.")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Recorder Error: Cannot open webcam.")
            return

        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 20
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')

        try:
            while True:
                filename_ts = time.strftime("%Y%m%d_%H%M%S")
                video_path = os.path.join(self.output_dir, f"capture_{filename_ts}.mp4")
                video_writer = cv2.VideoWriter(video_path, fourcc, fps, (frame_width, frame_height))
                start_time = time.time()

                while (time.time() - start_time) < self.duration:
                    ret, frame = cap.read()
                    if ret:
                        video_writer.write(frame)
                    else:
                        break
                video_writer.release()
        except KeyboardInterrupt:
            print("Recorder process stopping.")
        finally:
            cap.release()
            cv2.destroyAllWindows()

class Uploader:
    """
    Gets a job for a SINGLE video from the queue, waits for it,
    uploads it, and updates the DB for all associated alerts.
    """
    def __init__(self, job_queue, db_url, video_dir="video_captures"):
        self.job_queue = job_queue
        self.db_url = db_url
        self.video_dir = video_dir
        self.server_url = "http://127.0.0.1:5000/upload"
        self.wait_timeout = 120

    def _insert_db_records(self, conn, filename, alert_ids):
        sql = "INSERT INTO video_evidence (alert_id, video_filename, uploaded_at) VALUES (%s, %s, %s)"
        for alert_id in alert_ids:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, (alert_id, filename, datetime.now()))
                print(f"    -> DB record created for alert {alert_id}")
            except Exception as e:
                print(f"    -> ❌ DB Error for alert {alert_id}: {e}")
        conn.commit()

    def _upload_file(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                response = requests.post(self.server_url, files={'file': f}, timeout=15)
            if response.status_code == 200:
                print(f"  -> ✅ Upload successful: {os.path.basename(filepath)}")
                return True
            else:
                print(f"  -> ❌ Upload failed. Server returned {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  -> ❌ Upload failed for {os.path.basename(filepath)}: {e}")
        return False

    def run(self):
        print("✅ Uploader process started. Waiting for jobs...")
        conn = psycopg2.connect(self.db_url)
        while True:
            job = self.job_queue.get()
            filename = job['video_filename']
            alert_ids = job['alert_ids']
            filepath = os.path.join(self.video_dir, filename)
            
            print(f"\nProcessing job for video: {filename} (Alerts: {len(alert_ids)})")

            start_wait = time.time()
            while not os.path.exists(filepath):
                if time.time() - start_wait > self.wait_timeout:
                    print(f"  -> ❌ Timed out waiting for {filename}. Skipping job.")
                    continue
                time.sleep(1)
            
            if self._upload_file(filepath):
                self._insert_db_records(conn, filename, alert_ids)


class Cleaner:
    """Periodically cleans up old video files, keeping the last 5."""
    def __init__(self, video_dir="video_captures", interval=300):
        self.video_dir = video_dir
        self.interval = interval

    def run(self):
        print(f"✅ Cleaner process started. Will run every {self.interval/60} minutes.")
        while True:
            time.sleep(self.interval)
            print("\n--- Running cleanup job ---")

            try:
                files = [f for f in os.listdir(self.video_dir) if f.endswith('.mp4')]
                files.sort()

                if len(files) > 5:
                    files_to_delete = files[:-5]
                    print(f"Found {len(files_to_delete)} old file(s) to delete.")
                    for f in files_to_delete:
                        try:
                            os.remove(os.path.join(self.video_dir, f))
                            print(f"  - Deleted {f}")
                        except OSError as e:
                            print(f"  - ❌ Error deleting {f}: {e}")
                else:
                    print("No old files to delete.")
            except Exception as e:
                print(f"❌ An error occurred during cleanup: {e}")