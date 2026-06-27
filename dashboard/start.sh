#!/bin/bash
pip install fastapi==0.115.5 uvicorn==0.32.1 python-multipart==0.0.12
python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
