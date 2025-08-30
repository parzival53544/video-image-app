import os
import uuid
import subprocess
from flask import Flask, request, render_template, send_file

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

# Cria pastas se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        image = request.files.get("image")
        video = request.files.get("video")

        if not image or not video:
            return "Por favor, envie uma imagem e um vídeo.", 400

        # Nomes únicos
        image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{image.filename}")
        video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{video.filename}")
        output_name = os.path.splitext(image.filename)[0] + ".mp4"
        output_path = os.path.join(OUTPUT_FOLDER, output_name)

        image.save(image_path)
        video.save(video_path)

        # Extrai áudio do vídeo
        audio_path = os.path.join(UPLOAD_FOLDER, f"audio_{uuid.uuid4()}.aac")
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path, "-vn", "-c:a", "aac", audio_path
        ], check=True)

        # Ajusta imagem para vertical 1080x1920 sem esticar
        resized_image = os.path.join(UPLOAD_FOLDER, f"resized_{uuid.uuid4()}.png")
        subprocess.run([
            "ffmpeg", "-y", "-i", image_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            resized_image
        ], check=True)

        # Combina imagem + áudio em vídeo final
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", resized_image,
            "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            output_path
        ], check=True)

        return render_template("download.html", filename=output_name)

    return render_template("index.html")


@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
