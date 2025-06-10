FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта внутрь контейнера
COPY . .

# Запускаем бота
CMD ["python", "main.py"]
