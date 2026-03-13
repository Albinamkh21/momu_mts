FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/app

# 1. Сначала копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Копируем СОДЕРЖИМОЕ папки app в текущую папку (/app)
COPY ./app .

# 3. НЕ ДЕЛАЙ COPY . . — это всё испортит!

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]