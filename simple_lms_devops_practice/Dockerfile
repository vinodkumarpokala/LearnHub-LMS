FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser && mkdir -p /data && chown -R appuser:appuser /app /data
ENV LMS_DB_PATH=/data/lms.db
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "python -c 'from app import init_db; init_db()' && gunicorn --workers 2 --bind 0.0.0.0:8000 app:app"]
