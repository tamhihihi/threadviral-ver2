FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8000

# Cài đặt FFmpeg và dependencies hệ thống
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    fonts-noto-color-emoji \
    fontconfig \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài đặt các gói Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt trình duyệt Chromium headless cho Playwright
RUN mkdir -p /ms-playwright && \
    playwright install --with-deps chromium && \
    chmod -R 777 /ms-playwright

# Copy mã nguồn dự án
COPY . .

# Tạo các thư mục làm việc và cấp quyền ghi
RUN mkdir -p outputs temp memes bgm backgrounds && \
    chmod -R 777 /app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
