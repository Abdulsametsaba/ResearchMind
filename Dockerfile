
# ResearchMind - Dockerfile

FROM python:3.12-slim

# PyMuPDF ve diğer sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kaynak kodları
COPY backend/ ./

ENV PYTHONPATH=/app

# Çalışma dizinleri
RUN mkdir -p /app/data/cache/papers /app/data/reports

# Hugging Face varsayılan portu
EXPOSE 7860

# HF: PORT=7860
# Docker Compose: PORT=8000 olarak override edilecek
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --log-level info"]
