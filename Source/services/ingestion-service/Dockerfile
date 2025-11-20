FROM python:3.11-slim

# System dependencies for OCR and PDF conversion
RUN apt-get update; \
    apt-get install -y --no-install-recommends tesseract-ocr poppler-utils libglib2.0-0 libsm6 libxrender1 libxext6; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

ENV PYTHONUNBUFFERED=1

# Default command prints usage
ENTRYPOINT ["python", "app/main.py"]
CMD ["/app/data/raw_files/sample.pdf"]
