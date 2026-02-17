# Используем версию 1.50.0 или выше (на текущий момент 1.58.0)
FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Команда запуска
CMD ["python", "main.py"]