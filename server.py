from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# The folder where uploaded files will be stored
UPLOAD_FOLDER = 'uploads_from_client'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_file():
    """Endpoint to receive and save a video file."""
    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']

    # If the user does not select a file, the browser submits an empty file without a filename.
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        # Save the file to the server's upload folder
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        print(f"✅ File saved successfully: {file.filename}")
        
        return jsonify({
            "message": f"File '{file.filename}' uploaded successfully.",
            "filepath": filepath
        }), 200

if __name__ == '__main__':
    # Runs the server on http://127.0.0.1:5000
    app.run(debug=True, port=5000)