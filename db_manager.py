import os
import sqlite3
from datetime import datetime

class DBManager:
    def __init__(self, app_name="FaceVerificationApp"):
        data_dir = os.path.join(os.getenv('ProgramData'), app_name)
        os.makedirs(data_dir, exist_ok=True)
        self.db_file = os.path.join(data_dir, 'usage_stats.db')
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                date TEXT PRIMARY KEY,
                total_monitored INTEGER,
                screen_time INTEGER,
                active_time INTEGER,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def upsert_usage(self, date_str, total_monitored, screen_time, active_time):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""
            INSERT INTO usage_stats (date, total_monitored, screen_time, active_time, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_monitored=excluded.total_monitored,
                screen_time=excluded.screen_time,
                active_time=excluded.active_time,
                updated_at=excluded.updated_at
        """, (date_str, total_monitored, screen_time, active_time, now_str))
        conn.commit()
        conn.close()

    def read_all_stats(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT date, total_monitored, screen_time, active_time, updated_at FROM usage_stats")
        rows = c.fetchall()
        conn.close()
        return rows
