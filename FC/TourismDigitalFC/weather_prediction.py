"""
Weather Prediction Module for Sigiriya

This module provides weather forecasting functionality using trained machine learning models
(Gradient Boosting) trained on historical weather data. It predicts temperature, rainfall,
and wind speed for given dates.

Models:
- temp_model: Predicts average daily temperature (°C)
- rain_model: Predicts daily rainfall (mm)
- wind_model: Predicts average wind speed (m/s)

Features used:
- dayofweek: Day of the week (0-6)
- month: Month of the year (1-12)
- day: Day of the month (1-31)
- season: Sri Lankan season (1-4)
"""

import pandas as pd
import joblib
import os
from typing import List, Dict
from datetime import datetime


# ============================================================================
# SEASONAL CLASSIFICATION
# ============================================================================

def sri_lanka_season(month: int) -> int:
    """
    Classify the season based on month in Sri Lanka.
    
    Args:
        month: Month number (1-12)
    
    Returns:
        Season code:
        - 1: Southwest Monsoon (May-Sep)
        - 2: Northeast Monsoon (Dec-Feb)
        - 3: First Inter-monsoon (Mar-Apr)
        - 4: Second Inter-monsoon (Oct-Nov)
    """
    if month in [5, 6, 7, 8, 9]:
        return 1   # Southwest Monsoon
    elif month in [12, 1, 2]:
        return 2   # Northeast Monsoon
    elif month in [3, 4]:
        return 3   # First Inter-monsoon
    else:
        return 4   # Second Inter-monsoon


def weather_type(rain_mm: float, wind_ms: float) -> str:
    """
    Classify weather conditions based on rainfall and wind speed.
    
    Args:
        rain_mm: Rainfall in millimeters
        wind_ms: Wind speed in meters per second
    
    Returns:
        Weather description with emoji
    """
    if rain_mm > 30:
        return "Heavy Rain 🌧️"
    elif rain_mm > 20:
        return "Moderate Rain 🌦️"
    elif rain_mm > 15:
        return "Light Rain 🌦️"
    elif wind_ms > 6:
        return "Windy 🌬️"
    else:
        return "Clear ☀️"


# ============================================================================
# MODEL LOADING
# ============================================================================

def load_weather_models(models_dir: str = "./models"):
    """
    Load trained weather prediction models.
    
    Args:
        models_dir: Directory containing the trained model files
    
    Returns:
        Tuple of (temp_model, rain_model, wind_model)
    """
    try:
        temp_model = joblib.load(os.path.join(models_dir, "temp.pkl"))
        rain_model = joblib.load(os.path.join(models_dir, "rain.pkl"))
        wind_model = joblib.load(os.path.join(models_dir, "wind.pkl"))
        
        print(f"✓ Weather models loaded successfully from {models_dir}")
        return temp_model, rain_model, wind_model
    except FileNotFoundError as e:
        print(f"✗ Error: Could not find model files in {models_dir}")
        print(f"  Make sure you have run weather_training.ipynb first")
        raise


# ============================================================================
# GLOBAL MODEL INSTANCES
# ============================================================================

_models_loaded = False
temp_model = None
rain_model = None
wind_model = None


def initialize_models(models_dir: str = "./models"):
    """Initialize global model instances."""
    global _models_loaded, temp_model, rain_model, wind_model
    
    if not _models_loaded:
        temp_model, rain_model, wind_model = load_weather_models(models_dir)
        _models_loaded = True


# ============================================================================
# WEATHER PREDICTION
# ============================================================================

def get_weather_for_dates(dates: List[datetime]) -> str:
    """
    Predict weather for a list of dates.
    
    Args:
        dates: List of datetime objects to predict weather for
    
    Returns:
        Formatted string with weather predictions for each date
    """
    if not _models_loaded or temp_model is None:
        return "❌ Weather models not initialized. Please ensure models are trained."
    
    # Prepare features for the dates
    X = pd.DataFrame({
        'dayofweek': [d.weekday() for d in dates],
        'month': [d.month for d in dates],
        'day': [d.day for d in dates],
        'season': [sri_lanka_season(d.month) for d in dates]
    })
    
    # Make predictions
    temps = temp_model.predict(X)
    rains = rain_model.predict(X)
    winds = wind_model.predict(X)
    
    # Format response
    response = ""
    for i, d in enumerate(dates):
        temp = round(temps[i], 1)
        rain = round(rains[i], 1)
        wind = round(winds[i], 1)
        weather = weather_type(rains[i], winds[i])
        
        day_name = d.strftime('%A')
        date_str = d.strftime('%b %d, %Y')
        
        response += (
            f"📅 **{date_str} ({day_name})**\n"
            f"🌡️ Temperature: {temp}°C\n"
            f"💧 Rainfall: {rain}mm\n"
            f"💨 Wind Speed: {wind}m/s\n"
            f"⛅ Conditions: {weather}\n\n"
        )
    
    return response.strip()


def get_weather_dict_for_dates(dates: List[datetime]) -> List[Dict]:
    """
    Predict weather for a list of dates and return as list of dictionaries.
    
    Args:
        dates: List of datetime objects to predict weather for
    
    Returns:
        List of dictionaries with weather predictions
    """
    if not _models_loaded or temp_model is None:
        return []
    
    # Prepare features for the dates
    X = pd.DataFrame({
        'dayofweek': [d.weekday() for d in dates],
        'month': [d.month for d in dates],
        'day': [d.day for d in dates],
        'season': [sri_lanka_season(d.month) for d in dates]
    })
    
    # Make predictions
    temps = temp_model.predict(X)
    rains = rain_model.predict(X)
    winds = wind_model.predict(X)
    
    # Format as dictionaries
    results = []
    for i, d in enumerate(dates):
        results.append({
            'date': d.strftime('%Y-%m-%d'),
            'day_of_week': d.strftime('%A'),
            'temperature_celsius': round(temps[i], 1),
            'rainfall_mm': round(rains[i], 1),
            'wind_speed_ms': round(winds[i], 1),
            'weather_condition': weather_type(rains[i], winds[i]),
            'is_rainy': bool(rains[i] > 3),
            'is_windy': bool(winds[i] > 5),
            'is_heavy_rain': bool(rains[i] > 15)
        })
    
    return results


def get_weather_summary_for_date(date: datetime) -> Dict:
    """
    Get weather prediction for a single date.
    
    Args:
        date: datetime object for the date
    
    Returns:
        Dictionary with weather predictions
    """
    results = get_weather_dict_for_dates([date])
    return results[0] if results else {}


def get_best_weather_dates(dates: List[datetime]) -> List[Dict]:
    """
    Get weather predictions and rank dates by weather quality.
    Best dates have clear weather with mild temperature and no rain.
    
    Args:
        dates: List of datetime objects
    
    Returns:
        List of dictionaries sorted by weather quality (best first)
    """
    weather_data = get_weather_dict_for_dates(dates)
    
    # Score each date (higher is better)
    for item in weather_data:
        # Ideal temperature: 24-28°C
        temp_score = 10 - abs(item['temperature_celsius'] - 26) * 0.5
        temp_score = max(0, min(10, temp_score))
        
        # Penalty for rain
        rain_penalty = item['rainfall_mm'] * 0.5
        
        # Penalty for wind
        wind_penalty = item['wind_speed_ms'] * 0.3
        
        # Overall score
        item['weather_score'] = max(0, temp_score - rain_penalty - wind_penalty)
    
    # Sort by weather score (descending)
    return sorted(weather_data, key=lambda x: x['weather_score'], reverse=True)
