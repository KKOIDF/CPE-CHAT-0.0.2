FROM python:3.11-slim

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run_server.py ./

ENV DATA_DIR=/app/data
ENV CHROMA_DIR=/app/data/chroma
ENV SQLITE_PATH=/app/data/db/ingestion.db
ENV RAG_HOST=0.0.0.0
ENV RAG_PORT=8001

EXPOSE 8001
CMD ["python", "run_server.py"]
