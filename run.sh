#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
exec python -B -m streamlit run app.py "$@"
