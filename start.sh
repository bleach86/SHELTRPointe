#!/bin/bash

# Set default values
HOST="127.0.0.1"
PORT="52555"
SSL_KEYFILE=""
SSL_CERTFILE=""
PRODUCTION="false"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host=*)
            HOST="${1#*=}"
            shift
            ;;
        --port=*)
            PORT="${1#*=}"
            shift
            ;;
        --ssl-keyfile=*)
            SSL_KEYFILE="${1#*=}"
            shift
            ;;
        --ssl-certfile=*)
            SSL_CERTFILE="${1#*=}"
            shift
            ;;
        --production)
            PRODUCTION="true"
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Set host to 0.0.0.0 if in production mode
if [[ $PRODUCTION == "true" ]]; then
    HOST="0.0.0.0"
fi

# Start the server
if [[ -n $SSL_KEYFILE && -n $SSL_CERTFILE ]]; then
    uvicorn api:app._sio_app --host="$HOST" --port="$PORT" --ssl-keyfile="$SSL_KEYFILE" --ssl-certfile="$SSL_CERTFILE"
else
    uvicorn api:app._sio_app --host="$HOST" --port="$PORT"
fi
