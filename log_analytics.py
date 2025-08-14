# import os
# import re
# import time
# from datetime import datetime, timedelta
# from typing import TypedDict, List, Tuple, Optional, Dict
# from dotenv import load_dotenv
# import pyreadline3
# from pydantic import BaseModel, Field
# # SQLAlchemy imports for PostgreSQL
# from sqlalchemy import create_engine, text

# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.tools import tool
# from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode

# # --- 1. Agent State & Helper Classes ---

# class LogAnalysisState(TypedDict):
#     """Defines the data structure for the workflow."""
#     files_to_process: List[str]
#     username: Optional[str] = 'subba'
#     log_date: Optional[str]
#     daily_summary: Dict[str, int]
#     analysis_result: dict

# class DatabaseManager:
#     """Handles all interactions with a PostgreSQL database."""
#     def __init__(self):
#         self.database_url = os.getenv("DATABASE_URL")
#         if not self.database_url:
#             raise ValueError("DATABASE_URL not found in .env file. Please set it.")
        
#         self.engine = create_engine(self.database_url)
#         self._setup_database()

#     def _setup_database(self):
#         """Initializes the database and table if they don't exist."""
#         try:
#             with self.engine.connect() as conn:
#                 conn.execute(text("""
#                 CREATE TABLE IF NOT EXISTS daily_summary (
#                     id SERIAL PRIMARY KEY,
#                     username VARCHAR(255) NOT NULL,
#                     log_date DATE NOT NULL,
#                     total_lock_seconds INTEGER,
#                     total_inaccessible_seconds INTEGER,
#                     total_active_seconds INTEGER,
#                     UNIQUE(username, log_date)
#                 )
#                 """))
#                 conn.commit()
#             print("✅ PostgreSQL Database is ready.")
#         except Exception as e:
#             print(f"❌ Failed to connect or setup PostgreSQL database: {e}")
#             raise

#     def save_summary(self, summary: dict):
#         """Saves a summary record using an 'upsert' (INSERT ON CONFLICT) for PostgreSQL."""
#         try:
#             with self.engine.connect() as conn:
#                 # This is the standard "upsert" syntax for PostgreSQL
#                 upsert_sql = text("""
#                 INSERT INTO daily_summary 
#                 (username, log_date, total_lock_seconds, total_inaccessible_seconds, total_active_seconds)
#                 VALUES (:username, :log_date, :total_lock_seconds, :total_inaccessible_seconds, :total_active_seconds)
#                 ON CONFLICT (username, log_date) 
#                 DO UPDATE SET
#                     total_lock_seconds = EXCLUDED.total_lock_seconds,
#                     total_inaccessible_seconds = EXCLUDED.total_inaccessible_seconds,
#                     total_active_seconds = EXCLUDED.total_active_seconds;
#                 """)
#                 conn.execute(upsert_sql, parameters=summary)
#                 conn.commit()
#             print(f"✅ Record for {summary['username']} on {summary['log_date']} saved to PostgreSQL.")
#         except Exception as e:
#             print(f"❌ PostgreSQL database error: {e}")

# # --- 2. The Decorated Tool (Unchanged) ---
# class Event(BaseModel):
#     """Represents a single event with a type, start time, and end time."""
#     event_type: str = Field(description="The type of event, must be 'lockdown', 'inaccessible', or 'session'.")
#     start_time: str = Field(description="The start time of the event in HH:MM:SS,ms format.")
#     end_time: str = Field(description="The end time of the event in HH:MM:SS,ms format.")

# def _calculate_seconds_diff(start_str: str, end_str: str) -> int:
#     try:
#         time_format = "%H:%M:%S"
#         start = datetime.strptime(start_str.split(',')[0], time_format)
#         end = datetime.strptime(end_str.split(',')[0], time_format)
#         if end < start: end += timedelta(days=1)
#         return int((end - start).total_seconds())
#     except (ValueError, TypeError): return 0

# @tool
# def get_event_durations(events: List[Event]) -> Dict[str, int]:
#     """
#     Calculates the total duration in seconds for each event type from a list of Event objects.
#     """
#     summary = {"lockdown": 0, "inaccessible": 0, "session": 0}
#     session_starts, session_ends = [], []

#     for event_type, start_time, end_time in events:
#         if event_type == "session":
#             session_starts.append(start_time)
#             session_ends.append(end_time)
#         else:
#             duration = _calculate_seconds_diff(start_time, end_time)
#             if event_type in summary:
#                 summary[event_type] += duration

#     if session_starts and session_ends:
#         summary["session"] = _calculate_seconds_diff(min(session_starts), max(session_ends))

#     return summary

# # --- 3. The Main Agent Class ---

# class DailyLogAnalyzerAgent:
#     def __init__(self):
#         load_dotenv()
#         self.db_manager = DatabaseManager()
#         self.graph = self._build_graph()

#     def _build_graph(self) -> StateGraph:
#         workflow = StateGraph(LogAnalysisState)
#         workflow.add_node("process_next_file", self._process_file_node)
#         tool_node = ToolNode([get_event_durations])
#         workflow.add_node("calculate_durations", tool_node)
#         workflow.add_node("save_to_db", self._save_to_db_node)
#         workflow.set_entry_point("process_next_file")
#         workflow.add_edge("process_next_file", "calculate_durations")
#         workflow.add_conditional_edges(
#             "calculate_durations",
#             self._check_if_more_files,
#             {"continue": "process_next_file", "end": "save_to_db"}
#         )
#         workflow.add_edge("save_to_db", END)
#         return workflow.compile()

#     def _process_file_node(self, state: LogAnalysisState) -> LogAnalysisState:
#         file_path = state["files_to_process"].pop(0)
#         print(f"\n--- Processing file: {os.path.basename(file_path)} ---")
#         with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
#         llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
#         llm_with_tools = llm.bind_tools([get_event_durations])
#         prompt = f"""Analyze the log content below. Based on the content, call the `get_event_durations` tool with the appropriate arguments. The valid event_types are "lockdown", "inaccessible", and "session". For "lockdown", find every pair of "System locked" and "System unlocked" messages. For "inaccessible", find every pair of "Camera inaccessible" and "Camera became accessible". For "session", find the timestamp of the very first log entry and the very last log entry in this file.
#         LOG CONTENT:
#         ---
#         {content}
#         ---"""
#         try:
#             ai_message = llm_with_tools.invoke(prompt)
#             state["analysis_result"] = ai_message.tool_calls[0]['args']
#             print(f"✅ LLM prepared tool call for {len(state['analysis_result'].get('events', []))} events.")
#         except Exception as e:
#             print(f"❌ LLM Error: {e}")
#             state["analysis_result"] = {"events": []}
#         return state

#     def _check_if_more_files(self, state: LogAnalysisState) -> str:
#         last_file_summary = state["analysis_result"][0]['tool_output']
#         state["daily_summary"]["lockdown"] += last_file_summary.get("lockdown", 0)
#         state["daily_summary"]["inaccessible"] += last_file_summary.get("inaccessible", 0)
#         state["daily_summary"]["session"] += last_file_summary.get("session", 0)
#         print("📊 Accumulated Totals:", state["daily_summary"])
#         return "continue" if state["files_to_process"] else "end"

#     def _save_to_db_node(self, state: LogAnalysisState) -> LogAnalysisState:
#         summary = state["daily_summary"]
#         active_time = max(0, summary["session"] - (summary["lockdown"] + summary["inaccessible"]))
#         db_record = {
#             "username": state["username"],
#             "log_date": state["log_date"],
#             "total_lock_seconds": summary["lockdown"],
#             "total_inaccessible_seconds": summary["inaccessible"],
#             "total_active_seconds": active_time
#         }
#         self.db_manager.save_summary(db_record)
#         return state

#     def run(self, file_paths: List[str]):
#         if not file_paths:
#             print("No files provided to process.")
#             return
#         print(file_paths)
#         breakpoint()
#         username, log_date = "unknown", datetime.now().strftime('%Y-%m-%d')
#         with open(file_paths[0], 'r', encoding='utf-8') as f: content = f.read()
#         if match := re.search(r"Loading embedding for '(\w+)'", content): username = match.group(1)
#         if date_match := re.search(r"(\d{4}-\d{2}-\d{2})", content): log_date = date_match.group(1)
#         initial_state = {
#             "files_to_process": file_paths,
#             "daily_summary": {"lockdown": 0, "inaccessible": 0, "session": 0},
#             "username": username,
#             "log_date": log_date,
#         }
#         print(initial_state)
#         print(f"🚀 Starting analysis for user '{username}' on date '{log_date}'.")
#         self.graph.invoke(initial_state)

# # --- 4. Main Execution Block ---
# if __name__ == "__main__":
#     agent = DailyLogAnalyzerAgent()
#     LOG_DIR = "C:/ProgramData/FaceVerificationApp/Logs"
#     file_paths = ['"C:\ProgramData\FaceVerificationApp\Logs\log_2025-08-12_15-43-25.log"']
#     # for file in os.listdir(LOG_DIR):
#     #     if file.startswith("log_2025-08-12"):
#     #         file_paths.append(os.path.join(LOG_DIR, file))
#     print(type(file_paths))
#     agent.run(file_paths=file_paths)
    

import os
import re
from datetime import datetime, timedelta
from typing import List, Dict

# =======================
# CONFIG
# =======================
LOG_DIR = r"C:\ProgramData\FaceVerificationApp\Logs"
LOG_FILE_PREFIX = "log_"  # All log files start with this
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Regex patterns for event detection
EVENT_PATTERNS = {
    "lockdown_start": re.compile(r"System locked", re.IGNORECASE),
    "lockdown_end": re.compile(r"System unlocked", re.IGNORECASE),
    "cam_inaccessible_start": re.compile(r"Camera inaccessible", re.IGNORECASE),
    "cam_inaccessible_end": re.compile(r"Camera became accessible", re.IGNORECASE),
    "session_start": re.compile(r"Start session tracking", re.IGNORECASE),
    "session_end": re.compile(r"End session tracking", re.IGNORECASE),
}

# Timestamp regex
TIMESTAMP_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

# =======================
# Helper Functions
# =======================

def parse_logs(file_path: str) -> List[Dict]:
    """
    Parses a single log file into a structured list of events with timestamps.
    """
    events = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as log_file:
        for line in log_file:
            ts_match = TIMESTAMP_REGEX.match(line)
            if not ts_match:
                continue

            timestamp = datetime.strptime(ts_match.group(1), TIME_FORMAT)

            for event_key, pattern in EVENT_PATTERNS.items():
                if pattern.search(line):
                    events.append({"event_key": event_key, "timestamp": timestamp})
                    break
    return events


def calculate_durations(events: List[Dict]) -> Dict[str, int]:
    """
    Calculates total seconds for lockdown, inaccessible, and session.
    """
    durations = {"lockdown": 0, "inaccessible": 0, "session": 0}

    # State tracking
    lockdown_start = cam_inaccessible_start = session_start = None
    session_min_start = session_max_end = None

    for event in events:
        key = event["event_key"]
        ts = event["timestamp"]

        if key == "lockdown_start":
            lockdown_start = ts
        elif key == "lockdown_end" and lockdown_start:
            durations["lockdown"] += (ts - lockdown_start).total_seconds()
            lockdown_start = None

        elif key == "cam_inaccessible_start":
            cam_inaccessible_start = ts
        elif key == "cam_inaccessible_end" and cam_inaccessible_start:
            durations["inaccessible"] += (ts - cam_inaccessible_start).total_seconds()
            cam_inaccessible_start = None

        elif key == "session_start":
            session_start = ts
            if not session_min_start or ts < session_min_start:
                session_min_start = ts
        elif key == "session_end" and session_start:
            session_max_end = ts
            session_start = None

    # Session total is from earliest start to latest end
    if session_min_start and session_max_end:
        durations["session"] = (session_max_end - session_min_start).total_seconds()

    return {k: int(v) for k, v in durations.items()}


def summarize_all_logs(log_dir: str) -> Dict[str, int]:
    """
    Aggregates durations for all matching log files in the directory.
    """
    total_summary = {"lockdown": 0, "inaccessible": 0, "session": 0}

    log_files = [
        os.path.join(log_dir, f)
        for f in os.listdir(log_dir)
        if f.startswith(LOG_FILE_PREFIX) and f.endswith(".log")
    ]

    for log_file in log_files:
        events = parse_logs(log_file)
        file_summary = calculate_durations(events)
        for k in total_summary:
            total_summary[k] += file_summary[k]

    return {k: int(v) for k, v in total_summary.items()}


def format_duration(seconds: int) -> str:
    """Converts seconds into HH:MM:SS format."""
    return str(timedelta(seconds=seconds))


# =======================
# MAIN EXECUTION
# =======================
if __name__ == "__main__":
    print("📂 Analyzing logs in:", LOG_DIR)
    summary = summarize_all_logs(LOG_DIR)

    print("\n📊 Final Summary Across All Files:")
    for k, secs in summary.items():
        print(f"{k.capitalize():<12}: {format_duration(secs)} ({secs} sec)")
