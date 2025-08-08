# main.py
import os
import time
import uuid
from multiprocessing import Process, Manager
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Import the necessary classes (ensure you have the full components.py file)
from components import Recorder, Uploader, Cleaner

def alerter_task(job_queue):
    """
    This function now runs in the main process. It handles user input
    and places jobs on the shared queue using robust, file-based logic.
    """
    clip_duration = 30
    video_dir = "video_captures"
    wait_timeout = 45 # Seconds to wait for the initial alert clip to be written

    print("✅ Alerter is active. Press Enter to trigger an alert.")
    
    while True:
        input() # Blocks until Enter is pressed
        alert_time = datetime.now()
        new_alert_id = str(uuid.uuid4())
        print(f"🚨 Alert triggered at {alert_time.strftime('%H:%M:%S')}! ID: {new_alert_id}")

        # --- NEW ROBUST LOGIC ---

        # 1. Find the actual clip that contains the alert timestamp by reading the disk.
        #    This is crucial because the recorder's timing isn't perfect.
        alert_clip_info = None
        start_wait = time.time()
        print("   -> Searching for the corresponding video file...")
        while time.time() - start_wait < wait_timeout:
            # Get a sorted list of video files that have already been created
            try:
                available_files = sorted([f for f in os.listdir(video_dir) if f.endswith('.mp4')])
            except FileNotFoundError:
                available_files = []

            for filename in reversed(available_files): # Check recent files first
                try:
                    ts_str = filename.replace("capture_", "").replace(".mp4", "")
                    clip_start_time = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                    
                    if clip_start_time <= alert_time < clip_start_time + timedelta(seconds=clip_duration):
                        alert_clip_info = {'filename': filename, 'start_time': clip_start_time}
                        break
                except ValueError:
                    continue # Skip malformed filenames
            
            if alert_clip_info:
                print(f"   -> Found match: {alert_clip_info['filename']}")
                break
            time.sleep(1)
        
        if not alert_clip_info:
            print("   -> ❌ ERROR: Could not find a matching video clip. Is the recorder running?")
            continue

        # 2. Identify the full 5-clip evidence package based on the REAL files.
        try:
            # Get an up-to-date, sorted list of all available clips
            all_real_clips = sorted([f for f in os.listdir(video_dir) if f.endswith('.mp4')])
            alert_clip_index = all_real_clips.index(alert_clip_info['filename'])
        except (FileNotFoundError, ValueError):
            print("   -> ❌ ERROR: Could not find video files to build evidence package.")
            continue

        # Determine the slice of files we need
        start_index = max(0, alert_clip_index - 2)
        end_index = alert_clip_index + 2 # We aim for 2 files after

        # Get the files that already exist
        new_alert_targets = all_real_clips[start_index : alert_clip_index + 1]

        # Predict the names of the FUTURE clips based on the last KNOWN clip's time
        last_known_clip_name = new_alert_targets[-1]
        last_known_ts_str = last_known_clip_name.replace("capture_", "").replace(".mp4", "")
        last_known_time = datetime.strptime(last_known_ts_str, "%Y%m%d_%H%M%S")
        
        num_existing_after = 0 # In case the next clip already exists
        if alert_clip_index + 1 < len(all_real_clips):
            new_alert_targets.append(all_real_clips[alert_clip_index + 1])
            num_existing_after = 1

        # Predict the remaining future clips needed to make a total of 5
        num_to_predict = 5 - len(new_alert_targets)
        for i in range(1, num_to_predict + 1):
            next_clip_time = last_known_time + timedelta(seconds=clip_duration * (num_existing_after + i))
            next_filename = f"capture_{next_clip_time.strftime('%Y%m%d_%H%M%S')}.mp4"
            new_alert_targets.append(next_filename)

        # 3. Perform the intelligent queue update
        pending_jobs = []
        while not job_queue.empty():
            pending_jobs.append(job_queue.get())
        
        jobs_map = {job['video_filename']: job for job in pending_jobs}
        
        for target_file in new_alert_targets:
            if target_file in jobs_map:
                jobs_map[target_file]['alert_ids'].append(new_alert_id)
                print(f"   -> Merging alert into existing job for {target_file}")
            else:
                new_job = {'video_filename': target_file, 'alert_ids': [new_alert_id]}
                jobs_map[target_file] = new_job
                print(f"   -> Creating new job for {target_file}")

        for job in jobs_map.values():
            job_queue.put(job)


def main():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not found in .env file.")

    with Manager() as manager:
        shared_job_queue = manager.Queue()

        recorder = Recorder()
        uploader = Uploader(shared_job_queue, db_url)
        cleaner = Cleaner(interval=300)

        processes = [
            Process(target=recorder.run, name="Recorder"),
            Process(target=uploader.run, name="Uploader"),
            Process(target=cleaner.run, name="Cleaner")
        ]

        print("🚀 Starting background components...")
        for p in processes:
            p.start()

        try:
            alerter_task(shared_job_queue)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down all processes...")
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()
                    p.join()
            print("System shutdown complete.")

if __name__ == "__main__":
    main()