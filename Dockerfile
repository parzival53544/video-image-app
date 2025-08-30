# Usa Python 3.11 slim
FROM python:3.11-slim

# Atualiza o sistema e instala FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia todos os arquivos do projeto
COPY . /app

# Atualiza pip e instala dependências
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expõe porta padrão do Flask/Gunicorn
EXPOSE 5000

# Comando para rodar a aplicação no Render
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]
