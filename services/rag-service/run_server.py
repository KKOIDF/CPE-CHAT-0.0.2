import os
from uvicorn import run

def main():
    os.environ.setdefault('PYTHONPATH', 'app')
    # Allow configuration via environment variables
    host = os.getenv('RAG_HOST', '127.0.0.1')
    port = int(os.getenv('RAG_PORT', '8001'))
    run('app.main:app', host=host, port=port, timeout_keep_alive=60)

if __name__ == '__main__':
    main()
