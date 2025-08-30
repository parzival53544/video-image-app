# Usa imagem oficial do Python
FROM python:3.11-slim

# Atualiza o sistema e instala FFmpeg e dependências do sistema
RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia todos os arquivos do projeto
COPY . /app

# Atualiza pip e instala dependências Python
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta padrão do Flask/Gunicorn
EXPOSE 5000

# Comando para rodar a aplicação usando Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "main:app"]
