# Dockerfile para Render (Flask + pydub + ffmpeg)
FROM python:3.11-slim

# Evita prompts interativos
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Instala dependências do sistema (inclui ffmpeg)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

# Cria diretório da app
WORKDIR /app

# Copia requirements e instala dependências Python
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copia o restante do projeto
COPY . /app

# Expondo a porta usada pela app
EXPOSE 5000

# Comando que o Render irá executar (gunicorn serve app: main:app)
# Ajuste o number de workers conforme necessidade (4 é razoável para pequenos serviços)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "main:app"]
