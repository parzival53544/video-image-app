# Usa imagem oficial do Python
FROM python:3.10-slim

# Define pasta de trabalho
WORKDIR /app

# Instala dependências do sistema (FFmpeg é essencial para MoviePy)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos do projeto
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expõe a porta usada pelo Flask/Render
EXPOSE 10000

# Comando para rodar no Render (Gunicorn é mais estável que flask run)
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--timeout", "300", "main:app"]