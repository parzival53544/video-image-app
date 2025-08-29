# Use imagem oficial Python 3.11
FROM python:3.11-slim

# Evita prompts interativos no apt
ENV DEBIAN_FRONTEND=noninteractive

# Atualiza sistema e instala ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Diretório da aplicação
WORKDIR /app

# Copia arquivos do projeto
COPY . /app

# Instala dependências Python
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
# Gunicorn para deploy
RUN pip install --no-cache-dir gunicorn

# Porta que Render usará
EXPOSE 5000

# Comando de start via Gunicorn
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "300", "main:app"]
