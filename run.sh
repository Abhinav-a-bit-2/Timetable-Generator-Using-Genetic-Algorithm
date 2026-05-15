#!/bin/bash

# Start the backend in the background
uvicorn app:app --host 0.0.0.0 --port 8000 &

# Wait for backend to start
sleep 5

# Start the frontend
python frontend.py
