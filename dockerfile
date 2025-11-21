FROM python:3.9-slim

WORKDIR /app

# Копируем только нужные файлы (исключая .git через .dockerignore)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY app.py .
COPY templates/ templates/
COPY static/ static/
COPY employees.json .

# Создаем непривилегированного пользователя для безопасности
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]