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
        self.protocol("WM_DELETE_WINDOW", self.on_close)
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

    # ---------- Utils ----------
    @staticmethod
    def format_seconds(seconds: int) -> str:
        """Convert seconds into hh:mm:ss format string."""
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:02}"

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
                    self.tree.insert(
                        '',
                        'end',
                        values=(
                            date,
                            self.format_seconds(int(total_monitored)),
                            self.format_seconds(int(screen_time)),
                            self.format_seconds(int(active_time)),
                            updated_at or ""
                        )
                    )
                self.status_var.set("Dashboard refreshed.")
                self.update_status_banners()

            self.after(0, update_ui)

        threading.Thread(target=analyze_and_load, daemon=True).start()

    # ---------- Start/Stop actions ----------
    # def start_monitor(self):
    #     if not self.controller.refresh_auth_state():
    #         messagebox.showwarning("Auth Required", "You must sign in before monitoring can start.")
    #         self.open_login()
    #         return

    #     # Pass self as the parent window
    #     self.controller.start_recognition_loop(parent_window=self)
    #     self.status_var.set("Recognition monitoring started.")
    #     self.update_status_banners()

    def start_monitor(self):
        if not self.controller.refresh_auth_state():
            messagebox.showwarning("Auth Required", "You must sign in before monitoring can start.")
            self.open_login()
            return

        # Ask user if they want to be monitored
        answer = messagebox.askyesno("Monitoring Choice", "Do you want to be monitored?")
        if answer:
            # Employee-specific monitoring
            self.controller.start_recognition_loop(parent_window=self, use_reference=True)
            self.status_var.set("Recognition monitoring (employee-specific) started.")
        else:
            # General monitoring
            self.controller.start_recognition_loop(parent_window=self, use_reference=False)
            self.status_var.set("General monitoring (any face presence) started.")

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

    def on_close(self):
        # Ensure monitoring is stopped cleanly
        if self.controller.monitoring_active:
            self.controller.stop_recognition()
            self.controller.logger_manager.log_event("Monitoring stopped by user (app closed).")
        self.destroy()
