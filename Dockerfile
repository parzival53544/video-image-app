# Use Python 3.11
FROM python:3.11-slim

# Evita prompts e instala dependências básicas
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Cria pasta da aplicação
WORKDIR /app

# Copia todos os arquivos da aplicação
COPY . /app

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Expõe porta do Flask
EXPOSE 5000

# Comando para rodar a aplicação via Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "main:app"]
