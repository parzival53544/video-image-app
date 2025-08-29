import os
import re
import uuid
import subprocess
from flask import Flask, request, render_template, send_file
from pydub import AudioSegment, silence, effects

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

FFMPEG_BIN = "ffmpeg"  # se precisar, troque para caminho absoluto no Windows, ex: r"C:\ffmpeg\bin\ffmpeg.exe"


def run_cmd(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        last = (proc.stderr or "").splitlines()[-1:] or ["ffmpeg error"]
        raise RuntimeError(f"FFmpeg falhou: {last[0]}")
    return proc.returncode, proc.stdout, proc.stderr


def ensure_ffmpeg():
    try:
        subprocess.run([FFMPEG_BIN, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception:
        raise RuntimeError("ffmpeg não encontrado. Instale e deixe no PATH (teste 'ffmpeg -version').")


def safe_basename(name: str) -> str:
    base = os.path.splitext(os.path.basename(name))[0]
    base = re.sub(r"[^A-Za-z0-9_\-]+", "_", base).strip("_")
    return base or "video_final"


def detect_content_bounds(audio: AudioSegment, min_silence_len_ms=300) -> tuple[int, int]:
    """
    Detecta início/fim reais do áudio.
    Tenta thresholds mais sensíveis se necessário (22 -> 18 -> 14 dB abaixo da média).
    Retorna (start_ms, end_ms). Se nada detectado, retorna todo o áudio.
    """
    if audio.duration_seconds <= 0:
        return 0, 0

    # dBFS médio do arquivo (fallback para -60 se -inf)
    avg_db = audio.dBFS if audio.dBFS != float("-inf") else -60.0
    candidates = [22, 18, 14]  # mais conservador -> mais sensível

    for rel in candidates:
        thresh = max(avg_db - rel, -60.0)
        non_silent = silence.detect_nonsilent(
            audio,
            min_silence_len=min_silence_len_ms,
            silence_thresh=thresh
        )
        if non_silent:
            start_ms = max(0, non_silent[0][0])
            end_ms = min(len(audio), non_silent[-1][1])
            # Segurança: se ficou muito curto, relaxa
            if end_ms - start_ms >= 200:
                return start_ms, end_ms

    # Se não achou, usa inteiro
    return 0, len(audio)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    # Checagem dos campos esperados
    if "image" not in request.files or "video" not in request.files:
        return "Envie uma IMAGEM e um VÍDEO.", 400

    image_file = request.files["image"]
    video_file = request.files["video"]
    if image_file.filename == "" or video_file.filename == "":
        return "Arquivos inválidos.", 400

    try:
        ensure_ffmpeg()
    except Exception as e:
        return f"Erro: {e}", 500

    # Nomes e caminhos
    final_base = safe_basename(image_file.filename)  # nome do vídeo final = nome da imagem
    image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{os.path.basename(image_file.filename)}")
    video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{os.path.basename(video_file.filename)}")
    image_file.save(image_path)
    video_file.save(video_path)

    # Intermediários
    resized_image = os.path.join(UPLOAD_FOLDER, f"resized_{uuid.uuid4()}.png")
    audio_wav = os.path.join(UPLOAD_FOLDER, f"audio_{uuid.uuid4()}.wav")
    trimmed_wav = os.path.join(UPLOAD_FOLDER, f"trimmed_{uuid.uuid4()}.wav")
    normalized_m4a = os.path.join(UPLOAD_FOLDER, f"norm_{uuid.uuid4()}.m4a")
    output_path = os.path.join(OUTPUT_FOLDER, f"{final_base}.mp4")

    try:
        # 1) Ajusta IMAGEM para VERTICAL 1080x1920 (preserva proporção + pad)
        run_cmd([
            FFMPEG_BIN, "-y", "-i", image_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=rgba",
            resized_image
        ])

        # 2) Extrai ÁUDIO do VÍDEO (WAV 48k, estéreo)
        run_cmd([FFMPEG_BIN, "-y", "-i", video_path, "-vn", "-ac", "2", "-ar", "48000", "-f", "wav", audio_wav])

        # 3) Remoção inteligente de silêncio (início e fim) com pydub
        audio = AudioSegment.from_wav(audio_wav)
        start_ms, end_ms = detect_content_bounds(audio, min_silence_len_ms=300)
        if end_ms <= start_ms:
            # fallback: usa áudio inteiro
            start_ms, end_ms = 0, len(audio)

        sliced = audio[start_ms:end_ms]
        # normalização de pico leve antes do loudnorm (ajuda SNR)
        sliced = effects.normalize(sliced)
        sliced.export(trimmed_wav, format="wav")

        # 4) Normalização de loudness (LUFS) e encode para M4A (evita bug do .aac no Windows)
        try:
            run_cmd([
                FFMPEG_BIN, "-y", "-i", trimmed_wav,
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=7",
                "-c:a", "aac", "-b:a", "320k",
                normalized_m4a
            ])
        except Exception:
            # Fallback: se loudnorm falhar, apenas codifica em AAC 320k
            run_cmd([
                FFMPEG_BIN, "-y", "-i", trimmed_wav,
                "-c:a", "aac", "-b:a", "320k",
                normalized_m4a
            ])

        # 5) Combina IMAGEM + ÁUDIO em VÍDEO vertical 1080x1920
        #    -loop 1 mantém imagem fixa, -shortest fecha no fim do áudio, +faststart melhora playback web
        run_cmd([
            FFMPEG_BIN, "-y",
            "-loop", "1", "-framerate", "30", "-i", resized_image,
            "-i", normalized_m4a,
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            "-movflags", "+faststart",
            output_path
        ])

        return render_template("download.html", filename=os.path.basename(output_path))

    except Exception as e:
        print("ERRO NO PROCESSO:", e)
        return f"Erro no processamento: {e}", 500

    finally:
        # Limpeza de temporários (mantém apenas o vídeo final em outputs/)
        for f in [image_path, video_path, resized_image, audio_wav, trimmed_wav, normalized_m4a]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass


@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(path):
        return "Arquivo não encontrado.", 404
    return send_file(path, as_attachment=True, download_name=filename, mimetype="video/mp4")


if __name__ == "__main__":
    # Local: http://localhost:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
