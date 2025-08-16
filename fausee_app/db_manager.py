# db_manager.py

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
        # Ensure usage_stats exists
        c.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                date TEXT PRIMARY KEY,
                total_monitored INTEGER,
                screen_time INTEGER,
                active_time INTEGER,
                updated_at TEXT
            )
        """)
        # Ensure users table exists
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT
            )
        """)
        conn.commit()
        conn.close()

    # -------------- USER AUTH METHODS ----------------
    def get_user(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT username, password FROM users LIMIT 1")
        user = cursor.fetchone()
        conn.close()
        return user

    def create_or_replace_user(self, username, password):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users")  # One user per device
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()

    def verify_user(self, username, password):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()
        return user is not None

    # -------------- USAGE STATS METHODS ----------------
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
        cursor = conn.cursor()
        cursor.execute("SELECT date, total_monitored, screen_time, active_time, updated_at FROM usage_stats")
        rows = cursor.fetchall()
        conn.close()
        return rows

if __name__ == "__main__":
    db_manager = DBManager()
    print(db_manager.read_all_stats())