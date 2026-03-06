import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import joblib
import os

weather_path = '/Users/pavithrameddaduwage/sigiriya-weather-forecast/data/sigiriya_weather.csv'
models_path = '/Users/pavithrameddaduwage/sigiriya-weather-forecast/data/models'

def load_weather(path):
    df = pd.read_csv(path)
    df['ds'] = pd.to_datetime(df['dt_iso'].str.replace(' UTC','', regex=False))
    df['y'] = df['temp']
    df_daily = df.resample('D', on='ds').mean().reset_index()
    return df_daily[['ds','y']]

weather = load_weather(weather_path)

weather_model = Prophet()
weather_model.fit(weather)

future_weather = weather_model.make_future_dataframe(periods=365)
forecast_weather = weather_model.predict(future_weather)

plt.figure(figsize=(12,6))
plt.plot(weather['ds'], weather['y'], label='Historical Temp')
plt.plot(forecast_weather['ds'], forecast_weather['yhat'], label='Forecast Temp')
plt.legend()
plt.show()

def get_weather_forecast(date):
    row = forecast_weather[forecast_weather['ds'] == pd.to_datetime(date)]
    return float(row['yhat']) if not row.empty else None

def create_crowd_features(date):
    """Create features for XGBoost crowd prediction model."""
    features = {
        'month': date.month,
        'is_weekend': 1 if date.weekday() >= 5 else 0,
        'peak_season_flag': 1 if date.month in [1, 7, 8, 12] else 0,
        'holiday_flag': 0,
        'day_of_year': date.timetuple().tm_yday,
        'week_of_year': date.isocalendar()[1],
        'quarter': (date.month - 1) // 3 + 1,
        'lag_1': 300,  # Default values
        'lag_7': 300,
        'rolling_mean_7': 300
    }
    return features

def get_crowd_daily_forecast(date):
    """Get crowd prediction for a specific date using XGBoost model."""
    try:
        model = joblib.load(os.path.join(models_path, "best_sigiriya_model.pkl"))
    except:
        # Fallback path
        model = joblib.load("../models/best_sigiriya_model.pkl")
    
    features = create_crowd_features(date)
    feature_columns = [
        'month', 'is_weekend', 'peak_season_flag', 'holiday_flag',
        'day_of_year', 'week_of_year', 'quarter',
        'lag_1', 'lag_7', 'rolling_mean_7'
    ]
    
    df = pd.DataFrame([features])
    prediction = model.predict(df[feature_columns])[0]
    return float(prediction)

def get_crowd_weekly_forecast(date):
    """Predict weekly crowd by aggregating daily predictions for 7 days."""
    weekly_total = 0
    for i in range(7):
        future_date = date + timedelta(days=i)
        daily_pred = get_crowd_daily_forecast(future_date)
        weekly_total += daily_pred
    
    return float(weekly_total / 7)  # Return average

def get_crowd_yearly_forecast(year):
    """Predict yearly crowd by aggregating all daily predictions for the year."""
    yearly_total = 0
    start_date = datetime(year, 1, 1)
    
    # Aggregate for full year (or until end of year)
    for i in range(365):
        current_date = start_date + timedelta(days=i)
        if current_date.year > year:
            break
        daily_pred = get_crowd_daily_forecast(current_date)
        yearly_total += daily_pred
    
    return float(yearly_total)

# Plot functions for visualization
def plot_crowd_forecast():
    """Plot crowd forecasts for visualization."""
    dates = pd.date_range(start="2026-01-01", end="2026-12-31")
    daily_predictions = []
    
    for date in dates:
        pred = get_crowd_daily_forecast(date)
        daily_predictions.append(pred)
    
    df = pd.DataFrame({
        'date': dates,
        'daily': daily_predictions
    })
    
    # Calculate 7-day rolling average
    df['weekly_avg'] = df['daily'].rolling(window=7, center=True).mean()
    
    plt.figure(figsize=(14,6))
    plt.plot(df['date'], df['daily'], label='Daily Arrivals', alpha=0.5)
    plt.plot(df['date'], df['weekly_avg'], label='7-Day Average', linewidth=2)
    plt.title('Crowd Forecast for 2026 (XGBoost Model)')
    plt.xlabel('Date')
    plt.ylabel('Expected Visitors')
    plt.legend()
    plt.tight_layout()
    plt.show()
