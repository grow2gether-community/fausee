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
import sys
import os
from datetime import datetime
import tempfile

# Constants (keep your original configuration values)
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

pause_recognition = threading.Event()  # To pause recognition on lock
pause_recognition.clear()  # Start unpaused

class FaceRecognitionManager:
    def __init__(self, logger_manager, image_dir):
        self.logger = logger_manager
        self.app = self._init_face_model()
        self._remove_unneeded_models()
        self.pause_recognition = threading.Event()
        self.pause_recognition.clear()
        self.embedding_cache_path = os.path.join(tempfile.gettempdir(), "face_verifier.npy")
        self.ref_embedding = self.load_or_fetch_embedding()
        self.image_dir = image_dir
    def load_or_fetch_embedding(self):
        # Try load cached embedding
        if os.path.exists(self.embedding_cache_path):
            try:
                self.logger.log_event("Loading reference embedding from cache.")
                emb = np.load(self.embedding_cache_path)
                if emb is not None and emb.size > 0:
                    return emb
            except Exception as e:
                self.logger.log_event(f"Failed to load embedding cache, will fetch fresh. Error: {e}", level="error")

        # Cache miss: fetch from local image, calculate embedding
        embedding = self._fetch_embedding_from_local_image()

        # Save to cache
        if embedding is not None:
            try:
                np.save(self.embedding_cache_path, embedding)
                self.logger.log_event("Saved new reference embedding to cache.")
            except Exception as e:
                self.logger.log_event(f"Failed to save embedding cache. Error: {e}", level="warning")

        return embedding

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

    def _init_face_model(self):
        try:
            app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
            app.prepare(ctx_id=0, det_size=DET_SIZE)
            return app
        except Exception as e:
            self.logger.log_event(f"FATAL: Failed to initialize FaceAnalysis model: {e}", level="critical")
            sys.exit(1)

    def _remove_unneeded_models(self):
        # Remove landmark_3d_68 if present
        if 'landmark_3d_68' in self.app.models:
            self.app.models.pop('landmark_3d_68')
        print("Insightface models loaded:", self.app.models)

    # Session lock/unlock handler
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_WTSSESSION_CHANGE:
            if wparam == WTS_SESSION_LOCK:
                self.logger.log_event("System locked, pausing face recognition.")
                self.pause_recognition.set()
            elif wparam == WTS_SESSION_UNLOCK:
                self.logger.log_event("System unlocked, resuming face recognition.")
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

    @staticmethod
    def is_camera_accessible(device_index=0):
        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            return False
        ret, _ = cap.read()
        cap.release()
        return ret

    def wait_for_camera(self):
        if self.is_camera_accessible():
            self.logger.log_event("Camera is accessible.")
            return True

        downtime_start = time.time()
        next_alert_threshold = CAMERA_DOWNTIME_ALERT_INTERVAL
        self.logger.log_event("Camera inaccessible. Waiting...", level="warning")

        while True:
            time.sleep(CAMERA_RETRY_DELAY)
            if self.is_camera_accessible():
                total_downtime = time.time() - downtime_start
                self.logger.log_event(f"Camera became accessible after {total_downtime:.2f} seconds.")
                return True

            elapsed_time = time.time() - downtime_start
            if elapsed_time >= next_alert_threshold:
                self.logger.log_event(
                    f"Camera has been inaccessible for over {next_alert_threshold} seconds. (Admin alert placeholder)",
                    level="warning"
                )
                next_alert_threshold += CAMERA_DOWNTIME_ALERT_INTERVAL

    def create_alert_window(self):
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

    def recognition_loop(self, ref_embed):
        while True:
            if self.pause_recognition.is_set():
                time.sleep(1)
                continue
            self.wait_for_camera()
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                continue
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                continue
            frame = cv2.resize(frame, FRAME_RESIZE)
            if self.check_employee_in_frame(frame, ref_embed):
                self.logger.log_event("Employee verified.")
                cap.release()
                time.sleep(SUCCESS_RESTART_DELAY)
                continue
            retry_count = 0
            self.logger.log_event("Employee not detected. Starting verification retries.", level="warning")
            alert_window = self.create_alert_window()
            while retry_count < EMPLOYEE_RETRIES and not self.pause_recognition.is_set():
                ret, frame = cap.read()
                if not ret or frame is None:
                    cap.release()
                    self.wait_for_camera()
                    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                    continue
                frame = cv2.resize(frame, FRAME_RESIZE)
                if self.check_employee_in_frame(frame, ref_embed):
                    self.logger.log_event("Employee verified during retries.")
                    alert_window.destroy()
                    break
                else:
                    retry_count += 1
                    alert_window.update()
                    self.logger.log_event(f"Employee not found (Attempt {retry_count}/{EMPLOYEE_RETRIES})", level="warning")
            cap.release()
            if retry_count >= EMPLOYEE_RETRIES:
                alert_window.destroy()
                self.logger.log_event("Employee not found after max retries. Locking system.", level="error")
                self.lock_system()
                self.pause_recognition.set()
