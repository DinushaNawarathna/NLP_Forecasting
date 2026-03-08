"""
OpenWeatherMap Integration Module

This module integrates real-time hourly weather data from OpenWeatherMap API.
It provides functions to fetch current, hourly, and forecast weather data for Sigiriya.

API: https://openweathermap.org/
Sigiriya Coordinates: 7.9570° N, 80.7595° E
"""

import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import pytz

# Try to load from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required, will use environment variables

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenWeatherMap API Configuration
SIGIRIYA_LAT = 7.9570
SIGIRIYA_LON = 80.7595

# Sri Lanka Timezone
SRI_LANKA_TZ = pytz.timezone('Asia/Colombo')

# API Endpoints
CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
HOURLY_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
ONE_CALL_URL = "https://api.openweathermap.org/data/3.0/onecall"


def get_api_key():
    """Get API key from environment variable or .env file at runtime."""
    api_key = os.getenv('OPENWEATHER_API_KEY')
    logger.info(f"🔍 Checking environment variable OPENWEATHER_API_KEY: {'SET' if api_key else 'NOT SET'}")
    
    if api_key:
        logger.info(f"✅ API key found: {api_key[:10]}...{api_key[-5:]}")
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        logger.warning("⚠️ OPENWEATHER_API_KEY not set or invalid. Set it with: export OPENWEATHER_API_KEY='your_key'")
        return None
    
    return api_key


class OpenWeatherMapClient:
    """Client for OpenWeatherMap API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenWeatherMap client.
        
        Args:
            api_key: OpenWeatherMap API key (if None, reads from environment)
        """
        if api_key is None:
            api_key = get_api_key()
        
        self.api_key = api_key
        self.base_params = {
            'lat': SIGIRIYA_LAT,
            'lon': SIGIRIYA_LON,
            'units': 'metric',
            'appid': self.api_key
        }
    
    def get_current_weather(self) -> Optional[Dict]:
        """
        Get current weather conditions for Sigiriya.
        
        Returns:
            Dictionary with current weather data or None if API fails
            {
                'temp': float,
                'feels_like': float,
                'humidity': int,
                'pressure': int,
                'description': str,
                'main': str,
                'wind_speed': float,
                'wind_deg': int,
                'clouds': int,
                'timestamp': datetime
            }
        """
        if not self.api_key:
            logger.error("❌ OpenWeatherMap API key not set. Set OPENWEATHER_API_KEY environment variable.")
            return None
        
        try:
            response = requests.get(CURRENT_WEATHER_URL, params=self.base_params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Convert UTC timestamp to Sri Lanka timezone
            utc_time = datetime.fromtimestamp(data['dt'], tz=pytz.UTC)
            sl_time = utc_time.astimezone(SRI_LANKA_TZ)
            
            return {
                'temp': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'description': data['weather'][0]['description'],
                'main': data['weather'][0]['main'],
                'wind_speed': data['wind']['speed'],
                'wind_deg': data['wind'].get('deg', 0),
                'clouds': data['clouds']['all'],
                'timestamp': sl_time
            }
        except Exception as e:
            logger.error(f"Error fetching current weather: {e}")
            return None
    
    def get_hourly_forecast(self, hours: int = 48) -> Optional[List[Dict]]:
        """
        Get hourly weather forecast for next N hours.
        Note: OpenWeatherMap free plan provides 3-hourly forecasts, not hourly.
        So times will be in 3-hour intervals.
        
        Args:
            hours: Number of hours to forecast (max 120 for free plan)
        
        Returns:
            List of forecast dictionaries (3-hourly intervals)
            [{
                'datetime': datetime,
                'temp': float,
                'feels_like': float,
                'humidity': int,
                'description': str,
                'main': str,
                'wind_speed': float,
                'rainfall': float,  # mm
                'clouds': int,
                'visibility': int,
                'pop': float  # Probability of precipitation 0-1
            }, ...]
        """
        if not self.api_key:
            logger.error("❌ OpenWeatherMap API key not set. Set OPENWEATHER_API_KEY environment variable.")
            return None
        
        try:
            response = requests.get(HOURLY_FORECAST_URL, params=self.base_params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            forecasts = []
            hour_count = 0
            
            # Get current time in Sri Lanka timezone
            now_sl = datetime.now(SRI_LANKA_TZ)
            
            for item in data['list']:
                if hour_count >= hours:
                    break
                
                # Convert Unix timestamp (UTC) to Sri Lanka timezone
                # datetime.fromtimestamp() with tz parameter does the correct conversion
                sl_time = datetime.fromtimestamp(item['dt'], tz=SRI_LANKA_TZ)
                
                rainfall = 0
                if 'rain' in item and '3h' in item['rain']:
                    rainfall = item['rain']['3h'] / 3  # Convert 3h rainfall to hourly
                
                forecasts.append({
                    'datetime': sl_time,
                    'temp': item['main']['temp'],
                    'feels_like': item['main']['feels_like'],
                    'humidity': item['main']['humidity'],
                    'description': item['weather'][0]['description'],
                    'main': item['weather'][0]['main'],
                    'wind_speed': item['wind']['speed'],
                    'rainfall': rainfall,
                    'clouds': item['clouds']['all'],
                    'visibility': item['visibility'],
                    'pop': item.get('pop', 0)  # Probability of precipitation
                })
                hour_count += 1
            
            return forecasts
        except Exception as e:
            logger.error(f"Error fetching hourly forecast: {e}")
            return None
    
    def get_daily_forecast(self, days: int = 7) -> Optional[List[Dict]]:
        """
        Get daily weather forecast for next N days.
        
        Args:
            days: Number of days to forecast (max 5 for free plan)
        
        Returns:
            List of daily forecast dictionaries
            [{
                'date': datetime,
                'temp_max': float,
                'temp_min': float,
                'temp_avg': float,
                'description': str,
                'main': str,
                'humidity': int,
                'wind_speed': float,
                'rainfall': float,  # mm
                'clouds': int,
                'pop': float  # Probability of precipitation
            }, ...]
        """
        try:
            response = requests.get(HOURLY_FORECAST_URL, params=self.base_params)
            response.raise_for_status()
            data = response.json()
            
            daily_data = {}
            
            for item in data['list']:
                # Convert UTC to Sri Lanka timezone
                utc_time = datetime.fromtimestamp(item['dt'], tz=pytz.UTC)
                dt = utc_time.astimezone(SRI_LANKA_TZ)
                date_key = dt.date()
                
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        'temps': [],
                        'descriptions': [],
                        'mains': [],
                        'humidities': [],
                        'wind_speeds': [],
                        'rainfall': 0,
                        'clouds': [],
                        'pop': 0,
                        'count': 0
                    }
                
                daily_data[date_key]['temps'].append(item['main']['temp'])
                daily_data[date_key]['descriptions'].append(item['weather'][0]['description'])
                daily_data[date_key]['mains'].append(item['weather'][0]['main'])
                daily_data[date_key]['humidities'].append(item['main']['humidity'])
                daily_data[date_key]['wind_speeds'].append(item['wind']['speed'])
                daily_data[date_key]['clouds'].append(item['clouds']['all'])
                daily_data[date_key]['pop'] = max(daily_data[date_key]['pop'], item.get('pop', 0))
                daily_data[date_key]['count'] += 1
                
                if 'rain' in item and '3h' in item['rain']:
                    daily_data[date_key]['rainfall'] += item['rain']['3h']
            
            forecasts = []
            for date_key, data_dict in sorted(daily_data.items())[:days]:
                forecasts.append({
                    'date': datetime.combine(date_key, datetime.min.time()),
                    'temp_max': max(data_dict['temps']),
                    'temp_min': min(data_dict['temps']),
                    'temp_avg': sum(data_dict['temps']) / len(data_dict['temps']),
                    'description': data_dict['descriptions'][0],  # Most common description
                    'main': data_dict['mains'][0],
                    'humidity': sum(data_dict['humidities']) // len(data_dict['humidities']),
                    'wind_speed': sum(data_dict['wind_speeds']) / len(data_dict['wind_speeds']),
                    'rainfall': round(data_dict['rainfall'], 2),
                    'clouds': sum(data_dict['clouds']) // len(data_dict['clouds']),
                    'pop': data_dict['pop']
                })
            
            return forecasts
        except Exception as e:
            logger.error(f"Error fetching daily forecast: {e}")
            return None


# Singleton instance
_client = None


def get_client() -> OpenWeatherMapClient:
    """Get or create OpenWeatherMap client."""
    global _client
    if _client is None:
        _client = OpenWeatherMapClient()
    return _client


def get_current_weather() -> Optional[Dict]:
    """Get current weather for Sigiriya."""
    return get_client().get_current_weather()


def get_hourly_weather(hours: int = 48) -> Optional[List[Dict]]:
    """Get hourly weather forecast."""
    return get_client().get_hourly_forecast(hours)


def get_daily_weather(days: int = 7) -> Optional[List[Dict]]:
    """Get daily weather forecast."""
    return get_client().get_daily_forecast(days)


def format_hourly_for_display(hourly_data: List[Dict]) -> List[Dict]:
    """
    Format hourly weather data for display to user.
    
    Args:
        hourly_data: List of hourly forecast dictionaries
    
    Returns:
        Formatted list with readable descriptions
    """
    formatted = []
    for hour_data in hourly_data:
        temp_desc = format_temperature(hour_data['temp'])
        rain_desc = format_rainfall(hour_data['rainfall'])
        wind_desc = format_wind(hour_data['wind_speed'])
        
        formatted.append({
            'time': hour_data['datetime'].strftime('%I:%M %p'),
            'date': hour_data['datetime'].strftime('%A, %B %d'),
            'temp': f"{hour_data['temp']:.1f}°C",
            'temp_description': temp_desc,
            'condition': hour_data['main'],
            'description': hour_data['description'],
            'wind_speed': f"{hour_data['wind_speed']:.1f} m/s",
            'wind_description': wind_desc,
            'rainfall': f"{hour_data['rainfall']:.1f} mm",
            'rainfall_description': rain_desc,
            'humidity': f"{hour_data['humidity']}%",
            'clouds': f"{hour_data['clouds']}%",
            'visibility': f"{hour_data['visibility'] / 1000:.1f} km",
            'pop': f"{int(hour_data['pop'] * 100)}%",
            'recommendation': get_visit_recommendation(
                hour_data['temp'],
                hour_data['rainfall'],
                hour_data['wind_speed']
            )
        })
    
    return formatted


def format_temperature(temp: float) -> str:
    """Format temperature with emoji and description."""
    if temp < 15:
        return "🥶 Very Cold"
    elif temp < 18:
        return "❄️ Cold"
    elif temp < 22:
        return "🧥 Cool"
    elif temp < 26:
        return "☀️ Comfortable"
    elif temp < 30:
        return "🌞 Warm"
    elif temp < 35:
        return "🔥 Hot"
    else:
        return "🌡️ Very Hot"


def format_rainfall(rainfall: float) -> str:
    """Format rainfall with emoji and description."""
    if rainfall == 0:
        return "✅ No Rain"
    elif rainfall < 2:
        return "🌤️ Light Drizzle"
    elif rainfall < 5:
        return "☔ Light Rain"
    elif rainfall < 10:
        return "🌧️ Moderate Rain"
    elif rainfall < 20:
        return "⛈️ Heavy Rain"
    else:
        return "⛈️ Very Heavy Rain"


def format_wind(wind_speed: float) -> str:
    """Format wind speed with emoji and description."""
    if wind_speed < 2:
        return "🌬️ Calm"
    elif wind_speed < 5:
        return "💨 Light Breeze"
    elif wind_speed < 10:
        return "🌬️ Moderate Wind"
    elif wind_speed < 15:
        return "💨 Strong Wind"
    else:
        return "🌪️ Very Strong Wind"


def get_visit_recommendation(temp: float, rainfall: float, wind_speed: float) -> str:
    """Get overall recommendation for visiting Sigiriya."""
    score = 0
    
    # Temperature scoring
    if 20 <= temp <= 26:
        score += 3
    elif 18 <= temp <= 30:
        score += 2
    elif 15 <= temp <= 35:
        score += 1
    
    # Rainfall scoring
    if rainfall == 0:
        score += 3
    elif rainfall < 5:
        score += 2
    elif rainfall < 10:
        score += 1
    
    # Wind scoring
    if wind_speed < 10:
        score += 2
    elif wind_speed < 15:
        score += 1
    
    if score >= 7:
        return "✅ Excellent conditions for visiting!"
    elif score >= 5:
        return "👍 Good conditions for visiting"
    elif score >= 3:
        return "⚠️ Fair conditions, plan accordingly"
    else:
        return "❌ Not ideal conditions for visiting"
