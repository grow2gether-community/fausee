import cv2
import time
import numpy as np
import ctypes
import tkinter as tk
import threading
from insightface.app import FaceAnalysis
import logging
import win32gui
import win32ts
import win32api

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
# ---------------- CONFIG ----------------
SIMILARITY_THRESHOLD = 0.5
FRAME_RESIZE = (640, 480)
DET_SIZE = (320, 320)

CAMERA_ACCESS_RETRIES = 30
CAMERA_RETRY_DELAY = 5
EMPLOYEE_RETRIES = 100
EMPLOYEE_RETRY_DELAY = 2
SUCCESS_RESTART_DELAY = 5  # seconds to wait after successful verification

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename='face_verification.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ---------------- STATE FLAGS ----------------
pause_recognition = threading.Event()  # Controls whether recognition loop is paused
pause_recognition.clear()  # Start unpaused

# ---------------- INSIGHTFACE INIT ----------------
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=DET_SIZE)

# Load reference employee image
ref_img = cv2.imread("employee.jpg")
if ref_img is None:
    raise ValueError("Failed to load employee.jpg")
ref_faces = app.get(ref_img)
if not ref_faces:
    raise ValueError("No face detected in reference image")
ref_embed = ref_faces[0].embedding / np.linalg.norm(ref_faces[0].embedding)


def is_camera_accessible(device_index=0):
    cap = cv2.VideoCapture(device_index)

    if not cap.isOpened():
        print("Webcam could not be opened. It may be in use or unavailable.")
        return False

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print("Webcam opened, but failed to read a frame. It may be busy or blocked.")
        return False

    # Save the frame to verify it worked
    return True

def log_data(gain_time, lost_time, attempt):
    logging.info(f"Lost access to the camera for:{gain_time - lost_time}")

def create_alert_window():
    """Create fullscreen alert window."""
    win = tk.Tk()
    win.attributes('-fullscreen', True)
    win.attributes('-topmost', True)
    win.configure(bg='red')
    label = tk.Label(
        win,
        text="Couldn't find employee in the frame!",
        font=("Arial", 50),
        fg="white",
        bg="red"
    )
    label.pack(expand=True)
    win.update()
    return win

# ---------------- SESSION NOTIFICATION HANDLER ----------------
def wnd_proc(hwnd, msg, wparam, lparam):
    global pause_recognition
    if msg == WM_WTSSESSION_CHANGE:
        if wparam == WTS_SESSION_LOCK:
            logging.info("System locked — pausing face recognition.")
            pause_recognition.set()  # Pause loop
        elif wparam == WTS_SESSION_UNLOCK:
            logging.info("System unlocked — resuming face recognition.")
            pause_recognition.clear()  # Resume loop
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def session_event_listener():
    wc = win32gui.WNDCLASS()
    hinst = wc.hInstance = win32api.GetModuleHandle(None)
    wc.lpszClassName = "SessionChangeListener"
    wc.lpfnWndProc = wnd_proc
    class_atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindowEx(
        0, class_atom, "Session Change Listener",
        0, 0, 0, 0, 0,
        0, 0, hinst, None
    )

    # Register for lock/unlock notifications
    win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
    win32gui.PumpMessages()

def wait_for_camera():
    """Retry until camera is accessible"""
    # for attempt in range(CAMERA_ACCESS_RETRIES):
    attempt = 0
    interval_count = 1
    lost_time = time.time()
    while True:
        # startup_window = create_startup_window()
        current_time = time.time()
        if is_camera_accessible():
            # startup_window.destroy()
            log_data(current_time, lost_time, attempt)
            logging.info(f"Camera accessible. Retries: {attempt}")
            pass # send an alert to the admin about this
            return True
        if current_time - lost_time > 30*interval_count:
            log_data(current_time, lost_time, attempt)
            pass # send an alert to the admin about this
            interval_count += 1
        logging.info(f"Camera inaccessible. Retry {attempt}")
        print(f"Camera inaccessible. Retry {attempt}")
        attempt += 1
        time.sleep(CAMERA_RETRY_DELAY)

def check_employee_in_frame(frame):
    """Check if the employee is in the given frame."""
    faces = app.get(frame)
    for face in faces:
        cur_embed = face.embedding / np.linalg.norm(face.embedding)
        similarity = np.dot(ref_embed, cur_embed)
        if similarity > SIMILARITY_THRESHOLD:
            return True
    return False

def lock_system():
    """Lock the Windows system."""
    ctypes.windll.user32.LockWorkStation()

# ---------------- MAIN RECOGNITION LOOP ----------------
def recognition_loop():
    global pause_recognition
    while True:
        # Wait if paused
        if pause_recognition.is_set():
            time.sleep(1)
            continue

        if not wait_for_camera():
            continue

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            continue

        ret, frame = cap.read()
        if not ret or frame is None:
            cap.release()
            continue

        frame = cv2.resize(frame, FRAME_RESIZE)
        if check_employee_in_frame(frame):
            logging.info("Employee verified.")
            cap.release()
            time.sleep(SUCCESS_RESTART_DELAY)
            continue

        retry_count = 0
        alert_window = create_alert_window()
        while retry_count < EMPLOYEE_RETRIES and not pause_recognition.is_set():

            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                wait_for_camera()
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                continue

            frame = cv2.resize(frame, FRAME_RESIZE)
            if check_employee_in_frame(frame):
                alert_window.destroy()
                logging.info("Employee verified during retries.")
                break
            else:
                retry_count += 1
                alert_window.update()
                logging.warning(f"Employee not found (Attempt {retry_count}/{EMPLOYEE_RETRIES})")
                # time.sleep(EMPLOYEE_RETRY_DELAY)

        cap.release()

        if retry_count >= EMPLOYEE_RETRIES:
            logging.error("Employee not found — locking system.")
            alert_window.destroy()
            lock_system()
            pause_recognition.set()  # Will be cleared on unlock


# ---------------- ENTRY POINT ----------------
if __name__ == "__main__":
    # Start event listener in background
    threading.Thread(target=session_event_listener, daemon=True).start()
    logging.info("Starting continuous employee verification...")
    recognition_loop()


