# server.py
import os
from flask import Flask, request, jsonify

app = Flask(__name__)
UPLOAD_FOLDER = 'server_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        print(f"✅ Received and saved: {file.filename}")
        return jsonify({"message": f"File '{file.filename}' uploaded."}), 200

if __name__ == '__main__':
    print("✅ Server started. Listening at http://127.0.0.1:5000/upload")
    app.run(port=5000)