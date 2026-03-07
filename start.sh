#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || true
export PYTHONPATH=/home/coolhand/shared:$PYTHONPATH
exec python app.py
