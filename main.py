import os
import uuid
import subprocess
import threading
import glob
import time
from flask import Flask, request, render_template, send_file

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

# Cria pastas se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Função para limpar pastas após delay
def cleanup_folder(folder, delay_seconds=120):
    def worker():
        time.sleep(delay_seconds)
        files = glob.glob(os.path.join(folder, "*"))
        for f in files:
            try:
                os.remove(f)
            except Exception as e:
                print(f"Erro ao deletar {f}: {e}")
    threading.Thread(target=worker, daemon=True).start()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        image = request.files.get("image")
        video = request.files.get("video")

        if not image or not video:
            return "Por favor, envie uma imagem e um vídeo.", 400

        # Caminhos únicos
        image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{image.filename}")
        video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{video.filename}")
        image.save(image_path)
        video.save(video_path)

        # Nome final baseado na imagem
        output_filename = os.path.splitext(image.filename)[0] + ".mp4"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        # Ajusta imagem para vertical 1080x1920
        resized_image = os.path.join(UPLOAD_FOLDER, f"resized_{uuid.uuid4()}.png")
        resize_cmd = [
            "ffmpeg", "-y", "-i", image_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            resized_image
        ]
        subprocess.run(resize_cmd, check=True)

        # Extrai áudio do vídeo
        audio_file = os.path.join(UPLOAD_FOLDER, f"audio_{uuid.uuid4()}.aac")
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-c:a", "aac", audio_file], check=True)

        # Remove silêncio do início e do fim de forma confiável
        trimmed_audio = os.path.join(UPLOAD_FOLDER, f"trimmed_{uuid.uuid4()}.aac")
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_file,
            "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1:"
                   "stop_periods=-1:stop_threshold=-50dB:stop_silence=0.1",
            "-c:a", "aac", "-b:a", "320k",
            trimmed_audio
        ], check=True)

        # Normaliza áudio
        normalized_audio = os.path.join(UPLOAD_FOLDER, f"norm_{uuid.uuid4()}.aac")
        subprocess.run([
            "ffmpeg", "-y", "-i", trimmed_audio,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "320k",
            normalized_audio
        ], check=True)

        # Combina imagem + áudio em vídeo final
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", resized_image,
            "-i", normalized_audio,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            "-vf", "scale=1080:1920",
            output_path
        ], check=True)

        # Limpeza automática
        cleanup_folder(UPLOAD_FOLDER)
        cleanup_folder(OUTPUT_FOLDER)

        return render_template("download.html", filename=output_filename)

    return render_template("index.html")


@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
