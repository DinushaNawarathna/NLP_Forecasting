#!/bin/bash

# Start backend with OpenWeatherMap API key
# This script ensures the API key is available to the Python process

API_KEY="30ecd5116d9a2c98dc94fcfa6dbfba7d"

if [ -z "$API_KEY" ]; then
    echo "❌ Error: API_KEY is not set"
    exit 1
fi

echo "🚀 Starting backend with OpenWeatherMap API key..."
echo "📍 API Key: ${API_KEY:0:10}...${API_KEY: -5}"

export OPENWEATHER_API_KEY="$API_KEY"
python main.py
