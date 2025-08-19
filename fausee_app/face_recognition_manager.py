import cv2
import time
import numpy as np
import ctypes
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import threading
from insightface.app import FaceAnalysis
import win32gui
import win32ts
import win32api
import sys
import os
from datetime import datetime
import tempfile

# Constants
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8

SIMILARITY_THRESHOLD = 0.5
FRAME_RESIZE = (640, 480)
DET_SIZE = (320, 320)
CAMERA_DOWNTIME_ALERT_INTERVAL = 30
CAMERA_RETRY_DELAY = 5
EMPLOYEE_RETRIES = 100
EMPLOYEE_RETRY_DELAY = 2
SUCCESS_RESTART_DELAY = 5

pause_recognition = threading.Event()
pause_recognition.clear()


class FaceRecognitionManager:
    def __init__(self, logger_manager, image_dir):
        self.logger = logger_manager
        self.app = self._init_face_model()
        self._remove_unneeded_models()
        self.pause_recognition = threading.Event()
        self.pause_recognition.clear()
        self.embedding_cache_path = os.path.join(tempfile.gettempdir(), "face_verifier.npy")
        self.image_dir = image_dir

        if os.path.exists(self.embedding_cache_path):
            try:
                os.remove(self.embedding_cache_path)
                self.logger.log_event("Cleaned old reference embedding cache on startup.")
            except Exception as e:
                self.logger.log_event(f"Failed to clean cache on startup: {e}", level="warning")

        self.ref_embedding = self.load_or_fetch_embedding()

    # ----------- Embedding bootstrap & caching -----------

    def load_or_fetch_embedding(self):
        embedding = self._fetch_embedding_from_local_image()
        if embedding is not None:
            try:
                np.save(self.embedding_cache_path, embedding)
                self.logger.log_event("Saved new reference embedding to cache.")
            except Exception as e:
                self.logger.log_event(f"Failed to save embedding cache. Error: {e}", level="warning")
        return embedding

    def ensure_reference_embedding(self):
        """Ensure we have a usable ref embedding."""
        if self.ref_embedding is not None:
            return self.ref_embedding

        image_path = os.path.join(self.image_dir, "user.jpg")
        if not os.path.exists(image_path):
            self.logger.log_event("No user.jpg found. Reference embedding not available.", level="warning")
            return None

        embedding = self._fetch_embedding_from_local_image()
        if embedding is not None:
            np.save(self.embedding_cache_path, embedding)
            self.ref_embedding = embedding
        return self.ref_embedding

    def capture_reference_image_interactive(self, parent=None):
        """
        Opens a modal Toplevel window to let user capture a webcam photo as reference.
        """
        if parent is None:
            root = tk.Tk()
        else:
            root = tk.Toplevel(parent)

        root.title("Capture Reference Image")
        root.transient(parent)
        root.grab_set()

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.logger.log_event("Camera not available for reference capture.", level="critical")
            messagebox.showerror("Camera Error", "Could not access the camera.", parent=root)
            root.destroy()
            return None

        panel = tk.Label(root)
        panel.pack(padx=10, pady=10)

        captured_frame = [None]
        preview_active = True

        def show_frame():
            if not preview_active:
                return
            ret, frame = cap.read()
            if ret:
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                panel.imgtk = imgtk
                panel.config(image=imgtk)
                captured_frame[0] = frame
            panel.after(30, show_frame)

        def close_window():
            nonlocal preview_active
            preview_active = False
            cap.release()
            root.destroy()
            if parent:
                parent.focus_set()

        def accept():
            if captured_frame[0] is not None:
                os.makedirs(self.image_dir, exist_ok=True)
                save_path = os.path.join(self.image_dir, "user.jpg")
                cv2.imwrite(save_path, captured_frame[0])
                self.logger.log_event(f"Reference image saved at {save_path}.")
                close_window()
            else:
                messagebox.showwarning("Warning", "No frame captured.", parent=root)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Accept", command=accept).grid(row=0, column=0, padx=10)
        tk.Button(btn_frame, text="Cancel", command=close_window).grid(row=0, column=1, padx=10)
        
        root.protocol("WM_DELETE_WINDOW", close_window)

        show_frame()
        root.wait_window()

        if os.path.exists(os.path.join(self.image_dir, "user.jpg")):
            return os.path.join(self.image_dir, "user.jpg")
        return None

    def update_reference_image(self, parent_window=None):
        """Force user to update reference image and recompute embedding."""
        image_path = self.capture_reference_image_interactive(parent_window)
        if image_path:
            embedding = self._fetch_embedding_from_local_image()
            if embedding is not None:
                np.save(self.embedding_cache_path, embedding)
                self.ref_embedding = embedding
                self.logger.log_event("Reference image updated and embedding recomputed.")

    def _fetch_embedding_from_local_image(self):
        image_path = os.path.join(self.image_dir, "user.jpg")
        if not os.path.exists(image_path):
            self.logger.log_event(f"Reference image not found at '{image_path}'", level="critical")
            return None

        img = cv2.imread(image_path)
        if img is None:
            self.logger.log_event("Failed to read reference image (invalid image).", level="critical")
            return None

        faces = self.app.get(img)
        if not faces:
            self.logger.log_event("No face detected in the reference image.", level="critical")
            return None

        ref_embed = faces[0].embedding
        normalized_embed = ref_embed / np.linalg.norm(ref_embed)
        self.logger.log_event("Successfully extracted reference face embedding from local image.")
        return normalized_embed

    # ----------- Model init / housekeeping -----------

    def _init_face_model(self):
        try:
            app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=0, det_size=DET_SIZE)
            return app
        except Exception as e:
            self.logger.log_event(f"FATAL: Failed to initialize FaceAnalysis model: {e}", level="critical")
            sys.exit(1)

    def _remove_unneeded_models(self):
        if 'landmark_3d_68' in self.app.models:
            self.app.models.pop('landmark_3d_68')
        print("Insightface models loaded:", self.app.models)

    # ----------- Session lock/unlock listener -----------

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_WTSSESSION_CHANGE:
            if wparam == WTS_SESSION_LOCK:
                self.logger.log_event("System locked")
                self.pause_recognition.set()
            elif wparam == WTS_SESSION_UNLOCK:
                self.logger.log_event("System unlocked")
                self.pause_recognition.clear()
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def start_session_event_listener(self):
        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "SessionChangeListener"
        wc.lpfnWndProc = self._wnd_proc
        class_atom = win32gui.RegisterClass(wc)
        hwnd = win32gui.CreateWindowEx(0, class_atom, "Session Change Listener", 0, 0, 0, 0, 0, 0, 0, hinst, None)
        win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
        win32gui.PumpMessages()

    # ----------- Camera helpers -----------

    def is_camera_accessible(self, device_index=0):
        self.logger.log_event(f"Checking camera accessibility on device {device_index}.")
        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            return False
        ret, _ = cap.read()
        cap.release()
        return ret

    def wait_for_camera(self):
        if self.is_camera_accessible():
            self.logger.log_event("Camera accessible again")
            return True

        downtime_start = time.time()
        next_alert_threshold = CAMERA_DOWNTIME_ALERT_INTERVAL
        self.logger.log_event("Camera inaccessible", level="warning")

        while True:
            time.sleep(CAMERA_RETRY_DELAY)
            if self.is_camera_accessible():
                total_downtime = time.time() - downtime_start
                self.logger.log_event("Camera accessible again")
                return True

            elapsed_time = time.time() - downtime_start
            if elapsed_time >= next_alert_threshold:
                self.logger.log_event(
                    f"Camera inaccessible for over {next_alert_threshold} seconds.",
                    level="warning"
                )
                next_alert_threshold += CAMERA_DOWNTIME_ALERT_INTERVAL

    # ----------- UI / matching helpers -----------

    def create_alert_window(self, text):
        win = tk.Tk()
        win.attributes('-fullscreen', True)
        win.attributes('-topmost', True)
        win.configure(bg='red')
        label = tk.Label(
            win,
            text=text,
            font=("Arial", 50),
            fg="white",
            bg="red"
        )
        label.pack(expand=True)
        win.update()
        return win

    def check_employee_in_frame(self, frame, ref_embed):
        if ref_embed is None:
            return False
        faces = self.app.get(frame)
        for face in faces:
            cur_embed = face.embedding / np.linalg.norm(face.embedding)
            similarity = np.dot(ref_embed, cur_embed)
            if similarity > SIMILARITY_THRESHOLD:
                return True
        return False

    @staticmethod
    def lock_system():
        ctypes.windll.user32.LockWorkStation()

    # ----------- Internal watch loop primitive -----------

    def _face_watch_loop(self,
                         condition_check_fn,
                         alert_text,
                         max_attempts,
                         success_action_fn,
                         failure_action_fn,
                         delay_seconds):
        alert_window = None

        while True:
            if self.pause_recognition.is_set():
                if alert_window:
                    try:
                        alert_window.destroy()
                    except Exception:
                        pass
                    alert_window = None
                time.sleep(1)
                continue

            # Wait for camera to be accessible before capture
            self.wait_for_camera()
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                time.sleep(delay_seconds)
                continue

            continuous_count = 0
            while continuous_count < max_attempts and not self.pause_recognition.is_set():
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue

                frame = cv2.resize(frame, FRAME_RESIZE)

                if condition_check_fn(frame):  # person not found
                    if alert_window is None:
                        alert_window = self.create_alert_window(text=alert_text)
                    continuous_count += 1
                    try:
                        alert_window.update()
                    except Exception:
                        alert_window = None
                else:  # person found
                    if alert_window:
                        try:
                            alert_window.destroy()
                        except Exception:
                            pass
                        alert_window = None
                    continuous_count = 0
                    success_action_fn()
                    break  # exit inner loop

            cap.release()

            if continuous_count >= max_attempts:
                if alert_window:
                    try:
                        alert_window.destroy()
                    except Exception:
                        pass
                    alert_window = None
                failure_action_fn()
                return True

            # sleep only when person found
            time.sleep(delay_seconds)

    # ----------- Public loops -----------

    def recognition_loop(self, ref_embed):
        alert_text = "Couldn't find employee in the frame!"
        while True:
            if self.pause_recognition.is_set():
                time.sleep(1)
                continue

            failed = self._face_watch_loop(
                condition_check_fn=lambda frame: not self.check_employee_in_frame(frame, ref_embed),
                alert_text=alert_text,
                max_attempts=EMPLOYEE_RETRIES,
                success_action_fn=lambda: None,
                failure_action_fn=lambda: None,
                delay_seconds=5  # 5s cycle when person is present
            )

            if failed:
                self.pause_recognition.set()
                self.logger.log_event("Employee not found after max retries. Locking system.", level="error")
                self.lock_system()

                while self.pause_recognition.is_set():
                    time.sleep(1)

    def monitor_loop(self):
        alert_text = "Unauthorized presence detected!"
        while True:
            if self.pause_recognition.is_set():
                time.sleep(1)
                continue

            _ = self._face_watch_loop(
                condition_check_fn=lambda frame: bool(self.app.get(frame)),
                alert_text=alert_text,
                max_attempts=EMPLOYEE_RETRIES,
                success_action_fn=lambda: None,
                failure_action_fn=lambda: self.lock_system(),
                delay_seconds=5
            )
