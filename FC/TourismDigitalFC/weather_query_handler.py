"""Enhanced Weather Query Handler for 2026"""
import re
import datetime
from datetime import timedelta
from typing import Optional, List, Dict

try:
    from weather_prediction import get_weather_dict_for_dates, initialize_models
    initialize_models()
except:
    pass

try:
    from openweather_integration import get_hourly_weather, format_hourly_for_display
except:
    get_hourly_weather = None
    format_hourly_for_display = None

from location_validator import should_reject_query

# Helper functions for weather interpretation
def interpret_temperature(temp: float) -> str:
    """Interpret temperature and return description."""
    if temp < 15:
        return f"❄️ It'll be quite cold at {temp:.1f}°C - a bit chilly for Sigiriya"
    elif temp < 18:
        return f"🧥 The temperature will be around {temp:.1f}°C - cool weather, you might want a light jacket"
    elif temp < 22:
        return f"🌤️ It should be around {temp:.1f}°C - pleasant and refreshing"
    elif temp < 26:
        return f"☀️ The temperature will be around {temp:.1f}°C - ideal for visiting and climbing"
    elif temp < 30:
        return f"🌞 It will be warm at {temp:.1f}°C - great for exploring, but bring sunscreen"
    elif temp < 35:
        return f"🔥 It'll be quite hot at {temp:.1f}°C - stay hydrated while climbing"
    else:
        return f"🌡️ It will be very hot at {temp:.1f}°C - be careful and take frequent breaks"

def interpret_rainfall(rainfall: float) -> str:
    """Interpret rainfall and return description."""
    if rainfall == 0:
        return f"🌤️ There's no rain expected - you'll have perfect weather for your visit"
    elif rainfall < 2:
        return f"☔ There might be light drizzle around {rainfall:.1f}mm, but it shouldn't affect your visit much"
    elif rainfall < 5:
        return f"🌧️ Some light rain is possible, around {rainfall:.1f}mm - bring an umbrella but you can still visit"
    elif rainfall < 10:
        return f"⛈️ Moderate rain is expected around {rainfall:.1f}mm - you'll want waterproof gear"
    elif rainfall < 20:
        return f"🌧️ Heavy rain is expected around {rainfall:.1f}mm - the rock might be slippery for climbing"
    else:
        return f"Very heavy rain is forecast around {rainfall:.1f}mm - it won't be ideal for climbing"

def interpret_wind(wind: float) -> str:
    """Interpret wind speed and return description."""
    if wind < 2:
        return f"💨 The wind will be calm at {wind:.1f}m/s - perfect conditions for climbing"
    elif wind < 5:
        return f"🌬️ There will be a light breeze at {wind:.1f}m/s - pleasant wind, comfortable for activities"
    elif wind < 10:
        return f"💨 The wind will be moderate at {wind:.1f}m/s - noticeable but manageable for climbing"
    elif wind < 15:
        return f"🌪️ It will be quite windy at {wind:.1f}m/s - you'll need to hold onto the rock carefully"
    else:
        return f"🌪️ The wind will be very strong at {wind:.1f}m/s - be cautious and careful when climbing"

def should_recommend_visit(temp: float, rainfall: float, wind: float) -> str:
    """Overall recommendation based on all weather factors."""
    score = 0
    
    # Temperature scoring (20-26°C is ideal)
    if 20 <= temp <= 26:
        score += 3
    elif 18 <= temp <= 30:
        score += 2
    elif 15 <= temp <= 35:
        score += 1
    
    # Rainfall scoring (less is better)
    if rainfall == 0:
        score += 3
    elif rainfall < 5:
        score += 2
    elif rainfall < 10:
        score += 1
    
    # Wind scoring (less is better for climbing)
    if wind < 5:
        score += 3
    elif wind < 10:
        score += 2
    elif wind < 15:
        score += 1
    
    if score >= 8:
        return "✨ Overall, it looks like an excellent day to visit Sigiriya. All conditions are just perfect!"
    elif score >= 6:
        return "👍 It looks like a good day to visit Sigiriya. The conditions should be favorable."
    elif score >= 4:
        return "⚠️ The conditions are moderate - you can visit, but be prepared for some challenges."
    else:
        return "❌ It's not the ideal day to visit. You might want to consider another day if possible."

def format_rain_status(rainfall: float) -> str:
    """Direct answer to 'will it rain' type questions."""
    if rainfall == 0:
        return f"🌤️ No rain is expected - you'll have clear, dry weather for your visit."
    elif rainfall < 2:
        return f"☔ There might be minimal rain, around {rainfall:.1f}mm - it shouldn't affect your plans much."
    elif rainfall < 5:
        return f"🌧️ Light rain is possible, around {rainfall:.1f}mm - bring an umbrella just in case."
    elif rainfall < 10:
        return f"⛈️ Moderate rain is expected, around {rainfall:.1f}mm - waterproof gear would be a good idea."
    else:
        return f"🌧️ Heavy rain is expected, around {rainfall:.1f}mm - it might not be the best day for visiting."

def format_sunny_status(rainfall: float, temp: float) -> str:
    """Direct answer to 'will it be sunny/clear' type questions."""
    if rainfall == 0 and temp >= 20:
        return f"☀️ Yes, it should be clear and sunny with a temperature around {temp:.1f}°C and no rain expected."
    elif rainfall == 0:
        return f"🌤️ Yes, the skies should be clear, though it'll be cool at {temp:.1f}°C - bring a light jacket."
    elif rainfall < 2:
        return f"⛅ Mostly sunny with just minimal rain around {rainfall:.1f}mm - should be a great day!"
    else:
        return f"🌥️ It will be mixed - some clouds and rain around {rainfall:.1f}mm expected, but still visitable."

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

class WeatherHandler:
    def __init__(self):
        self.year = 2026
        # Use current system date, but ensure it's in 2026
        now = datetime.datetime.now()
        if now.year == 2026:
            self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Fallback if not in 2026 (for testing), use actual current date in 2026 context
            self.today = datetime.datetime(2026, now.month, now.day)
    
    def parse_date(self, query: str) -> Optional[datetime.datetime]:
        """Parse dates from query"""
        q = query.lower()
        
        # Check for natural language dates first
        if 'today' in q:
            return self.today
        if 'tomorrow' in q or 'next day' in q:
            return self.today + datetime.timedelta(days=1)
        
        # Try YYYY-MM-DD format
        match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', q)
        if match:
            try:
                y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if y == 2026 and 1 <= m <= 12 and 1 <= d <= 31:
                    return datetime.datetime(2026, m, d)
            except:
                pass
        
        # Try DD/MM/YYYY format
        match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', q)
        if match:
            try:
                d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if y == 2026 and 1 <= m <= 12 and 1 <= d <= 31:
                    return datetime.datetime(2026, m, d)
            except:
                pass
        
        # Try "29th July" or "July 29" format
        for month_name, month_num in MONTHS.items():
            # Match "July 29" or "29 July" with optional ordinal suffix
            pattern1 = r'(\d{1,2})(?:st|nd|rd|th)?\s+' + month_name
            pattern2 = month_name + r'\s+(\d{1,2})(?:st|nd|rd|th)?'
            for pattern in [pattern1, pattern2]:
                match = re.search(pattern, q, re.IGNORECASE)
                if match:
                    try:
                        day = int(match.group(1))
                        if 1 <= day <= 31:
                            return datetime.datetime(2026, month_num, day)
                    except:
                        pass
        
        return None
    
    def parse_dynamic_date(self, query: str) -> Optional[datetime.datetime]:
        """Parse relative dates like 'next Monday', 'this Friday', etc"""
        q = query.lower()
        
        # Days of week
        days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_offsets = {day: i for i, day in enumerate(days_of_week)}
        
        today = self.today
        current_weekday = today.weekday()
        
        for day_name, day_offset in day_offsets.items():
            if day_name in q:
                days_ahead = day_offset - current_weekday
                
                # "this [day]" - could be today or this week
                if 'this' in q and days_ahead <= 0:
                    days_ahead += 7
                # "next [day]"
                elif 'next' in q:
                    days_ahead += 7
                # Just the day name without "this" or "next" - look ahead
                elif days_ahead < 0:
                    days_ahead += 7
                
                target_date = today + datetime.timedelta(days=days_ahead)
                if target_date.year == 2026:
                    return target_date
        
        return None
    
    def parse_month(self, query: str) -> Optional[int]:
        """Extract month from query"""
        q = query.lower()
        for month_name, month_num in MONTHS.items():
            if month_name in q:
                return month_num
        return None
    
    def get_month_dates(self, month: int) -> List[datetime.datetime]:
        """Get all dates in a specific month"""
        dates = []
        day = 1
        while True:
            try:
                dates.append(datetime.datetime(2026, month, day))
                day += 1
            except ValueError:
                break
        return dates
    
    def detect_param(self, query: str) -> str:
        """Detect which weather parameter is being asked about"""
        q = query.lower()
        if any(w in q for w in ['temp', 'temperature', 'hot', 'warm', 'degree', 'celsius', 'how hot', 'how warm']):
            return 'temperature'
        if any(w in q for w in ['rain', 'rainfall', 'wet', 'precipitation', 'how much rain']):
            return 'rainfall'
        if any(w in q for w in ['wind', 'breeze', 'speed', 'windy']):
            return 'wind'
        return 'all'
    
    def parse_week_range(self, query: str) -> list:
        """Extract week range from query like 'first week', 'second week', etc"""
        q = query.lower()
        
        # Handle "first week of [month]", "second week of [month]", etc
        week_patterns = [
            (r'first week of (\w+)', 1),
            (r'second week of (\w+)', 2),
            (r'third week of (\w+)', 3),
            (r'last week of (\w+)', -1),
        ]
        
        for pattern, week_num in week_patterns:
            match = re.search(pattern, q)
            if match:
                month_name = match.group(1)
                if month_name in MONTHS:
                    month = MONTHS[month_name]
                    if week_num == -1:  # last week
                        dates = self.get_month_dates(month)
                        return dates[-7:] if dates else []
                    else:
                        dates = self.get_month_dates(month)
                        start_idx = (week_num - 1) * 7
                        end_idx = start_idx + 7
                        return dates[start_idx:end_idx]
        
        # Handle "this week" - current week starting from today
        if 'this week' in q:
            today = self.today
            # Get start of week (Monday)
            start = today - datetime.timedelta(days=today.weekday())
            return [start + datetime.timedelta(days=i) for i in range(7)]
        
        # Handle "next week"
        if 'next week' in q:
            today = self.today
            # Get start of next week (next Monday)
            start = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=7)
            return [start + datetime.timedelta(days=i) for i in range(7)]
        
        return []
    
    def parse_next_month(self, query: str) -> Optional[int]:
        """Extract 'next month' from query"""
        q = query.lower()
        
        if 'next month' in q:
            # Current date is March 1, 2026, so next month is April (month 4)
            current_month = self.today.month
            next_month = current_month + 1
            if next_month > 12:
                next_month = 1
            return next_month
        
        return None
    
    def _is_hourly_query(self, query: str) -> bool:
        """Check if query is asking about hourly/real-time weather."""
        q = query.lower()
        # Exclude "current weather" from hourly queries
        if 'current weather' in q and not any(x in q for x in ['next', 'this hour', 'now']):
            return False
        hourly_keywords = [
            'next hour', 'this hour', 'current hour', 'now',
            'right now', 'current weather', 'real-time',
            'realtime', 'latest weather', 'next few hours',
            'hourly', 'per hour', 'every hour', 'forecast next hour'
        ]
        return any(keyword in q for keyword in hourly_keywords)
    
    def _get_today_weather_forecast(self) -> str:
        """Get today's weather from forecast data (not API)."""
        try:
            today_weather = get_weather_dict_for_dates([self.today])
            if today_weather:
                d = today_weather[0]
                return (f"📍 **Today's Weather in Sigiriya**\n"
                       f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"{interpret_temperature(d['temperature_celsius'])}\n"
                       f"{interpret_rainfall(d['rainfall_mm'])}\n"
                       f"{interpret_wind(d['wind_speed_ms'])}\n"
                       f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"{should_recommend_visit(d['temperature_celsius'], d['rainfall_mm'], d['wind_speed_ms'])}")
            else:
                return "Unable to fetch today's weather forecast."
        except Exception as e:
            return "Unable to fetch today's weather forecast."
    
    def _get_current_weather(self, query: str) -> str:
        """Get current weather conditions using forecast data (removed API dependency)."""
        try:
            # Get today's forecasted weather instead of real-time API
            today_weather = get_weather_dict_for_dates([self.today])
            if today_weather:
                d = today_weather[0]
                return (f"📍 **Current Weather Forecast in Sigiriya**\n"
                       f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"{interpret_temperature(d['temperature_celsius'])}\n"
                       f"{interpret_rainfall(d['rainfall_mm'])}\n"
                       f"{interpret_wind(d['wind_speed_ms'])}\n"
                       f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"{should_recommend_visit(d['temperature_celsius'], d['rainfall_mm'], d['wind_speed_ms'])}")
            else:
                return "Unable to fetch weather forecast."
        except Exception as e:
            return "Unable to fetch weather forecast. Please try asking about a specific date."

    
    def _find_best_day(self, query: str) -> str:
        """Find the best day to visit based on weather conditions."""
        try:
            today = self.today
            best_score = -1
            best_date = None
            best_weather = None
            
            # Check next 7 days
            for i in range(7):
                check_date = today + datetime.timedelta(days=i)
                if check_date.year > 2026 or (check_date.year == 2026 and check_date > datetime.datetime(2026, 12, 31)):
                    break
                
                try:
                    weather_data = get_weather_dict_for_dates([check_date])
                    if weather_data:
                        d = weather_data[0]
                        temp = d['temperature_celsius']
                        rainfall = d['rainfall_mm']
                        wind = d['wind_speed_ms']
                        
                        score = 0
                        if 20 <= temp <= 26:
                            score += 3
                        elif 18 <= temp <= 30:
                            score += 2
                        elif 15 <= temp <= 35:
                            score += 1
                        
                        if rainfall == 0:
                            score += 3
                        elif rainfall < 5:
                            score += 2
                        elif rainfall < 10:
                            score += 1
                        
                        if wind < 5:
                            score += 3
                        elif wind < 10:
                            score += 2
                        elif wind < 15:
                            score += 1
                        
                        if score > best_score:
                            best_score = score
                            best_date = check_date
                            best_weather = (temp, rainfall, wind)
                except:
                    continue
            
            if best_date and best_weather:
                date_str = best_date.strftime('%B %d (%A)')
                temp, rainfall, wind = best_weather
                recommendation = should_recommend_visit(temp, rainfall, wind)
                return (f"✓ Best day to visit: {date_str}\n"
                       f"🌡 {temp:.1f}°C | 💧 {rainfall:.1f}mm | 💨 {wind:.1f}m/s\n"
                       f"{recommendation}")
            
            return "Unable to determine best day."
        except:
            return "Error finding best day to visit."
    
    def _get_week_forecast(self, query: str) -> str:
        """Get week forecast summary."""
        try:
            today = self.today
            week_dates = [today + datetime.timedelta(days=i) for i in range(7)]
            
            weather_data = get_weather_dict_for_dates(week_dates)
            if not weather_data:
                return "No week forecast available."
            
            temps = [d['temperature_celsius'] for d in weather_data if 'temperature_celsius' in d]
            rains = [d['rainfall_mm'] for d in weather_data if 'rainfall_mm' in d]
            winds = [d['wind_speed_ms'] for d in weather_data if 'wind_speed_ms' in d]
            
            response = f"📅 Week Forecast ({today.strftime('%b %d')} - {week_dates[-1].strftime('%b %d')})\n"
            response += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for i, date in enumerate(week_dates):
                if i < len(weather_data):
                    d = weather_data[i]
                    day_str = date.strftime('%a')
                    temp = d.get('temperature_celsius', 0)
                    rain = d.get('rainfall_mm', 0)
                    wind = d.get('wind_speed_ms', 0)
                    
                    rain_icon = "🌧" if rain > 5 else "☔" if rain > 0 else "✓"
                    response += f"{day_str}: 🌡{temp:.0f}°C | 💧{rain:.0f}mm {rain_icon} | 💨{wind:.1f}m/s\n"
            
            if temps and rains:
                avg_temp = sum(temps) / len(temps)
                total_rain = sum(rains)
                response += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                response += f"Avg: 🌡{avg_temp:.1f}°C | Total Rain: 💧{total_rain:.1f}mm"
            
            return response
        except Exception as e:
            return "Error fetching week forecast."
    
    def _get_hourly_weather_response(self, query: str) -> str:
        """Get real-time hourly weather data from OpenWeatherMap API."""
        if not get_hourly_weather:
            # Fallback if OpenWeatherMap integration not available
            return "⏰ Real-time weather data temporarily unavailable. Try asking about weather for a specific date!"
        
        try:
            import pytz
            from datetime import datetime
            
            # Get current time in Sri Lanka timezone
            sri_lanka_tz = pytz.timezone('Asia/Colombo')
            now_sl = datetime.now(sri_lanka_tz)
            
            # Check if asking for "next hour" specifically
            q = query.lower()
            is_next_hour_only = any(phrase in q for phrase in ['next hour', 'next 1 hour', 'weather next hour'])
            
            # Get hourly data (next 24 hours to ensure we have data)
            hourly_data = get_hourly_weather(hours=24)
            
            if not hourly_data:
                return "⏰ Unable to fetch real-time weather. Please try again!"
            
            # Filter to get only future times (times after current time)
            future_data = [h for h in hourly_data if h['datetime'] > now_sl]
            
            if not future_data:
                return "⏰ No future hourly data available"
            
            # If asking for "next hour", show only the next hour's data
            if is_next_hour_only:
                future_data = future_data[:1]
                header = "🕐 **Weather for Next Hour in Sigiriya**"
            else:
                # Otherwise show next 4 hours
                future_data = future_data[:4]
                header = "🕐 **Real-Time Hourly Weather for Sigiriya**"
            
            # Format the data for display
            formatted = format_hourly_for_display(future_data)
            
            if not formatted:
                return "No hourly data available"
            
            # If asking for "next hour", show compact single line format with emojis
            if is_next_hour_only:
                hour = formatted[0]
                response = f"⏰ {hour['time']} | 🌡 {hour['temp']} ({hour['temp_description']}) | ☁ {hour['description']}\n"
                response += f"💧 {hour['rainfall']} ({hour['rainfall_description']}) | 💨 {hour['wind_speed']} ({hour['wind_description']}) | 💧 Humidity: {hour['humidity']}\n"
                response += f"✓ {hour['recommendation']}\n"
                response += f"🔄 {now_sl.strftime('%I:%M %p')}"
                return response
            
            # Build response for multiple hours
            response = f"{header}\n"
            response += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Show the forecast hours
            for i, hour in enumerate(formatted):
                response += f"⏰ {hour['time']} ({hour['date']})\n"
                response += f"🌡 Temperature: {hour['temp']} ({hour['temp_description']})\n"
                response += f"☁ Condition: {hour['description']}\n"
                response += f"💧 Rainfall: {hour['rainfall']} ({hour['rainfall_description']})\n"
                response += f"💨 Wind: {hour['wind_speed']} ({hour['wind_description']})\n"
                response += f"💧 Humidity: {hour['humidity']} | ☁ Clouds: {hour['clouds']}\n"
                response += f"✓ Recommendation: {hour['recommendation']}\n"
                
                if i < len(formatted) - 1:  # Add separator between hours (not after last one)
                    response += "──────────────────────────────────\n"
            
            # Keep only the updated timestamp
            response += "\n🔄 Updated: " + now_sl.strftime('%I:%M %p') + "\n"
            
            return response
            
        except Exception as e:
            return f"⏰ Error fetching real-time weather: {str(e)}\nPlease try asking about weather for a specific date!"
    
    def handle_query(self, query: str) -> str:
        """Main handler for weather queries - prioritizes trained model data"""
        q = query.lower()
        
        # Year validation
        if any(y in q for y in ['2025', '2027', '2028', '2029', '2030', '2031']):
            return "I have weather forecasts available for 2026 only. Could you ask about a date in 2026?"
        
        # Weather keyword validation (allow visit/day queries for tourism context)
        if not any(w in q for w in ['weather', 'temperature', 'temp', 'rain', 'rainfall', 'wind', 'forecast', 'climate', 'hot', 'cold', 'warm', 'windy', 'sunny', 'clear', 'cloud', 'sky', 'visit', 'day', 'best', 'now']):
            return "I can help you with weather questions! You can ask me about temperature, rainfall, wind conditions, forecasts, and the best days to visit Sigiriya."
        
        # ============================================================
        # PRIORITY 1: TODAY/NOW WEATHER (use trained forecast data)
        # ============================================================
        if any(phrase in q for phrase in ['today weather', 'weather today', 'weather for today', 'weather now', 'now', 'right now', 'at the moment', 'current weather', 'today\'s weather', 'how\'s the weather']):
            return self._get_today_weather_forecast()
        
        # ============================================================
        # PRIORITY 2: HOURLY/NEXT HOUR (use API - OpenWeatherMap)
        # ============================================================
        if any(phrase in q for phrase in ['next hour', 'this hour', 'current hour', 'hourly', 'per hour', 'weather next hour', 'forecast next hour']):
            return self._get_hourly_weather_response(query)
        
        if self._is_hourly_query(q):
            return self._get_hourly_weather_response(query)
        
        # ============================================================
        # PRIORITY 3: BEST DAY/WEEK/MONTH (use trained forecast data)
        # ============================================================
        if any(phrase in q for phrase in ['best day', 'best weather', 'ideal day', 'perfect day', 'worst day', 'worst weather']):
            return self._find_best_day(query)
        
        if any(phrase in q for phrase in ['this week', 'next week', 'weekly forecast', 'week ahead', 'weather this week', 'weather next week']):
            return self._get_week_forecast(query)
        
        # ============================================================
        # PRIORITY 4: SPECIFIC DATE (use trained forecast data)
        # ============================================================
        max_date = datetime.datetime(2026, 12, 31)
        
        # Try to parse specific date
        date = self.parse_date(query)
        if date and date.year == 2026:
            if date > max_date:
                return f"⏰ Weather forecast available only through Dec 31, 2026.\n📅 Please choose an earlier date!"
            return self._format_weather_response_for_date(date, query)
        
        # Try dynamic date (next Monday, this Friday, etc)
        dynamic_date = self.parse_dynamic_date(query)
        if dynamic_date and dynamic_date.year == 2026:
            if dynamic_date > max_date:
                return f"⏰ Weather forecast available only through Dec 31, 2026.\n📅 Please choose an earlier date!"
            return self._format_weather_response_for_date(dynamic_date, query)
        
        # ============================================================
        # PRIORITY 5: WEEK RANGE (use trained forecast data)
        # ============================================================
        week_dates = self.parse_week_range(query)
        if week_dates:
            try:
                weather_data = get_weather_dict_for_dates(week_dates)
                if weather_data and len(weather_data) > 0:
                    return self._format_week_summary(weather_data, week_dates, query)
            except Exception as e:
                pass
        
        # ============================================================
        # PRIORITY 6: MONTH RANGE (use trained forecast data)
        # ============================================================
        month = self.parse_next_month(query)
        if month:
            month_dates = self.get_month_dates(month)
            if month_dates:
                return self._format_month_summary(month_dates, month, query)
        
        return "I can help with weather information. Try asking me about a specific date, the upcoming week, or a particular month in 2026. For example, 'What's the weather like on March 15?' or 'Will it rain next week?'"
    
    def _format_weather_response_for_date(self, date: datetime.datetime, query: str) -> str:
        """Format weather response for a specific date using trained model data."""
        try:
            weather_data = get_weather_dict_for_dates([date])
            if not weather_data or len(weather_data) == 0:
                return f"I don't have weather data for {date.strftime('%B %d, %Y')}. Could you try another date?"
            
            d = weather_data[0]
            date_str = date.strftime('%B %d, %Y (%A)')
            temp = d['temperature_celsius']
            rainfall = d['rainfall_mm']
            wind = d['wind_speed_ms']
            q = query.lower()
            
            # Check for specific parameter requests
            if 'rain' in q or 'rainfall' in q or 'precipit' in q:
                return f"On {date_str}, here's the rain forecast: {format_rain_status(rainfall)} Expected rainfall is {rainfall:.1f}mm."
            
            if 'sunny' in q or 'clear' in q or 'sky' in q:
                return f"On {date_str}, the sky conditions will be: {format_sunny_status(rainfall, temp)}"
            
            if 'cloud' in q:
                cloud_status = "It will be quite cloudy" if rainfall > 5 else "There will be some clouds" if rainfall > 2 else "It should be mostly clear and sunny"
                return f"On {date_str}, {cloud_status}."
            
            if 'cold' in q or 'freeze' in q:
                return f"The temperature on {date_str} will be: {interpret_temperature(temp)}"
            
            if 'hot' in q or 'heat' in q or 'warm' in q:
                return f"The temperature on {date_str} will be: {interpret_temperature(temp)}"
            
            if 'temperature' in q or 'temp' in q or 'degree' in q or 'celsius' in q:
                return f"The temperature on {date_str} will be: {interpret_temperature(temp)}"
            
            if 'wind' in q or 'windy' in q or 'breeze' in q or 'gust' in q:
                return f"The wind conditions on {date_str}: {interpret_wind(wind)}"
            
            # Default: show complete weather with recommendation
            return f"Here's the weather forecast for {date_str}:\n\n{interpret_temperature(temp)}\n{interpret_rainfall(rainfall)}\n{interpret_wind(wind)}\n\n{should_recommend_visit(temp, rainfall, wind)}"
        
        except Exception as e:
            return f"I'm sorry, I couldn't fetch the weather for {date.strftime('%B %d, %Y')}. Please try again!"
    
    def _format_week_summary(self, weather_data: list, dates: list, query: str) -> str:
        """Format weather summary for a week using trained model data."""
        try:
            q = query.lower()
            
            temps = [d['temperature_celsius'] for d in weather_data]
            rainfalls = [d['rainfall_mm'] for d in weather_data]
            winds = [d['wind_speed_ms'] for d in weather_data]
            
            avg_temp = sum(temps) / len(temps)
            total_rain = sum(rainfalls)
            rainy_days = sum(1 for r in rainfalls if r > 2)
            sunny_days = sum(1 for r in rainfalls if r == 0)
            
            # Find best day (least rain, comfortable temp)
            best_day_idx = min(range(len(dates)), key=lambda i: (rainfalls[i], abs(temps[i] - 25)))
            best_day = dates[best_day_idx].strftime('%A')
            
            week_label = "this week" if 'this week' in q else "next week" if 'next week' in q else "the week"
            
            response = f"Here's the weather forecast for {week_label}:\n\n"
            response += f"Average temperature will be around {avg_temp:.0f}°C, with "
            
            if total_rain < 5:
                response += "minimal rain expected - perfect for visiting!"
            elif total_rain < 15:
                response += "some light rain on a couple of days."
            else:
                response += "moderate rainfall throughout the week."
            
            response += f"\n\nYou'll have {sunny_days} completely clear days and {rainy_days} rainy days. "
            response += f"The best day to visit would be {best_day}, when conditions look ideal."
            
            return response.strip()
        except Exception as e:
            return "I'm sorry, I couldn't fetch the weekly forecast. Please try again!"
    
    def _format_month_summary(self, dates: list, month: int, query: str) -> str:
        """Format weather summary for a month using trained model data."""
        try:
            if not dates:
                return f"I don't have weather data available for that month."
            
            weather_data = get_weather_dict_for_dates(dates)
            
            month_name = datetime.datetime(2026, month, 1).strftime('%B')
            
            if weather_data:
                temps = [d['temperature_celsius'] for d in weather_data]
                rainfalls = [d['rainfall_mm'] for d in weather_data]
                winds = [d['wind_speed_ms'] for d in weather_data]
                
                avg_temp = sum(temps) / len(temps)
                total_rain = sum(rainfalls)
                rainy_days = sum(1 for r in rainfalls if r > 2)
                sunny_days = len(dates) - rainy_days
                
                response = f"Here's what to expect in {month_name} 2026:\n\n"
                response += f"The average temperature will be around {avg_temp:.0f}°C, ranging from {min(temps):.0f}°C to {max(temps):.0f}°C. "
                
                if total_rain < 20:
                    response += "You can expect relatively dry conditions with minimal rainfall."
                elif total_rain < 60:
                    response += "There will be moderate rainfall throughout the month."
                else:
                    response += "It will be a quite wet month with significant rainfall."
                
                response += f"\n\nYou'll have about {sunny_days} clear days and {rainy_days} days with rain. "
                response += f"Overall, {month_name} looks " + ("excellent" if total_rain < 30 else "good" if total_rain < 60 else "challenging") + " for visiting Sigiriya."
                
                return response.strip()
            
            return f"I couldn't fetch the weather data for {month_name}. Please try again!"
        except Exception as e:
            return f"I couldn't fetch the weather for {month_name}. Please try again!"
        
_handler = WeatherHandler()

def get_weather_response(query: str) -> str:
    """Public API to get weather response"""
    # Check location validation first
    should_reject, error_message = should_reject_query(query)
    if should_reject:
        return error_message
    
    return _handler.handle_query(query)
