import joblib
import pandas as pd
from datetime import datetime, timedelta

# Load trained models
temp_model = joblib.load("../models/temp.pkl")
rain_model = joblib.load("../models/rain.pkl")
wind_model = joblib.load("../models/wind.pkl")

def sri_lanka_season(month):
    if month in [5,6,7,8,9]:
        return 1
    elif month in [12,1,2]:
        return 2
    elif month in [3,4]:
        return 3
    else:
        return 4

def weather_type(rain, wind):
    if rain > 15:
        return "Heavy Rain 🌧️"
    elif rain > 3:
        return "Light Rain 🌦️"
    elif wind > 5:
        return "Windy 🌬️"
    else:
        return "Clear ☀️"

def get_weather_for_dates(dates):
    """Return weather info for a list of datetime dates."""
    X = pd.DataFrame({
        'dayofweek': [d.weekday() for d in dates],
        'month': [d.month for d in dates],
        'day': [d.day for d in dates],
        'season': [sri_lanka_season(d.month) for d in dates]
    })

    temps = temp_model.predict(X)
    rains = rain_model.predict(X)
    winds = wind_model.predict(X)

    response = ""
    for i, d in enumerate(dates):
        response += (
            f"{d.date()} (Day {i+1}): "
            f"{round(temps[i],1)}°C, "
            f"{weather_type(rains[i], winds[i])}, "
            f"Wind {round(winds[i],1)} m/s\n"
        )
    return response.strip()


class WeatherChatbot:
    """A simple chatbot for weather questions."""
    
    def answer_question(self, question):
        question_lower = question.lower()
        today = datetime.today()
        
        # Specific date question
        if "on" in question_lower:
            try:
                # Extract date in YYYY-MM-DD format
                for word in question_lower.split():
                    if "-" in word:
                        d = datetime.strptime(word, "%Y-%m-%d")
                        return get_weather_for_dates([d])
            except:
                return "Sorry, I couldn't understand the date format. Use YYYY-MM-DD."
        
        # General weather questions
        if "weather" in question_lower or "temperature" in question_lower:
            return get_weather_for_dates([today])
        
        if "rain" in question_lower:
            return get_weather_for_dates([today])
        
        if "wind" in question_lower:
            return get_weather_for_dates([today])
        
        return "Sorry, I can only answer questions about weather in Sigiriya."

