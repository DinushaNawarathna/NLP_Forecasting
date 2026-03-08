import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

with open('../models/temp.pkl','rb') as f:
    temp_model = pickle.load(f)
with open('../models/rain.pkl','rb') as f:
    rain_model = pickle.load(f)
with open('../models/wind.pkl','rb') as f:
    wind_model = pickle.load(f)
with open('../models/best_sigiriya_model.pkl','rb') as f:
    crowd_model = pickle.load(f)

def predict_weather(date):
    df = pd.DataFrame({'ds':[date]})
    temp = temp_model.predict(df)['yhat'].values[0]
    rain = rain_model.predict(df)['yhat'].values[0]
    wind = wind_model.predict(df)['yhat'].values[0]
    return temp, rain, wind

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

def predict_crowd_daily(date):
    """Predict daily crowd using XGBoost model with feature engineering."""
    features = create_crowd_features(date)
    feature_columns = [
        'month', 'is_weekend', 'peak_season_flag', 'holiday_flag',
        'day_of_year', 'week_of_year', 'quarter',
        'lag_1', 'lag_7', 'rolling_mean_7'
    ]
    df = pd.DataFrame([features])
    arrivals = crowd_model.predict(df[feature_columns])[0]
    return arrivals

def predict_crowd_weekly(date):
    """
    Predict weekly crowd by aggregating daily predictions for 7 days.
    """
    weekly_total = 0
    for i in range(7):
        future_date = date + timedelta(days=i)
        daily_pred = predict_crowd_daily(future_date)
        weekly_total += daily_pred
    return weekly_total / 7  # Return average

def final_prediction(date):
    temp, rain, wind = predict_weather(date)
    arrivals_daily = predict_crowd_daily(date)
    arrivals_weekly = predict_crowd_weekly(date)
    return f"Prediction for {date}:\nWeather → Temp: {temp:.1f}°C, Rain: {rain:.1f}mm, Wind: {wind:.1f}m/s\n" \
           f"Tourist Arrivals → Daily: {int(arrivals_daily)}, Weekly Average: {int(arrivals_weekly)}"

def plot_monthly_crowd(start_date, end_date):
    """Plot monthly crowd predictions using the new XGBoost model."""
    dates = pd.date_range(start=start_date, end=end_date)
    daily_predictions = []
    
    for date in dates:
        pred = predict_crowd_daily(date)
        daily_predictions.append(pred)
    
    df = pd.DataFrame({
        'date': dates,
        'daily': daily_predictions
    })
    
    # Calculate 7-day rolling average for trend
    df['weekly_avg'] = df['daily'].rolling(window=7, center=True).mean()
    
    plt.figure(figsize=(12,6))
    plt.plot(df['date'], df['daily'], label='Daily Arrivals', marker='o', alpha=0.5)
    plt.plot(df['date'], df['weekly_avg'], label='7-Day Average', linewidth=2)
    plt.title(f'Tourist Arrivals {start_date} to {end_date}')
    plt.xticks(rotation=45)
    plt.xlabel('Date')
    plt.ylabel('Arrivals')
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    test_date = datetime.strptime('2026-02-15', '%Y-%m-%d')
    print(final_prediction(test_date))
    plot_monthly_crowd('2026-02-01', '2026-02-28')
