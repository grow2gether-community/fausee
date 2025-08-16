# import os
# import threading
# import tkinter as tk
# from tkinter import ttk, messagebox, simpledialog
# import webbrowser

# class PasswordDialog(simpledialog.Dialog):
#     def body(self, master):
#         tk.Label(master, text="Password:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
#         self.password_var = tk.StringVar()
#         self.password_entry = tk.Entry(master, textvariable=self.password_var, show="*")
#         self.password_entry.grid(row=0, column=1, padx=4, pady=4)
#         return self.password_entry  # initial focus

#     def apply(self):
#         self.result = self.password_var.get()

# class DashboardApp(tk.Tk):
#     def __init__(self, monitor_controller):
#         super().__init__()
#         self.title("Monitoring Dashboard")
#         self.configure(bg="#232946")
#         self.geometry("800x560")

#         self.controller = monitor_controller

#         # Tkinter style setup
#         style = ttk.Style(self)
#         style.theme_use('clam')
#         style.configure("Treeview",
#                         background="#eebbc3",
#                         foreground="#232946",
#                         fieldbackground="#eebbc3",
#                         font=('Segoe UI', 12))
#         style.configure("Treeview.Heading",
#                         font=('Segoe UI Bold', 13),
#                         background="#393c6a",
#                         foreground="#f2f2f2")
#         style.configure("TButton",
#                         font=('Segoe UI', 13),
#                         background="#eebbc3",
#                         foreground="#232946",
#                         borderwidth=0,
#                         focusthickness=1,
#                         focuscolor="#eebbc3")

#         # Usage stats table setup
#         self.tree = ttk.Treeview(self, columns=('Date', 'Total Monitored', 'Screen Time', 'Active Time', 'Updated At'),
#                                  show='headings', height=12)
#         for col in self.tree['columns']:
#             self.tree.heading(col, text=col)
#             self.tree.column(col, width=120, anchor=tk.CENTER)
#         self.tree.pack(pady=16, padx=20, fill=tk.BOTH, expand=True)

#         # Buttons
#         btn_frame = tk.Frame(self, bg="#232946")
#         btn_frame.pack(pady=10)
#         self.start_btn = ttk.Button(btn_frame, text="Start Monitoring", command=self.start_monitor)
#         self.stop_btn = ttk.Button(btn_frame, text="Stop Monitoring", command=self.stop_monitor)
#         self.refresh_btn = ttk.Button(btn_frame, text="Refresh Dashboard", command=self.load_data)
#         self.login_btn = ttk.Button(btn_frame, text="Open Login", command=self.open_login)
#         self.start_btn.grid(row=0, column=0, padx=10)
#         self.stop_btn.grid(row=0, column=1, padx=10)
#         self.refresh_btn.grid(row=0, column=2, padx=10)
#         self.login_btn.grid(row=0, column=3, padx=10)

#         # Status labels
#         self.status_var = tk.StringVar()
#         self.auth_var = tk.StringVar()
#         self.monitor_var = tk.StringVar()

#         self.status_label = tk.Label(self, textvariable=self.status_var, bg="#232946", fg="#eebbc3",
#                                      font=('Segoe UI', 11))
#         self.auth_label = tk.Label(self, textvariable=self.auth_var, bg="#232946", fg="#eebbc3",
#                                    font=('Segoe UI', 11))
#         self.monitor_label = tk.Label(self, textvariable=self.monitor_var, bg="#232946", fg="#eebbc3",
#                                       font=('Segoe UI', 11))
#         self.status_label.pack(pady=(4, 0))
#         self.auth_label.pack(pady=(2, 0))
#         self.monitor_label.pack(pady=(2, 10))

#         # Initial statuses
#         self.update_status_banners(analysis_phase=True)

#         # Load data initially
#         self.load_data()

#     # ---------- UI helpers ----------

#     def update_status_banners(self, analysis_phase=False):
#         auth = self.controller.authenticated
#         mon = self.controller.monitoring_active and not self.controller.face_manager.pause_recognition.is_set()

#         if not auth:
#             self.auth_var.set("Auth: Not authenticated — Authenticate to start monitoring.")
#         else:
#             self.auth_var.set("Auth: Authenticated (session).")

#         if mon:
#             self.monitor_var.set("Monitoring: ACTIVE (face recognition running).")
#         else:
#             self.monitor_var.set("Monitoring: INACTIVE. You are not being monitored currently.")

#         if analysis_phase:
#             self.status_var.set("Ready.")
#         else:
#             # Leave whatever the last action set.
#             pass

#     def open_login(self):
#         try:
#             webbrowser.open("http://127.0.0.1:5000/login")
#             messagebox.showinfo("Login", "Browser opened. Complete sign-in, then click OK.")
#             # Ask user to confirm login completion; set flag if yes
#             if messagebox.askyesno("Confirm", "Did you complete sign-in successfully?"):
#                 self.controller.set_authenticated(True)
#                 self.status_var.set("Signed in for this session.")
#             else:
#                 self.controller.set_authenticated(False)
#                 self.status_var.set("Sign-in not completed.")
#         finally:
#             self.update_status_banners()

#     # ---------- Data load ----------

#     def load_data(self):
#         def analyze_and_load():
#             self.status_var.set("Analyzing logs, please wait...")
#             try:
#                 self.controller.trigger_log_analysis_now()
#                 rows = self.controller.db_manager.read_all_stats()
#             except Exception as e:
#                 rows = []
#                 messagebox.showerror("Error", f"Failed to load stats: {e}")

#             def update_ui():
#                 for item in self.tree.get_children():
#                     self.tree.delete(item)
#                 for r in rows:
#                     def format_seconds(sec):
#                         try:
#                             sec = int(sec)
#                             h = sec // 3600
#                             m = (sec % 3600) // 60
#                             s = sec % 60
#                             return f"{h:02d}:{m:02d}:{s:02d}"
#                         except Exception:
#                             return sec

#                     date, total_monitored, screen_time, active_time, updated_at = r
#                     self.tree.insert('', 'end', values=(
#                         date,
#                         format_seconds(total_monitored),
#                         format_seconds(screen_time),
#                         format_seconds(active_time),
#                         updated_at or ""
#                     ))
#                 self.status_var.set("Dashboard refreshed.")
#                 self.update_status_banners()

#             self.after(0, update_ui)

#         threading.Thread(target=analyze_and_load, daemon=True).start()

#     # ---------- Start/Stop actions ----------

#     def start_monitor(self):
#         # If not authenticated -> guide user to login
#         if not self.controller.authenticated:
#             messagebox.showwarning(
#                 "Authenticate to start monitoring",
#                 "You must sign in before monitoring can start."
#             )
#             self.open_login()
#             if not self.controller.authenticated:
#                 # User still not authenticated; abort
#                 self.status_var.set("Start aborted: user not authenticated.")
#                 self.update_status_banners()
#                 return

#         # Ask consent to be monitored
#         if not messagebox.askyesno("Monitor", "Do you want to be monitored?"):
#             self.status_var.set("Monitoring not started.")
#             self.update_status_banners()
#             return

#         # Kick off recognition loop (controller handles ref embedding + resume)
#         def start_bg():
#             try:
#                 self.controller.start_recognition_loop()
#             except Exception as e:
#                 messagebox.showerror("Error", f"Failed to start recognition: {e}")
#                 return
#             self.status_var.set("Recognition monitoring started.")
#             self.update_status_banners()

#         threading.Thread(target=start_bg, daemon=True).start()

#     def stop_monitor(self):
#         dlg = PasswordDialog(self, title="Verify to Stop Monitoring")
#         if not dlg.result:
#             self.status_var.set("Stop cancelled.")
#             return
#         password = dlg.result
#         if not password:
#             messagebox.showerror("Error", "Password is required.")
#             return

#         ok = self.controller.verify_password_only(password)
#         if not ok:
#             messagebox.showerror("Error", "Invalid password. Monitoring continues.")
#             self.update_status_banners()
#             return

#         # Verified -> stop
#         self.controller.stop_recognition()
#         self.status_var.set("Monitoring stopped by user.")
#         messagebox.showinfo("Status", "Monitoring stopped.")
#         self.update_status_banners()

import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import webbrowser

class PasswordDialog(simpledialog.Dialog):
    def body(self, master):
        tk.Label(master, text="Password:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(master, textvariable=self.password_var, show="*")
        self.password_entry.grid(row=0, column=1, padx=4, pady=4)
        return self.password_entry

    def apply(self):
        self.result = self.password_var.get()

class DashboardApp(tk.Tk):
    def __init__(self, monitor_controller):
        super().__init__()
        self.title("Monitoring Dashboard")
        self.configure(bg="#232946")
        self.geometry("800x560")

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
                        borderwidth=0)

        # Usage stats table
        self.tree = ttk.Treeview(self, columns=('Date', 'Total Monitored', 'Screen Time', 'Active Time', 'Updated At'),
                                 show='headings', height=12)
        for col in self.tree['columns']:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor=tk.CENTER)
        self.tree.pack(pady=16, padx=20, fill=tk.BOTH, expand=True)

        # Buttons
        btn_frame = tk.Frame(self, bg="#232946")
        btn_frame.pack(pady=10)
        self.start_btn = ttk.Button(btn_frame, text="Start Monitoring", command=self.start_monitor)
        self.stop_btn = ttk.Button(btn_frame, text="Stop Monitoring", command=self.stop_monitor)
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh Dashboard", command=self.load_data)
        self.login_btn = ttk.Button(btn_frame, text="Open Login", command=self.open_login)
        self.start_btn.grid(row=0, column=0, padx=10)
        self.stop_btn.grid(row=0, column=1, padx=10)
        self.refresh_btn.grid(row=0, column=2, padx=10)
        self.login_btn.grid(row=0, column=3, padx=10)
        self.update_img_btn = ttk.Button(btn_frame, text="Update Reference Image", command=self.update_ref_image)
        self.update_img_btn.grid(row=0, column=4, padx=10)
        
        # Status labels
        self.status_var = tk.StringVar()
        self.auth_var = tk.StringVar()
        self.monitor_var = tk.StringVar()

        self.status_label = tk.Label(self, textvariable=self.status_var, bg="#232946", fg="#eebbc3",
                                     font=('Segoe UI', 11))
        self.auth_label = tk.Label(self, textvariable=self.auth_var, bg="#232946", fg="#eebbc3",
                                   font=('Segoe UI', 11))
        self.monitor_label = tk.Label(self, textvariable=self.monitor_var, bg="#232946", fg="#eebbc3",
                                      font=('Segoe UI', 11))
        self.status_label.pack(pady=(4, 0))
        self.auth_label.pack(pady=(2, 0))
        self.monitor_label.pack(pady=(2, 10))

        # Initial statuses
        self.update_status_banners()
        self.load_data()

    # ---------- UI helpers ----------

    def update_status_banners(self):
        auth = self.controller.refresh_auth_state()
        mon = self.controller.monitoring_active and not self.controller.face_manager.pause_recognition.is_set()

        if not auth:
            self.auth_var.set("Auth: Not authenticated — Authenticate to start monitoring.")
        else:
            self.auth_var.set("Auth: Authenticated.")

        if mon:
            self.monitor_var.set("Monitoring: ACTIVE (face recognition running).")
        else:
            self.monitor_var.set("Monitoring: INACTIVE. You are not being monitored.")

    def open_login(self):
        self.controller.start_auth_flow()
        messagebox.showinfo("Login", "Browser opened. Please complete sign-in in the browser.")
        # Wait for DB to contain a user
        def check_auth():
            if self.controller.refresh_auth_state():
                self.status_var.set("Signed in for this session.")
                self.update_status_banners()
            else:
                self.after(2000, check_auth)  # poll again in 2 sec
        self.after(2000, check_auth)

    # ---------- Data load ----------

    def load_data(self):
        def analyze_and_load():
            self.status_var.set("Analyzing logs...")
            try:
                self.controller.trigger_log_analysis_now()
                rows = self.controller.db_manager.read_all_stats()
            except Exception as e:
                rows = []
                messagebox.showerror("Error", f"Failed to load stats: {e}")

            def update_ui():
                for item in self.tree.get_children():
                    self.tree.delete(item)
                for r in rows:
                    date, total_monitored, screen_time, active_time, updated_at = r
                    self.tree.insert('', 'end', values=(date, total_monitored, screen_time, active_time, updated_at or ""))
                self.status_var.set("Dashboard refreshed.")
                self.update_status_banners()

            self.after(0, update_ui)

        threading.Thread(target=analyze_and_load, daemon=True).start()

    # ---------- Start/Stop actions ----------

    def start_monitor(self):
        if not self.controller.refresh_auth_state():
            messagebox.showwarning("Auth Required", "You must sign in before monitoring can start.")
            self.open_login()
            return

        # Pass self as the parent window
        self.controller.start_recognition_loop(parent_window=self)
        self.status_var.set("Recognition monitoring started.")
        self.update_status_banners()

    def stop_monitor(self):
        dlg = PasswordDialog(self, title="Verify to Stop Monitoring")
        if not dlg.result:
            self.status_var.set("Stop cancelled.")
            return
        password = dlg.result
        if not password:
            messagebox.showerror("Error", "Password is required.")
            return

        ok = self.controller.verify_password_only(password)
        if not ok:
            messagebox.showerror("Error", "Invalid password. Monitoring continues.")
            self.update_status_banners()
            return

        # Verified -> stop
        self.controller.stop_recognition()
        self.status_var.set("Monitoring stopped by user.")
        messagebox.showinfo("Status", "Monitoring stopped.")
        self.update_status_banners()

    def update_ref_image(self):
        # Pass self as the parent window
        self.controller.update_reference_image(parent_window=self)
        messagebox.showinfo("Success", "Reference image updated.")
        self.update_status_banners()