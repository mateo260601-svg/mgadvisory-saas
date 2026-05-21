# MG Advisory Finance OS
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data/projects outputs
ENV PYTHONPATH=/app
ENV STORAGE_DIR=/app
CMD ["python", "start.py"]
