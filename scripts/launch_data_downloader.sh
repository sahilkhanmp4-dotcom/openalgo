#!/usr/bin/env bash
# OpenAlgo Data Downloader Launcher

cd /home/john/openalgo || exit 1
mkdir -p /home/john/openalgo/log

# Check if Data Downloader is already running on port 8090
if ! curl -s --connect-timeout 1 http://127.0.0.1:8090/ > /dev/null 2>&1; then
    nohup /home/john/openalgo/venv/bin/python /home/john/openalgo/data_downloader_app.py </dev/null > /home/john/openalgo/log/data_downloader_desktop.log 2>&1 &
    disown
    
    # Wait for server to become responsive
    for i in $(seq 1 20); do
        if curl -s --connect-timeout 1 http://127.0.0.1:8090/ > /dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
fi

xdg-open "http://127.0.0.1:8090" > /dev/null 2>&1 &
