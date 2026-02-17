# Используем готовый образ с Python и всеми зависимостями браузеров
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем только python-пакеты (браузеры уже внутри образа!)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код
COPY . .

# Railway автоматически подхватит команду запуска из Procfile или CMD
CMD ["python", "main.py"]