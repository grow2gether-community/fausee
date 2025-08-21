# controller_api.py
from flask import Blueprint, jsonify, request
from flask_cors import CORS

def create_controller_api(controller):
    api = Blueprint("controller_api", __name__)

    # Enable CORS for this blueprint
    CORS(api, resources={r"/api/*": {"origins": "*"}})

    @api.get("/api/status")
    def status():
        auth = controller.refresh_auth_state()
        mon = controller.monitoring_active and not controller.face_manager.pause_recognition.is_set()
        return jsonify({
            "authenticated": auth,
            "monitoring": mon
        })

    @api.post("/api/start")
    def start():
        mode = request.args.get("mode", "reference")  # "reference" or "presence"
        use_reference = (mode == "reference")
        controller.start_recognition_loop(parent_window=None, use_reference=use_reference)
        return jsonify({"ok": True, "mode": mode})

    @api.post("/api/stop")
    def stop():
        controller.stop_recognition()
        return jsonify({"ok": True})

    @api.post("/api/update-ref")
    def update_ref():
        # No parent window in headless mode; FaceRecognitionManager handles camera dialog itself
        controller.update_reference_image(parent_window=None)
        return jsonify({"ok": True})

    @api.get("/api/stats")
    def stats():
        filter_period = request.args.get("filter", "all")
        rows = controller.db_manager.read_all_stats(filter_period)
        data = []
        for r in rows:
            date, total_monitored, screen_time, active_time, updated_at = r
            data.append({
                "date": date,
                "total_monitored": int(total_monitored or 0),
                "screen_time": int(screen_time or 0),
                "active_time": int(active_time or 0),
                "updated_at": updated_at or ""
            })
        return jsonify({"rows": data})

    @api.post("/api/analyze-logs")
    def analyze_logs():
        """Triggers a manual, immediate log analysis."""
        controller.trigger_log_analysis_now()
        return jsonify({"ok": True})

    @api.get("/api/login-url")
    def login_url():
        # For web flow buttons
        return jsonify({"url": "http://127.0.0.1:5000/login"})

    return api