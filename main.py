import os
import uuid
import subprocess
from flask import Flask, request, render_template, send_file, redirect, url_for

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Função para rodar comando ffmpeg e capturar erros
def run_ffmpeg(cmd):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Erro no ffmpeg: {result.stderr}")
    return result

# Remove silêncios do início e fim do áudio
def trim_audio(input_audio, output_audio):
    cmd = [
        "ffmpeg", "-y", "-i", input_audio,
        "-af", "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.5:stop_periods=1:stop_threshold=-40dB:stop_silence=0.5",
        "-c:a", "aac", "-b:a", "320k",
        output_audio
    ]
    run_ffmpeg(cmd)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        image = request.files.get("image")
        video = request.files.get("video")

        if not image or not video:
            return "Por favor, envie uma imagem e um vídeo.", 400

        # Caminhos de upload
        image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{image.filename}")
        video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{video.filename}")

        image.save(image_path)
        video.save(video_path)

        # Nome final baseado na imagem
        final_filename = f"{os.path.splitext(image.filename)[0]}.mp4"
        output_path = os.path.join(OUTPUT_FOLDER, final_filename)

        # Ajusta imagem para 1080x1920
        resized_image = os.path.join(UPLOAD_FOLDER, f"resized_{uuid.uuid4()}.png")
        run_ffmpeg([
            "ffmpeg", "-y", "-i", image_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            resized_image
        ])

        # Extrai áudio do vídeo
        audio_file = os.path.join(UPLOAD_FOLDER, f"audio_{uuid.uuid4()}.aac")
        run_ffmpeg([
            "ffmpeg", "-y", "-i", video_path, "-vn",
            "-c:a", "aac", audio_file
        ])

        # Remove silêncios
        trimmed_audio = os.path.join(UPLOAD_FOLDER, f"trimmed_{uuid.uuid4()}.aac")
        trim_audio(audio_file, trimmed_audio)

        # Combina imagem + áudio
        run_ffmpeg([
            "ffmpeg", "-y", "-loop", "1", "-i", resized_image,
            "-i", trimmed_audio,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            output_path
        ])

        return render_template("download.html", filename=final_filename)

    return render_template("index.html")


@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
