# Use imagem oficial do Python 3.11 slim
FROM python:3.11-slim

# Instala FFmpeg e dependências do sistema
RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia arquivos do projeto para o container
COPY . /app

# Atualiza pip e instala dependências Python
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expõe porta padrão usada pelo Render
ENV PORT=10000
EXPOSE $PORT

# Comando para rodar a aplicação com Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "main:app"]
