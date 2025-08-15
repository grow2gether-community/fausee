import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

class DashboardApp(tk.Tk):
    def __init__(self, monitor_controller):
        super().__init__()
        self.title("Monitoring Dashboard")
        self.configure(bg="#232946")
        self.geometry("700x500")

        self.controller = monitor_controller

        # Tkinter style setup
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure("Treeview",
                        background="#eebbc3",
                        foreground="#232946",
                        fieldbackground="#eebbc3",
                        font=('Segoe UI', 12))
        style.configure("Treeview.Heading",
                        font=('Segoe UI Bold', 13),
                        background="#393c6a",
                        foreground="#f2f2f2")
        style.configure("TButton",
                        font=('Segoe UI', 13),
                        background="#eebbc3",
                        foreground="#232946",
                        borderwidth=0,
                        focusthickness=1,
                        focuscolor="#eebbc3")

        # Usage stats table setup
        self.tree = ttk.Treeview(self, columns=('Date', 'Total Monitored', 'Screen Time', 'Active Time', 'Updated At'),
                                 show='headings', height=12)
        for col in self.tree['columns']:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor=tk.CENTER)
        self.tree.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)

        # Buttons
        btn_frame = tk.Frame(self, bg="#232946")
        btn_frame.pack(pady=10)
        self.start_btn = ttk.Button(btn_frame, text="Start Monitoring", command=self.start_monitor)
        self.stop_btn = ttk.Button(btn_frame, text="Stop Monitoring", command=self.stop_monitor)
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Dashboard", command=self.load_data)
        self.start_btn.grid(row=0, column=0, padx=10)
        self.stop_btn.grid(row=0, column=1, padx=10)
        self.refresh_btn.grid(row=0, column=2, padx=10)

        # Status label
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(self, textvariable=self.status_var, bg="#232946", fg="#eebbc3",
                                     font=('Segoe UI', 11))
        self.status_label.pack(pady=10)
        self.status_var.set("Ready.")

        # Load data initially
        self.load_data()

    def load_data(self):
        # Run log analyzer in background thread before loading data
        def analyze_and_load():
            self.status_var.set("Analyzing logs, please wait...")
            self.controller.trigger_log_analysis_now()  # This processes logs & updates DB
            # Now load updated DB stats
            rows = self.controller.db_manager.read_all_stats()

            # Must update UI elements on main thread via .after()
            def update_ui():
                for item in self.tree.get_children():
                    self.tree.delete(item)
                for r in rows:
                    def format_seconds(sec):
                        try:
                            sec = int(sec)
                            h = sec // 3600
                            m = (sec % 3600) // 60
                            s = sec % 60
                            return f"{h:02d}:{m:02d}:{s:02d}"
                        except Exception:
                            return sec

                    date, total_monitored, screen_time, active_time, updated_at = r
                    self.tree.insert('', 'end', values=(
                        date,
                        format_seconds(total_monitored),
                        format_seconds(screen_time),
                        format_seconds(active_time),
                        updated_at or ""
                    ))
                self.status_var.set("Dashboard refreshed.")

            self.after(0, update_ui)

        threading.Thread(target=analyze_and_load, daemon=True).start()

    def start_monitor(self):
        resp = messagebox.askyesno("Monitor", "Do you want to be monitored?")
        if resp:
            ref_embedding = self.controller.face_manager.ref_embedding
            if ref_embedding is None:
                messagebox.showerror("Error", "Reference embedding unavailable. Please capture your face image first.")
                self.status_var.set("Failed: No reference embedding.")
                return
            self.controller.face_manager.pause_recognition.clear()  # Clear pause before starting recognition loop
            threading.Thread(target=self.controller.start_recognition_loop, args=(ref_embedding,), daemon=True).start()
            self.status_var.set("Recognition monitoring started.")
            messagebox.showinfo("Status", "Recognition monitoring started.")
        else:
            self.controller.face_manager.pause_recognition.clear()  # Clear pause before starting monitor loop
            threading.Thread(target=self.controller.start_monitoring_loop, daemon=True).start()
            self.status_var.set("Generic monitoring started.")
            messagebox.showinfo("Status", "Generic monitoring started (alerts on any face).")

    def stop_monitor(self):
        self.controller.stop_monitoring()
        self.status_var.set("Monitoring stopped.")
        messagebox.showinfo("Status", "Monitoring stopped.")
