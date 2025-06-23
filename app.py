import os
import uuid
import logging
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import yt_dlp

# Setup logging
LOG_FOLDER = 'logs'
os.makedirs(LOG_FOLDER, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_FOLDER, 'app.log')),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey')
socketio = SocketIO(app, cors_allowed_origins='*')
DOWNLOAD_FOLDER = 'static/audio'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        room_id = str(uuid.uuid4())[:8]
        session['room'] = room_id
        session['role'] = 'host'
        session['media_type'] = request.form['media_type']
        session['visibility'] = request.form['visibility']
        if session['visibility'] == 'private':
            session['password'] = request.form['password']
        return redirect(url_for('room', room_id=room_id))
    return render_template('create.html')

@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'POST':
        room = request.form['room_id']
        session['room'] = room
        session['role'] = 'player'
        session['name'] = request.form.get('name', '')
        # Check password if private room - skipping persistence for MVP
        return redirect(url_for('room', room_id=room))
    return render_template('join.html')

@app.route('/room/<room_id>')
def room(room_id):
    return render_template('room.html', room=room_id, role=session.get('role'), media_type=session.get('media_type'))

@app.route('/download')
def download():
    query = request.args.get('song')
    filename = f"{uuid.uuid4()}.mp3"
    output_path = os.path.join(DOWNLOAD_FOLDER, filename)
    url = f"ytsearch1:{query}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return jsonify({'url': f"/{output_path}"})
    except Exception as e:
        logging.error(f"yt-dlp failed: {e}")
        # fallback to youtube_dl
        try:
            import youtube_dl
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return jsonify({'url': f"/{output_path}"})
        except Exception as ex:
            logging.error(f"youtube_dl fallback failed: {ex}")
            return jsonify({'error': 'Download failed'}), 500

@socketio.on('join')
def on_join(data):
    room = data.get('room')
    join_room(room)
    logging.info(f"User joined room {room}")

@socketio.on('command')
def on_command(data):
    room = data.get('room')
    emit('command', data, room=room)

@socketio.on('end')
def on_end(data):
    room = data.get('room')
    emit('end', {}, room=room)
    # Optionally clear session or room data

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
