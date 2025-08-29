import os
import uuid
import subprocess
from flask import Flask, request, render_template, send_file

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def run_ffmpeg(cmd):
    """Executa comandos ffmpeg e lança exceção se falhar."""
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Erro FFmpeg: {result.stderr}")
    return result

def trim_silence(input_audio, output_audio):
    """Remove silêncios do início e fim usando FFmpeg"""
    cmd = [
        "ffmpeg", "-y", "-i", input_audio,
        "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.5:\
detection=peak,areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.5:detection=peak,areverse",
        "-c:a", "aac", "-b:a", "320k",
        output_audio
    ]
    run_ffmpeg(cmd)

def normalize_audio(input_audio, output_audio):
    """Normaliza o volume"""
    cmd = [
        "ffmpeg", "-y", "-i", input_audio,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "320k",
        output_audio
    ]
    run_ffmpeg(cmd)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        image_file = request.files.get("image")
        video_file = request.files.get("video")

        if not image_file or not video_file:
            return "Por favor, envie uma imagem e um vídeo.", 400

        # Salva arquivos
        image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{image_file.filename}")
        video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{video_file.filename}")
        image_file.save(image_path)
        video_file.save(video_path)

        # Nome final baseado na imagem original
        final_filename = os.path.splitext(image_file.filename)[0] + ".mp4"
        output_path = os.path.join(OUTPUT_FOLDER, final_filename)

        # Ajusta imagem para 1080x1920 vertical
        resized_image = os.path.join(UPLOAD_FOLDER, f"resized_{uuid.uuid4()}.png")
        resize_cmd = [
            "ffmpeg", "-y", "-i", image_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            resized_image
        ]
        run_ffmpeg(resize_cmd)

        # Extrai áudio do vídeo
        audio_file = os.path.join(UPLOAD_FOLDER, f"audio_{uuid.uuid4()}.aac")
        extract_audio_cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-c:a", "aac", audio_file]
        run_ffmpeg(extract_audio_cmd)

        # Remove silêncios
        trimmed_audio = os.path.join(UPLOAD_FOLDER, f"trimmed_{uuid.uuid4()}.aac")
        trim_silence(audio_file, trimmed_audio)

        # Normaliza áudio
        normalized_audio = os.path.join(UPLOAD_FOLDER, f"norm_{uuid.uuid4()}.aac")
        normalize_audio(trimmed_audio, normalized_audio)

        # Combina imagem + áudio em vídeo final
        combine_cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", resized_image,
            "-i", normalized_audio,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            output_path
        ]
        run_ffmpeg(combine_cmd)

        return render_template("download.html", filename=final_filename)

    return render_template("index.html")

@app.route("/download/<filename>")
def download(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
