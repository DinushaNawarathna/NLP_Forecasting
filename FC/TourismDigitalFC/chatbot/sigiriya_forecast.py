import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from prophet import Prophet
from sklearn.ensemble import GradientBoostingRegressor
import joblib

# =========================
# Paths
# =========================
data_path = "/Users/pavithrameddaduwage/sigiriya-weather-forecast/data"
models_path = os.path.join(data_path, "models")
os.makedirs(models_path, exist_ok=True)

crowd_daily_file = os.path.join(data_path, "crowd_yearly.csv")
crowd_weekly_file = os.path.join(data_path, "crowd_weekly.csv")
weather_file = os.path.join(data_path, "sigiriya_weather.csv")

# =========================
# Sri Lanka season mapping
# =========================
def sri_lanka_season(month):
    if month in [5,6,7,8,9]:
        return 1  # Southwest monsoon
    elif month in [12,1,2]:
        return 2  # Northeast monsoon
    elif month in [3,4]:
        return 3  # First Inter-monsoon
    else:
        return 4  # Second Inter-monsoon

# =========================
# Weather type helper
# =========================
def weather_type(rain, wind):
    if rain > 15:
        return "Heavy Rain 🌧️"
    elif rain > 3:
        return "Light Rain 🌦️"
    elif wind > 5:
        return "Windy 🌬️"
    else:
        return "Clear ☀️"

# =========================
# Train Crowd Forecast Models
# =========================
def train_crowd_models():
    """
    Train XGBoost crowd prediction model using features from crowd.ipynb approach.
    This replaces the older Prophet-based models with a more accurate ML model.
    """
    # Load crowd data
    crowd_data_2023 = pd.read_csv(data_path + "/sigiriya_2023_crowd.csv")
    crowd_data_2024 = pd.read_csv(data_path + "/sigiriya_2024_crowd.csv")
    crowd_data_2025 = pd.read_csv(data_path + "/sigiriya_2025_crowd.csv")
    
    # Concatenate all data
    df = pd.concat([crowd_data_2023, crowd_data_2024, crowd_data_2025], ignore_index=True)
    
    # Parse datetime
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Feature engineering
    df['month'] = df['date'].dt.month
    df['is_weekend'] = (df['date'].dt.dayofweek >= 5).astype(int)
    df['peak_season_flag'] = df['month'].isin([1, 7, 8, 12]).astype(int)
    df['holiday_flag'] = 0  # Can be enhanced with actual holiday data
    df['day_of_year'] = df['date'].dt.dayofyear
    df['week_of_year'] = df['date'].dt.isocalendar().week.astype(int)
    df['quarter'] = df['date'].dt.quarter
    
    # Lag features
    df['lag_1'] = df['total_visitors_daily'].shift(1)
    df['lag_7'] = df['total_visitors_daily'].shift(7)
    df['rolling_mean_7'] = df['total_visitors_daily'].rolling(7).mean()
    
    # Drop rows with NaN values
    df = df.dropna()
    
    # Prepare features and target
    feature_columns = [
        'month', 'is_weekend', 'peak_season_flag', 'holiday_flag',
        'day_of_year', 'week_of_year', 'quarter',
        'lag_1', 'lag_7', 'rolling_mean_7'
    ]
    
    X = df[feature_columns]
    y = df['total_visitors_daily']
    
    # Train/test split
    split_index = int(len(df) * 0.8)
    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]
    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]
    
    # Train XGBoost model
    from xgboost import XGBRegressor
    model = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        random_state=42,
        n_jobs=2
    )
    
    model.fit(X_train, y_train)
    
    # Save model
    joblib.dump(model, os.path.join(models_path, "best_sigiriya_model.pkl"))
    
    print("✓ Crowd model (XGBoost) trained and saved.")
    return model

# =========================
# Train Weather Forecast Models
# =========================
def train_weather_models():
    df = pd.read_csv(weather_file)

    # Fix datetime parsing
    df['dt_iso'] = pd.to_datetime(
        df['dt_iso'],
        format='%Y-%m-%d %H:%M:%S +0000 UTC',
        errors='coerce'
    )
    df = df.dropna(subset=['dt_iso'])
    df = df.sort_values('dt_iso')
    df = df[['dt_iso','temp','rain_1h','humidity','wind_speed']]

    if df.empty:
        raise ValueError("No valid datetime rows found in sigiriya_weather.csv. Check dt_iso column.")

    # Fill missing values
    df['rain_1h'] = df['rain_1h'].fillna(0)
    df['humidity'] = df['humidity'].fillna(df['humidity'].mean())
    df['wind_speed'] = df['wind_speed'].fillna(df['wind_speed'].mean())

    df.set_index('dt_iso', inplace=True)

    # Daily aggregation
    daily = df.resample('D').agg({
        'temp':'mean',
        'rain_1h':'sum',
        'humidity':'mean',
        'wind_speed':'mean'
    })

    daily['dayofweek'] = daily.index.dayofweek
    daily['month'] = daily.index.month
    daily['day'] = daily.index.day
    daily['season'] = daily.index.month.map(sri_lanka_season)

    X = daily[['dayofweek','month','day','season']]
    y_temp = daily['temp']
    y_rain = daily['rain_1h']
    y_wind = daily['wind_speed']

    # Train Gradient Boosting Regressors
    gb_temp = GradientBoostingRegressor().fit(X, y_temp)
    gb_rain = GradientBoostingRegressor().fit(X, y_rain)
    gb_wind = GradientBoostingRegressor().fit(X, y_wind)

    # Save models
    joblib.dump(gb_temp, os.path.join(models_path,"temp.pkl"))
    joblib.dump(gb_rain, os.path.join(models_path,"rain.pkl"))
    joblib.dump(gb_wind, os.path.join(models_path,"wind.pkl"))

    print("Weather models trained and saved.")
    return gb_temp, gb_rain, gb_wind

# =========================
# Prediction helpers
# =========================
def predict_daily_crowd(date_str):
    """Predict daily crowd using XGBoost model with feature engineering."""
    from datetime import datetime as dt
    
    if isinstance(date_str, str):
        date = dt.strptime(date_str, "%Y-%m-%d")
    else:
        date = date_str
    
    model = joblib.load(os.path.join(models_path, "best_sigiriya_model.pkl"))
    
    # Create features
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
    
    feature_columns = [
        'month', 'is_weekend', 'peak_season_flag', 'holiday_flag',
        'day_of_year', 'week_of_year', 'quarter',
        'lag_1', 'lag_7', 'rolling_mean_7'
    ]
    
    X = pd.DataFrame([features])
    prediction = model.predict(X[feature_columns])[0]
    return float(prediction)

def predict_weekly_crowd(date_str):
    """Predict weekly crowd by aggregating daily predictions for 7 days."""
    from datetime import datetime as dt, timedelta
    
    if isinstance(date_str, str):
        date = dt.strptime(date_str, "%Y-%m-%d")
    else:
        date = date_str
    
    weekly_total = 0
    for i in range(7):
        future_date = date + timedelta(days=i)
        daily_pred = predict_daily_crowd(future_date)
        weekly_total += daily_pred
    
    return float(weekly_total / 7)  # Return average

def predict_weather_for_dates(dates):
    gb_temp = joblib.load(os.path.join(models_path,"temp.pkl"))
    gb_rain = joblib.load(os.path.join(models_path,"rain.pkl"))
    gb_wind = joblib.load(os.path.join(models_path,"wind.pkl"))

    X = pd.DataFrame({
        'dayofweek': [d.weekday() for d in dates],
        'month': [d.month for d in dates],
        'day': [d.day for d in dates],
        'season': [sri_lanka_season(d.month) for d in dates]
    })

    temps = gb_temp.predict(X)
    rains = gb_rain.predict(X)
    winds = gb_wind.predict(X)

    response = ""
    for i,d in enumerate(dates):
        response += f"{d.date()} (Day {i+1}): {round(temps[i],1)}°C, {weather_type(rains[i],winds[i])}, Wind {round(winds[i],1)} m/s\n"
    return response.strip()

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    # Train models
    train_crowd_models()
    train_weather_models()

    # Example predictions
    import datetime
    future_dates = [datetime.datetime.today() + datetime.timedelta(days=i) for i in range(360)]
    print("\nWeather forecast for next 7 days:\n")
    print(predict_weather_for_dates(future_dates))

    print("\nCrowd forecast examples:\n")
    print("Tomorrow daily crowd:", predict_daily_crowd((datetime.datetime.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")))
    print("Next week weekly crowd:", predict_weekly_crowd((datetime.datetime.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")))
