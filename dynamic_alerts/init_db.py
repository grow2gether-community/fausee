# init_db.py
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def initialize_database():
    """Connects to the DB and creates a simple logging table for evidence."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not found in .env file")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS video_evidence;")

    # NEW SCHEMA: A simple log. No more UNIQUE constraints or arrays.
    cur.execute("""
        CREATE TABLE video_evidence (
            id SERIAL PRIMARY KEY,
            alert_id UUID NOT NULL,
            video_filename VARCHAR(255) NOT NULL,
            uploaded_at TIMESTAMP NOT NULL
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized with simple evidence log table.")

if __name__ == "__main__":
    initialize_database()