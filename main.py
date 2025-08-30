import os
import uuid
import subprocess
from flask import Flask, request, render_template, send_file

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def trim_audio(input_path, output_path):
    """
    Corta silêncios do início e do fim do áudio usando ffmpeg.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af",
        "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.3:" +
        "stop_periods=1:stop_threshold=-50dB:stop_silence=0.3",
        "-c:a", "aac", "-b:a", "320k", output_path
    ]
    subprocess.run(cmd, check=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video_file = request.files.get("video")
        image_file = request.files.get("image")

        if not video_file or not image_file:
            return "Por favor, envie um vídeo e uma imagem.", 400

        # Salva arquivos
        video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{video_file.filename}")
        image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{image_file.filename}")
        video_file.save(video_path)
        image_file.save(image_path)

        # Extrai áudio
        audio_path = os.path.join(UPLOAD_FOLDER, f"audio_{uuid.uuid4()}.aac")
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-c:a", "aac", "-b:a", "320k", audio_path
        ], check=True)

        # Corta silêncios
        trimmed_audio_path = os.path.join(UPLOAD_FOLDER, f"trimmed_{uuid.uuid4()}.aac")
        trim_audio(audio_path, trimmed_audio_path)

        # Cria vídeo final (imagem + áudio)
        output_filename = f"{os.path.splitext(image_file.filename)[0]}.mp4"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-i", trimmed_audio_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            "-vf", "scale=1080:1920",
            output_path
        ], check=True)

        return render_template("download.html", filename=output_filename)

    return render_template("index.html")


@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
