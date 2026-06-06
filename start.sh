#!/bin/bash
echo "Starting FastAPI Backend..."
cd backend
source venv/bin/activate
python3 main.py &
BACKEND_PID=$!

echo "Starting Next.js Frontend..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

function cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    exit
}

trap cleanup SIGINT SIGTERM

echo "Servers are running! Access the frontend at http://localhost:3000"
echo "Press Ctrl+C to stop."
wait
