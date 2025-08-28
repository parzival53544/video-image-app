# Usa imagem base com Python e FFmpeg
FROM python:3.11-slim

# Instala dependências do sistema
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Cria pastas
RUN mkdir /app /app/uploads /app/outputs

# Define diretório de trabalho
WORKDIR /app

# Copia arquivos Python e templates
COPY . /app

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Expondo a porta padrão do Flask no Render
EXPOSE 5000

# Comando para rodar a aplicação
CMD ["python", "main.py"]
