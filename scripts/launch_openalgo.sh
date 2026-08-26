#!/usr/bin/env bash
# OpenAlgo Platform Launcher

cd /home/john/openalgo || exit 1
mkdir -p /home/john/openalgo/log

# Check if OpenAlgo is already running on port 5000
if ! curl -s --connect-timeout 1 http://127.0.0.1:5000/ > /dev/null 2>&1; then
    nohup /home/john/openalgo/venv/bin/python /home/john/openalgo/app.py </dev/null > /home/john/openalgo/log/app_desktop.log 2>&1 &
    disown
    
    # Wait for server to become responsive (up to 10 seconds)
    for i in $(seq 1 20); do
        if curl -s --connect-timeout 1 http://127.0.0.1:5000/ > /dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
fi

xdg-open "http://127.0.0.1:5000" > /dev/null 2>&1 &
