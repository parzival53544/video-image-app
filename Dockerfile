# Use uma imagem oficial do Python com pip
FROM python:3.11-slim

# Atualiza o sistema e instala ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia arquivos do projeto
COPY . /app

# Atualiza pip e instala dependências do Python
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta padrão do Flask
EXPOSE 5000

# Comando para rodar a aplicação no Render com Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]
