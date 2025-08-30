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


def run_cmd(cmd):
    """Executa comando FFmpeg e lança erro se falhar"""
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Erro FFmpeg: {proc.stderr}")
    return proc.stdout


def remove_silence(input_audio, output_audio):
    """Remove silêncio do início e fim do áudio"""
    cmd = [
        "ffmpeg", "-y", "-i", input_audio,
        "-af",
        "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.3:"\
        "stop_periods=1:stop_threshold=-50dB:stop_silence=0.3",
        "-c:a", "aac", "-b:a", "320k",
        output_audio
    ]
    run_cmd(cmd)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video_file = request.files.get("video")
        image_file = request.files.get("image")

        if not video_file or not image_file:
            return "Por favor, envie um vídeo e uma imagem.", 400

        # Nomes únicos
        video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{video_file.filename}")
        image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{image_file.filename}")
        output_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(image_file.filename)[0]}.mp4")
        trimmed_audio_path = os.path.join(UPLOAD_FOLDER, f"trimmed_{uuid.uuid4()}.aac")

        video_file.save(video_path)
        image_file.save(image_path)

        # Extrai áudio do vídeo
        audio_path = os.path.join(UPLOAD_FOLDER, f"audio_{uuid.uuid4()}.aac")
        run_cmd(["ffmpeg", "-y", "-i", video_path, "-vn", "-c:a", "aac", audio_path])

        # Remove silêncio do início e fim
        remove_silence(audio_path, trimmed_audio_path)

        # Gera vídeo vertical 1080x1920 com imagem cobrindo toda a tela
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-i", trimmed_audio_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"\
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            output_path
        ]
        run_cmd(cmd)

        return render_template("download.html", filename=os.path.basename(output_path))

    return render_template("index.html")


@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
