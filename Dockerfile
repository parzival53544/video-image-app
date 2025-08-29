# Imagem base oficial do Python
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Copia todos os arquivos do projeto para o container
COPY . /app

# Instala dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Instala FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Expondo a porta padrão do Render
EXPOSE 10000

# Comando para rodar a aplicação com Gunicorn
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:10000", "main:app"]
