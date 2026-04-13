#!/bin/bash
# Plexus Coffee Dashboard — Local Server Launcher
# Double-click this file in Finder to start the dashboard

cd "$(dirname "$0")"

PORT=8765

# Kill anything already on that port
lsof -ti tcp:$PORT | xargs kill -9 2>/dev/null

echo "Starting Plexus Coffee Dashboard on http://localhost:$PORT"
echo "Press Ctrl+C to stop."
echo ""

# Start server in background, open browser
python3 -m http.server $PORT &
SERVER_PID=$!

sleep 0.8
open "http://localhost:$PORT/plexus-coffee-dashboard.html"

# Keep terminal open until Ctrl+C
trap "kill $SERVER_PID 2>/dev/null; echo 'Server stopped.'; exit 0" SIGINT SIGTERM
wait $SERVER_PID
