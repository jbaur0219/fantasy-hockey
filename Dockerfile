FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pywebpush tzdata pillow
COPY . .
ENV DATA_DIR=/data PYTHONUNBUFFERED=1
CMD ["python", "server.py"]
