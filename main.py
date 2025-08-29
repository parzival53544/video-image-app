import os
import uuid
import subprocess
from flask import Flask, request, render_template, send_file
from pydub import AudioSegment, silence, effects

app = Flask(__name__)

# Pastas
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Caminho pro ffmpeg (se não estiver no PATH, coloque o caminho absoluto aqui)
FFMPEG_BIN = "ffmpeg"


def run_cmd(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def ensure_ffmpeg():
    rc, out, err = run_cmd([FFMPEG_BIN, "-version"])
    if rc != 0:
        raise RuntimeError("ffmpeg não foi encontrado. Instale e coloque no PATH.")


def detect_and_trim_with_pydub_from_video(video_path, out_trimmed_wav,
                                          min_silence_len_ms=300, rel_thresh_db=20):
    """
    Usa pydub para detectar trechos não-silenciosos e corta início/fim.
    - rel_thresh_db: quão abaixo da média (dBFS) considerar silêncio (ex: 20 -> 20dB abaixo do nível médio)
    Retorna (start_ms, end_ms) usados e escreve out_trimmed_wav (wav).
    """
    # carrega áudio inteiro do arquivo (pydub usa ffmpeg por baixo)
    audio = AudioSegment.from_file(video_path)
    # pega nível médio do áudio
    avg_db = audio.dBFS if audio.dBFS != float("-inf") else -60.0
    # calcula threshold absoluto
    silence_thresh = max(avg_db - rel_thresh_db, -60.0)  # limita em -60dB floor
    # detecta segmentos não-silenciosos
    nonsilent = silence.detect_nonsilent(audio,
                                         min_silence_len=min_silence_len_ms,
                                         silence_thresh=silence_thresh)
    if not nonsilent:
        # nada detectado — salva o original como WAV
        audio.export(out_trimmed_wav, format="wav")
        return 0, len(audio)

    start_ms = nonsilent[0][0]
    end_ms = nonsilent[-1][1]

    # extrai segmento com som
    sliced = audio[start_ms:end_ms]
    # peak-normalizar levemente para evitar picos
    sliced = effects.normalize(sliced)
    # salva como wav (alta fidelidade)
    sliced.export(out_trimmed_wav, format="wav")
    return start_ms, end_ms


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    # Valida upload
    if "image" not in request.files or "video" not in request.files:
        return "Envie 'image' e 'video'.", 400

    image_file = request.files["image"]
    video_file = request.files["video"]
    if image_file.filename == "" or video_file.filename == "":
        return "Arquivo inválido.", 400

    try:
        ensure_ffmpeg()
    except Exception as e:
        return f"Erro: ffmpeg não encontrado: {e}", 500

    # Salva uploads
    image_orig = os.path.basename(image_file.filename)
    base_name = os.path.splitext(image_orig)[0]
    image_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{image_orig}")
    video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}_{video_file.filename}")
    image_file.save(image_path)
    video_file.save(video_path)

    # caminhos intermediários
    resized_image = os.path.join(UPLOAD_FOLDER, f"resized_{uuid.uuid4()}.png")
    trimmed_wav = os.path.join(UPLOAD_FOLDER, f"trimmed_{uuid.uuid4()}.wav")
    normalized_m4a = os.path.join(UPLOAD_FOLDER, f"norm_{uuid.uuid4()}.m4a")
    output_mp4 = os.path.join(OUTPUT_FOLDER, f"{base_name}.mp4")

    try:
        # 1) redimensiona/pad imagem para 1080x1920 vertical
        rc, out, err = run_cmd([
            FFMPEG_BIN, "-y", "-i", image_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=rgba",
            resized_image
        ])
        if rc != 0:
            raise RuntimeError(f"Erro ao redimensionar imagem: {err.splitlines()[-1]}")

        # 2) detectar e cortar silêncio com pydub direto do arquivo de vídeo
        #    grava trimmed_wav com o áudio sem silêncio no começo/fim
        detect_and_trim_with_pydub_from_video(video_path, trimmed_wav,
                                              min_silence_len_ms=300, rel_thresh_db=22)

        # 3) normaliza o trimmed wav para LUFS com ffmpeg loudnorm (gera m4a)
        rc, out, err = run_cmd([
            FFMPEG_BIN, "-y", "-i", trimmed_wav,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=7",
            "-c:a", "aac", "-b:a", "320k",
            normalized_m4a
        ])
        if rc != 0:
            # se loudnorm falhar, tentamos fallback escrevendo WAV -> M4A com bitrate
            rc2, out2, err2 = run_cmd([
                FFMPEG_BIN, "-y", "-i", trimmed_wav,
                "-c:a", "aac", "-b:a", "320k",
                normalized_m4a
            ])
            if rc2 != 0:
                raise RuntimeError(f"Erro ao normalizar áudio (fallback também falhou): {err2}")

        # 4) Combina imagem (loop) + áudio normalizado em MP4 vertical
        rc, out, err = run_cmd([
            FFMPEG_BIN, "-y",
            "-loop", "1", "-i", resized_image,
            "-i", normalized_m4a,
            "-c:v", "libx264", "-tune", "stillimage",
            "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "320k",
            "-pix_fmt", "yuv420p", "-shortest",
            "-vf", "scale=1080:1920",
            output_mp4
        ])
        if rc != 0:
            raise RuntimeError(f"Erro ao gerar vídeo final: {err.splitlines()[-1]}")

        # 5) renderiza página de download
        return render_template("download.html", filename=os.path.basename(output_mp4))

    except Exception as e:
        # loga erro no servidor e retorna mensagem amigável
        print("PROCESS ERROR:", e)
        return f"Erro no processamento: {e}", 500

    finally:
        # limpa intermediários (mantemos output_mp4)
        for f in [image_path, video_path, resized_image, trimmed_wav, normalized_m4a]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass


@app.route("/download/<filename>", methods=["GET"])
def download(filename):
    path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(path):
        return "Arquivo não encontrado.", 404
    return send_file(path, as_attachment=True, download_name=filename, mimetype="video/mp4")


if __name__ == "__main__":
    # roda em 0.0.0.0:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
