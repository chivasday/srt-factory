from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
import whisper
import os
import uuid
import time
import json
from pathlib import Path
import threading
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super-secret-key-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SRT_FOLDER'] = 'srt_output'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

# Buat folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SRT_FOLDER'], exist_ok=True)

# Global status
tasks = {}

class SRTProcessor:
    def __init__(self):
        self.model = None
    
    def load_model(self):
        if self.model is None:
            print("🔄 Loading Whisper model (medium)...")
            self.model = whisper.load_model("medium")
            print("✅ Model ready!")
    
    def process(self, video_path, task_id):
        try:
            tasks[task_id]['status'] = 'processing'
            tasks[task_id]['progress'] = 10
            
            # Load model jika belum
            self.load_model()
            
            tasks[task_id]['progress'] = 30
            result = self.processor.transcribe(
                video_path, 
                language="id", 
                task="transcribe",
                verbose=False
            )
            
            tasks[task_id]['progress'] = 70
            
            # Generate SRT
            srt_path = video_path.rsplit('.', 1)[0] + '.srt'
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(result['segments']):
                    start = segment['start']
                    end = segment['end']
                    text = segment['text'].strip()
                    
                    f.write(f"{i+1}\n")
                    f.write(f"{self.format_time(start)} --> {self.format_time(end)}\n")
                    f.write(f"{text}\n\n")
            
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['srt_path'] = srt_path
            tasks[task_id]['progress'] = 100
            
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)
    
    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

processor = SRTProcessor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file:
        # Generate unique ID
        task_id = str(uuid.uuid4())
        filename = f"{task_id}_{file.filename}"
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        file.save(video_path)
        
        # Simpan task info
        tasks[task_id] = {
            'filename': file.filename,
            'video_path': video_path,
            'status': 'queued',
            'progress': 0,
            'started_at': datetime.now().isoformat()
        }
        
        # Start processing di background
        thread = threading.Thread(
            target=processor.process, 
            args=(video_path, task_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'task_id': task_id, 'message': 'Processing started!'})

@app.route('/status/<task_id>')
def status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify(task)

@app.route('/download/<task_id>')
def download(task_id):
    task = tasks.get(task_id)
    if not task or task['status'] != 'completed':
        flash('SRT belum selesai diproses!')
        return redirect(url_for('index'))
    
    return send_file(task['srt_path'], as_attachment=True)

@app.route('/tasks')
def list_tasks():
    return jsonify(tasks)

if __name__ == '__main__':
    print("🚀 SRT Factory starting on http://localhost:5000")
    print("💪 VPS EPYC 64-core ready! Max speed mode!")
    app.run(host='0.0.0.0', port=5000, debug=True)
