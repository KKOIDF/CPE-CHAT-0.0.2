FROM python:3.11-slim

WORKDIR /mlflow

# MLflow server for experiment tracking. We also install gunicorn explicitly for stable serving.
RUN pip install --no-cache-dir "mlflow==3.10.1" gunicorn \
    && python -c "import mlflow; print('mlflow', mlflow.__version__)"

EXPOSE 5000

# Persist backend store (SQLite) and serve artifacts via proxy from /mlflow/artifacts.
# Using `mlflow-artifacts:/` ensures clients can upload/download via the tracking server.
CMD ["mlflow", "server", "--host", "0.0.0.0", "--port", "5000", "--backend-store-uri", "sqlite:////mlflow/mlflow.db", "--serve-artifacts", "--artifacts-destination", "/mlflow/artifacts", "--default-artifact-root", "mlflow-artifacts:/", "--allowed-hosts", "localhost,localhost:5000,127.0.0.1,127.0.0.1:5000,mlflow,mlflow:5000,cpe-chat-mlflow,cpe-chat-mlflow:5000"]
