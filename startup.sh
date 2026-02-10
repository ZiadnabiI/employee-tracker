#!/bin/bash
# Azure App Service startup script for FastAPI
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
