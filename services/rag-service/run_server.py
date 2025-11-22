import os
from uvicorn import run

def main():
    os.environ.setdefault('PYTHONPATH', 'app')
    run('app.main:app', host='127.0.0.1', port=8001, timeout_keep_alive=60)

if __name__ == '__main__':
    main()
