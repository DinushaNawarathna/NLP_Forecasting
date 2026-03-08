"""
Weather Model Training Script
Trains machine learning models for temperature, rainfall, and wind prediction
Based on historical Sigiriya weather data for 2026 forecasting
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import warnings

warnings.filterwarnings('ignore')

# ============================================================================
# SEASONAL CLASSIFICATION
# ============================================================================

def sri_lanka_season(month):
    """Classify Sri Lankan monsoon seasons"""
    if month in [5, 6, 7, 8, 9]:
        return 1   # Southwest Monsoon
    elif month in [12, 1, 2]:
        return 2   # Northeast Monsoon
    elif month in [3, 4]:
        return 3   # First Inter-monsoon
    else:
        return 4   # Second Inter-monsoon


# ============================================================================
# DATA LOADING AND PREPROCESSING
# ============================================================================

def load_and_prepare_data(csv_path):
    """Load and preprocess weather data"""
    print(f"Loading weather data from {csv_path}...")
    
    df = pd.read_csv(csv_path)
    
    # Parse datetime
    df['dt_iso'] = pd.to_datetime(df['dt_iso'], format='%Y-%m-%d %H:%M:%S +0000 UTC', errors='coerce')
    df = df.sort_values('dt_iso')
    
    # Select relevant columns
    df = df[['dt_iso', 'temp', 'rain_1h', 'humidity', 'wind_speed']]
    
    # Handle missing values
    df['rain_1h'] = df['rain_1h'].fillna(0)
    df['humidity'] = df['humidity'].fillna(df['humidity'].mean())
    df['wind_speed'] = df['wind_speed'].fillna(df['wind_speed'].mean())
    
    # Aggregate to daily data
    df.set_index('dt_iso', inplace=True)
    daily = df.resample('D').agg({
        'temp': 'mean',
        'rain_1h': 'sum',
        'humidity': 'mean',
        'wind_speed': 'mean'
    })
    
    print(f"✓ Data loaded: {len(daily)} days of weather data")
    print(f"  Date range: {daily.index.min()} to {daily.index.max()}")
    print(f"  Temperature: {daily['temp'].min():.1f}°C to {daily['temp'].max():.1f}°C")
    print(f"  Rainfall: {daily['rain_1h'].min():.1f}mm to {daily['rain_1h'].max():.1f}mm")
    print(f"  Wind speed: {daily['wind_speed'].min():.1f}m/s to {daily['wind_speed'].max():.1f}m/s")
    
    return daily


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def create_features(daily_df):
    """Create features for model training"""
    daily_df['dayofweek'] = daily_df.index.dayofweek
    daily_df['month'] = daily_df.index.month
    daily_df['day'] = daily_df.index.day
    daily_df['season'] = daily_df.index.month.map(sri_lanka_season)
    
    X = daily_df[['dayofweek', 'month', 'day', 'season']]
    
    y_temp = daily_df['temp']
    y_rain = daily_df['rain_1h']
    y_wind = daily_df['wind_speed']
    
    return X, y_temp, y_rain, y_wind


# ============================================================================
# MODEL TRAINING
# ============================================================================

def train_weather_models(X, y_temp, y_rain, y_wind, test_split=0.85):
    """Train weather prediction models"""
    
    # Split data
    split = int(len(X) * test_split)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_temp_train, y_temp_test = y_temp.iloc[:split], y_temp.iloc[split:]
    y_rain_train, y_rain_test = y_rain.iloc[:split], y_rain.iloc[split:]
    y_wind_train, y_wind_test = y_wind.iloc[:split], y_wind.iloc[split:]
    
    models = {}
    
    # Temperature model
    print("\n📊 Training Temperature Model...")
    temp_model = GradientBoostingRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    )
    temp_model.fit(X_train, y_temp_train)
    
    temp_pred = temp_model.predict(X_test)
    temp_mae = mean_absolute_error(y_temp_test, temp_pred)
    temp_r2 = r2_score(y_temp_test, temp_pred)
    
    print(f"  ✓ MAE: {temp_mae:.2f}°C")
    print(f"  ✓ R² Score: {temp_r2:.4f}")
    models['temp'] = temp_model
    
    # Rainfall model
    print("\n📊 Training Rainfall Model...")
    rain_model = GradientBoostingRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    )
    rain_model.fit(X_train, y_rain_train)
    
    rain_pred = rain_model.predict(X_test)
    rain_mae = mean_absolute_error(y_rain_test, rain_pred)
    rain_r2 = r2_score(y_rain_test, rain_pred)
    
    print(f"  ✓ MAE: {rain_mae:.2f}mm")
    print(f"  ✓ R² Score: {rain_r2:.4f}")
    models['rain'] = rain_model
    
    # Wind speed model
    print("\n📊 Training Wind Speed Model...")
    wind_model = GradientBoostingRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    )
    wind_model.fit(X_train, y_wind_train)
    
    wind_pred = wind_model.predict(X_test)
    wind_mae = mean_absolute_error(y_wind_test, wind_pred)
    wind_r2 = r2_score(y_wind_test, wind_pred)
    
    print(f"  ✓ MAE: {wind_mae:.2f}m/s")
    print(f"  ✓ R² Score: {wind_r2:.4f}")
    models['wind'] = wind_model
    
    return models


# ============================================================================
# GENERATE YEARLY SUMMARY
# ============================================================================

def generate_2026_forecast_summary(X_base, models):
    """Generate 2026 weather forecast summary for all 365 days"""
    
    print("\n📅 Generating 2026 Full Year Forecast Summary...")
    
    # Create features for all 2026 dates
    dates_2026 = []
    features = []
    
    for month in range(1, 13):
        # Get days in month
        if month == 2:
            days_in_month = 28  # 2026 is not a leap year
        elif month in [4, 6, 9, 11]:
            days_in_month = 30
        else:
            days_in_month = 31
        
        for day in range(1, days_in_month + 1):
            date = datetime(2026, month, day)
            dates_2026.append(date)
            features.append({
                'dayofweek': date.weekday(),
                'month': month,
                'day': day,
                'season': sri_lanka_season(month)
            })
    
    X_2026 = pd.DataFrame(features)
    
    # Make predictions
    temp_pred = models['temp'].predict(X_2026)
    rain_pred = models['rain'].predict(X_2026)
    wind_pred = models['wind'].predict(X_2026)
    
    # Create detailed forecast
    forecast_data = []
    for i, date in enumerate(dates_2026):
        forecast_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'month': date.month,
            'day': date.day,
            'day_of_week': date.strftime('%A'),
            'temperature_celsius': max(15, min(35, temp_pred[i])),  # Clamp to realistic range
            'rainfall_mm': max(0, rain_pred[i]),  # No negative rainfall
            'wind_speed_ms': max(0, wind_pred[i])  # No negative wind
        })
    
    # Monthly summaries
    monthly_summary = {}
    for month in range(1, 13):
        month_data = [f for f in forecast_data if f['month'] == month]
        temps = [f['temperature_celsius'] for f in month_data]
        rains = [f['rainfall_mm'] for f in month_data]
        winds = [f['wind_speed_ms'] for f in month_data]
        
        monthly_summary[month] = {
            'month_name': datetime(2026, month, 1).strftime('%B'),
            'avg_temperature': round(sum(temps) / len(temps), 1),
            'min_temperature': round(min(temps), 1),
            'max_temperature': round(max(temps), 1),
            'total_rainfall': round(sum(rains), 1),
            'rainy_days': sum(1 for r in rains if r > 0.5),
            'avg_wind': round(sum(winds) / len(winds), 1),
            'max_wind': round(max(winds), 1)
        }
    
    # Yearly summary
    all_temps = [f['temperature_celsius'] for f in forecast_data]
    all_rains = [f['rainfall_mm'] for f in forecast_data]
    all_winds = [f['wind_speed_ms'] for f in forecast_data]
    
    yearly_summary = {
        'year': 2026,
        'avg_temperature': round(sum(all_temps) / len(all_temps), 1),
        'min_temperature': round(min(all_temps), 1),
        'max_temperature': round(max(all_temps), 1),
        'total_rainfall': round(sum(all_rains), 1),
        'rainy_days': sum(1 for r in all_rains if r > 0.5),
        'avg_wind': round(sum(all_winds) / len(all_winds), 1),
        'max_wind': round(max(all_winds), 1)
    }
    
    print(f"✓ 2026 Forecast Generated:")
    print(f"  Yearly Avg Temp: {yearly_summary['avg_temperature']}°C")
    print(f"  Yearly Total Rainfall: {yearly_summary['total_rainfall']}mm")
    print(f"  Rainy Days: {yearly_summary['rainy_days']}/365")
    
    return forecast_data, monthly_summary, yearly_summary


# ============================================================================
# MODEL SAVING
# ============================================================================

def save_models(models, output_dir='./models'):
    """Save trained models to disk"""
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"✓ Created models directory: {output_dir}")
    
    for name, model in models.items():
        path = os.path.join(output_dir, f"{name}.pkl")
        joblib.dump(model, path)
        print(f"✓ Saved {name} model to {path}")


def save_forecasts(forecast_data, monthly_summary, yearly_summary, output_dir='./'):
    """Save forecast data to CSV and JSON"""
    import json
    
    # Save daily forecast
    df_forecast = pd.DataFrame(forecast_data)
    forecast_csv = os.path.join(output_dir, 'forecast_2026_weather.csv')
    df_forecast.to_csv(forecast_csv, index=False)
    print(f"✓ Saved daily forecast to {forecast_csv}")
    
    # Save monthly summary
    monthly_json = os.path.join(output_dir, 'weather_monthly_summary_2026.json')
    with open(monthly_json, 'w') as f:
        json.dump(monthly_summary, f, indent=2)
    print(f"✓ Saved monthly summary to {monthly_json}")
    
    # Save yearly summary
    yearly_json = os.path.join(output_dir, 'weather_yearly_summary_2026.json')
    with open(yearly_json, 'w') as f:
        json.dump(yearly_summary, f, indent=2)
    print(f"✓ Saved yearly summary to {yearly_json}")


# ============================================================================
# MAIN TRAINING PIPELINE
# ============================================================================

def main():
    """Execute complete training pipeline"""
    
    print("=" * 70)
    print("🌤️  WEATHER PREDICTION MODEL TRAINING")
    print("=" * 70)
    
    # Get current working directory
    cwd = os.getcwd()
    csv_path = os.path.join(cwd, "data/sigiriya_weather.csv")
    
    # Check if data file exists
    if not os.path.exists(csv_path):
        print(f"\n❌ Error: Weather data file not found at {csv_path}")
        print("Please ensure 'data/sigiriya_weather.csv' exists in the working directory")
        return False
    
    try:
        # Load and prepare data
        daily_df = load_and_prepare_data(csv_path)
        
        # Create features
        X, y_temp, y_rain, y_wind = create_features(daily_df)
        
        # Train models
        models = train_weather_models(X, y_temp, y_rain, y_wind)
        
        # Generate 2026 forecasts
        forecast_data, monthly_summary, yearly_summary = generate_2026_forecast_summary(X, models)
        
        # Save models
        save_models(models)
        
        # Save forecasts
        save_forecasts(forecast_data, monthly_summary, yearly_summary)
        
        print("\n" + "=" * 70)
        print("✅ TRAINING COMPLETE!")
        print("=" * 70)
        print("\nModels saved to ./models/")
        print("Forecasts saved to current directory")
        print("\nYou can now use weather_prediction.py for weather queries")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during training: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
