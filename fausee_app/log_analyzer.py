import os
import re
from datetime import datetime

class LogAnalyzer:
    """
    Computes daily aggregates from log lines based on intervals.
    - total_monitored: Time monitoring was enabled.
    - screen_time: total_monitored - locked_time.
    - active_time: screen_time - cam_inaccessible_time.
    """

    EVENT_PATTERNS = {
        "monitor_start": re.compile(r"Monitoring started by user", re.IGNORECASE),
        "monitor_stop": re.compile(r"Monitoring stopped by user", re.IGNORECASE),
        "lock": re.compile(r"System locked", re.IGNORECASE),
        "unlock": re.compile(r"System unlocked", re.IGNORECASE),
        "cam_inaccessible": re.compile(r"Camera inaccessible\b", re.IGNORECASE),
        "cam_accessible": re.compile(r"Camera accessible again\b", re.IGNORECASE),
    }

    TIMESTAMP_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, log_dir, db_manager):
        self.log_dir = log_dir
        self.db_manager = db_manager
        self._cache = {}

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        """Convert seconds into hh:mm:ss format string."""
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:02}"

    def parse_logs(self, file_path):
        events = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = self.TIMESTAMP_REGEX.match(line)
                if not m:
                    continue
                ts = datetime.strptime(m.group(1), self.TIME_FORMAT)
                for key, pat in self.EVENT_PATTERNS.items():
                    if pat.search(line):
                        events.append({"event_key": key, "timestamp": ts})
                        break
        return sorted(events, key=lambda e: e["timestamp"])

    @staticmethod
    def _build_intervals(events, start_key, stop_key, last_ts):
        intervals = []
        cur = None
        for e in events:
            if e["event_key"] == start_key:
                if cur is None:
                    cur = e["timestamp"]
            elif e["event_key"] == stop_key and cur:
                end = e["timestamp"]
                if end >= cur:
                    intervals.append((cur, end))
                cur = None
        if cur:
            intervals.append((cur, last_ts))
        return intervals

    @staticmethod
    def _sum_intervals(intervals):
        return sum((e - s).total_seconds() for s, e in intervals)

    @staticmethod
    def _sum_overlap(main_intervals, sub_intervals):
        total_overlap = 0.0
        for main_s, main_e in main_intervals:
            for sub_s, sub_e in sub_intervals:
                overlap_s = max(main_s, sub_s)
                overlap_e = min(main_e, sub_e)
                if overlap_e > overlap_s:
                    total_overlap += (overlap_e - overlap_s).total_seconds()
        return total_overlap

    def calculate_usage(self, events):
        if not events:
            return {"total_monitored": 0, "screen_time": 0, "active_time": 0}

        last_ts = datetime.now()

        monitor_intervals = self._build_intervals(events, "monitor_start", "monitor_stop", last_ts)
        if not monitor_intervals:
            return {"total_monitored": 0, "screen_time": 0, "active_time": 0}

        lock_intervals = self._build_intervals(events, "lock", "unlock", last_ts)
        cam_intervals = self._build_intervals(events, "cam_inaccessible", "cam_accessible", last_ts)

        total_monitored = self._sum_intervals(monitor_intervals)
        locked_time = self._sum_overlap(monitor_intervals, lock_intervals)
        cam_inaccessible_time = self._sum_overlap(monitor_intervals, cam_intervals)

        screen_time = max(0, total_monitored - locked_time)
        active_time = max(0, screen_time - cam_inaccessible_time)

        return {
            "total_monitored": int(total_monitored),
            "screen_time": int(screen_time),
            "active_time": int(active_time),
        }

    def process_today(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        path = os.path.join(self.log_dir, f"log_{today_str}.log")
        if not os.path.exists(path):
            usage = {"total_monitored": 0, "screen_time": 0, "active_time": 0}
            self.db_manager.upsert_usage(today_str, **usage)
            return {k: self._format_seconds(v) for k, v in usage.items()}

        mtime = os.path.getmtime(path)
        cached = self._cache.get(path)
        if cached and cached["mtime"] == mtime:
            return {k: self._format_seconds(v) for k, v in cached["result"].items()}

        events = self.parse_logs(path)
        usage = self.calculate_usage(events)
        self.db_manager.upsert_usage(today_str, **usage)

        self._cache[path] = {"mtime": mtime, "result": usage}
        return {k: self._format_seconds(v) for k, v in usage.items()}
