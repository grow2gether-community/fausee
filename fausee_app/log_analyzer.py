import os
import re
from datetime import datetime, timedelta

class LogAnalyzer:
    # EVENT_PATTERNS = {
    #     "start": re.compile(r"Application starting new session", re.IGNORECASE),
    #     "stop": re.compile(r"Application shutting down", re.IGNORECASE),
    #     "lockdown_start": re.compile(r"System locked", re.IGNORECASE),
    #     "lockdown_end": re.compile(r"System unlocked", re.IGNORECASE),
    #     "cam_inaccessible_start": re.compile(r"Camera inaccessible", re.IGNORECASE),
    #     "cam_inaccessible_end": re.compile(r"Camera is accessible", re.IGNORECASE),
    # }
    EVENT_PATTERNS = {
        "start": re.compile(r"Starting log analyzer background thread|Starting continuous employee verification|Loading reference embedding from cache", re.IGNORECASE),
        "stop": re.compile(r"Application shutting down", re.IGNORECASE),
        "lockdown_start": re.compile(r"System locked", re.IGNORECASE),
        "lockdown_end": re.compile(r"System unlocked", re.IGNORECASE),
        "cam_inaccessible_start": re.compile(r"Camera inaccessible", re.IGNORECASE),
        "cam_inaccessible_end": re.compile(r"Camera is accessible", re.IGNORECASE),
        "monitoring_stopped": re.compile(r"Monitoring stopped by user", re.IGNORECASE),
        # Add any further matched events here if needed
    }
    TIMESTAMP_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, log_dir, db_manager):
        self.log_dir = log_dir
        self.db_manager = db_manager

    def parse_logs(self, file_path):
        events = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as log_file:
            for line in log_file:
                ts_match = self.TIMESTAMP_REGEX.match(line)
                if not ts_match:
                    continue
                timestamp = datetime.strptime(ts_match.group(1), self.TIME_FORMAT)
                for key, pattern in self.EVENT_PATTERNS.items():
                    if pattern.search(line):
                        events.append({"event_key": key, "timestamp": timestamp})
                        break
        return sorted(events, key=lambda x: x["timestamp"])

    def calculate_usage(self, events):
        total_monitored = 0
        lockdown_time = 0
        inaccessible_time = 0

        lockdown_start = None
        cam_inacc_start = None
        session_start = None

        for e in events:
            key, ts = e['event_key'], e['timestamp']

            if key == "start":
                session_start = ts
            elif key == "stop" and session_start:
                total_monitored += (ts - session_start).total_seconds()
                session_start = None

            if key == "lockdown_start":
                lockdown_start = ts
            elif key == "lockdown_end" and lockdown_start:
                lockdown_time += (ts - lockdown_start).total_seconds()
                lockdown_start = None

            if key == "cam_inaccessible_start":
                cam_inacc_start = ts
            elif key == "cam_inaccessible_end" and cam_inacc_start:
                inaccessible_time += (ts - cam_inacc_start).total_seconds()
                cam_inacc_start = None

        if session_start and events:
            total_monitored += (events[-1]["timestamp"] - session_start).total_seconds()

        screen_time = total_monitored - lockdown_time
        active_time = screen_time - inaccessible_time

        return {
            "total_monitored": int(total_monitored),
            "screen_time": int(max(screen_time, 0)),
            "active_time": int(max(active_time, 0))
        }

    def process_today(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"log_{today_str}.log")
        if not os.path.exists(log_file):
            print(f"No log for today: {log_file}")
            return

        events = self.parse_logs(log_file)
        usage = self.calculate_usage(events)
        self.db_manager.upsert_usage(today_str, **usage)
        return usage
