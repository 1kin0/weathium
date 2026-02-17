# 1. Используем slim версию образа, если не нужны все 3 браузера
FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

# Переменные окружения для ускорения Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /app

# 2. Сначала копируем только requirements для кэширования слоя
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Копируем остальное (изменения здесь не затронут установку библиотек)
COPY . .

CMD ["python", "main.py"]