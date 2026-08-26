#!/usr/bin/env bash
# OpenAlgo Quant Studio & Strategy Builder Launcher

cd /home/john/openalgo || exit 1
mkdir -p /home/john/openalgo/log
export PYTHONPATH="/home/john/openalgo:${PYTHONPATH}"

# Check if Quant Studio is already running on port 8080
if ! curl -s --connect-timeout 1 http://127.0.0.1:8080/ > /dev/null 2>&1; then
    nohup /home/john/openalgo/venv/bin/python /home/john/openalgo/quant_engine/app.py </dev/null > /home/john/openalgo/log/quant_studio_desktop.log 2>&1 &
    disown
    
    # Wait for server to become responsive
    for i in $(seq 1 20); do
        if curl -s --connect-timeout 1 http://127.0.0.1:8080/ > /dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
fi

xdg-open "http://127.0.0.1:8080" > /dev/null 2>&1 &
