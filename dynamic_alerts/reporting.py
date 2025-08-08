# reporting.py
import os
import psycopg2
from dotenv import load_dotenv

def get_db_connection():
    """Establishes and returns a database connection using the .env file."""
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not found in .env file")
    return psycopg2.connect(db_url)

def generate_report():
    """Queries the database and prints a report on video evidence."""
    print("Connecting to database to generate report...")
    conn = get_db_connection()
    with conn.cursor() as cur:
        # This query groups the simple log data to find the most critical videos
        report_query = """
            SELECT
                video_filename,
                COUNT(alert_id) as alert_count,
                ARRAY_AGG(alert_id) as associated_alert_ids
            FROM
                video_evidence
            GROUP BY
                video_filename
            ORDER BY
                alert_count DESC;
        """
        cur.execute(report_query)
        results = cur.fetchall()
        
        print("\n--- Video Evidence Criticality Report ---")
        if not results:
            print("No evidence has been logged in the database yet.")
            return

        for row in results:
            filename, count, alert_ids = row
            print(f"\n📹 Video: {filename}")
            print(f"   - Serves as evidence for: {count} alert(s)")
            print(f"   - Associated Alert IDs:")
            for alert_id in alert_ids:
                print(f"     - {alert_id}")
            
    conn.close()
    print("\n--- Report Complete ---")

if __name__ == "__main__":
    generate_report()