FROM python:3.9-slim

WORKDIR /app

# Копируем только нужные файлы (исключая .git через .dockerignore)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY app.py .
COPY data_managers.py .
COPY templates/ templates/
COPY static/ static/
# COPY employees.json .
# COPY student.json .

# Создаем папку storage и настраиваем права
RUN mkdir -p /app/storage && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Создаем необходимые подпапки с правильными правами
RUN mkdir -p /app/storage/violations && \
    chown -R appuser:appuser /app/storage
    
USER appuser

EXPOSE 5000

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Объявляем точку монтирования для volume
VOLUME /app/storage

CMD ["python", "app.py"]