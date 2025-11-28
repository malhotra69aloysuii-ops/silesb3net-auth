#!/bin/bash
echo "Starting Braintree Auth Checker API..."
exec gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 8 --timeout 0 btree:app
