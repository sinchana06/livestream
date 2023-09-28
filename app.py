from flask import Flask, Response, request, jsonify
from flask_pymongo import PyMongo
from bson import ObjectId
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


app = Flask(__name__)

# MongoDB configuration (replace with your MongoDB connection details)
app.config['MONGO_URI'] = 'mongodb://localhost:27017/livestream_app'
mongo = PyMongo(app)
overlay_settings = mongo.db.overlay_settings

# Enable CORS for specific origins (replace with your React frontend URL)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Replace this with the new video URL
video_url = 'http://archive.org/download/SampleMpeg4_201307/sample_mpeg4.mp4'

def generate_frames():
    cap = cv2.VideoCapture(video_url)  # Use the new video URL

    while True:
        success, frame = cap.read()
        if not success:
            break
        if overlay_settings.count_documents({}) > 0:
            frame = apply_overlays(frame)

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            break

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()

def apply_overlays(frame, overlay_settings):
    for overlay in overlay_settings:
        x = overlay['positionX']
        y = overlay['positionY']
        text = overlay['content']

        # Convert frame to RGB format (required for OpenCV)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_frame = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(pil_frame)

        # Define text properties (font, size, color, etc.)
        font = ImageFont.load_default()
        font_size = 20
        text_color = (255, 255, 255)

        # Position and render the text on the frame
        draw.text((x, y), text, font=font, fill=text_color)
        
        # Convert the image back to BGR format
        frame_rgb = np.array(pil_frame)
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        # Apply overlay on the frame
        frame = frame_bgr

    return frame

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/overlay-settings', methods=['GET', 'POST'])
def overlay_settings_api():
    if request.method == 'GET':
        settings = list(overlay_settings.find())
        # Convert ObjectId fields to strings in the response
        for setting in settings:
            setting['_id'] = str(setting['_id'])
        return jsonify(settings)
    elif request.method == 'POST':
        data = request.json
        overlay_id = overlay_settings.insert_one(data).inserted_id
        overlay = overlay_settings.find_one({'_id': overlay_id})
        # Convert ObjectId to string in the response
        overlay['_id'] = str(overlay['_id'])
        return jsonify(overlay), 201

@app.route('/api/overlay-settings/<string:id>', methods=['GET', 'PUT', 'DELETE'])
def overlay_settings_detail(id):
    overlay = overlay_settings.find_one({'_id': ObjectId(id)})

    if not overlay:
        return jsonify({'error': 'Overlay not found'}), 404

    if request.method == 'GET':
        # Convert ObjectId to string in the response
        overlay['_id'] = str(overlay['_id'])
        return jsonify(overlay)
    elif request.method == 'PUT':
        data = request.json
        overlay_settings.update_one({'_id': ObjectId(id)}, {'$set': data})
        return jsonify(data), 200
    elif request.method == 'DELETE':
        overlay_settings.delete_one({'_id': ObjectId(id)})
        return jsonify({'message': 'Overlay deleted'}), 204

@app.route('/api/apply-overlay-settings', methods=['POST'])   
def apply_overlay_settings():
    try:
        overlay_settings = list(mongo.db.overlay_settings.find())

        cap = cv2.VideoCapture(video_url)
        video_frames = []

        while True:
            success, frame = cap.read()
            if not success:
                break

            # Apply overlays to the frame
            frame = apply_overlays(frame, overlay_settings)
            video_frames.append(frame)

        cap.release()

        # Convert video frames to a video stream
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter('output.mp4', fourcc, 30, (frame.shape[1], frame.shape[0]))

        for frame in video_frames:
            out.write(frame)

        out.release()

        return jsonify({'message': 'Overlay settings applied successfully.'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

