"""
Crowd Prediction Module for Sigiriya

This module provides visitor crowd forecasting using a trained XGBoost model
with feature engineering based on temporal and seasonal patterns.
The model uses historical visitor data to predict crowd levels for future dates.

Model:
- best_sigiriya_model: XGBoost regressor for visitor count prediction
"""

import pandas as pd
import numpy as np
import joblib
import os
from typing import List, Dict
from datetime import datetime, timedelta


# ============================================================================
# GLOBAL MODEL INSTANCES
# ============================================================================

_models_loaded = False
best_sigiriya_model = None
_last_known_values = []  # Store last 7 days of visitor counts for lag features


def initialize_crowd_models(models_dir: str = "./models"):
    """Initialize global crowd model instances."""
    global _models_loaded, best_sigiriya_model
    
    if not _models_loaded:
        best_sigiriya_model = load_crowd_models(models_dir)
        _models_loaded = True


def load_crowd_models(models_dir: str = "./models"):
    """
    Load trained crowd prediction model and initialize historical data.
    
    Args:
        models_dir: Directory containing the trained model files
    
    Returns:
        Trained XGBoost model for crowd prediction
    """
    global _last_known_values
    
    try:
        model = joblib.load(os.path.join(models_dir, "best_sigiriya_model.pkl"))
        
        print(f"✓ Crowd model loaded successfully from {models_dir}")
        
        # Load historical data to initialize lag features
        try:
            csv_path = os.path.join(os.getcwd(), "sigiriya_synthetic_visitors_2023_2025.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path, parse_dates=["Date"])
                df = df.sort_values("Date").reset_index(drop=True)
                
                # Get last 7 days of historical data for lag features
                if len(df) > 0:
                    _last_known_values = df["Visitor_Count"].tail(7).tolist()
                    print(f"✓ Initialized lag features with {len(_last_known_values)} historical values")
                    print(f"  Last known values: {_last_known_values}")
        except Exception as e:
            print(f"⚠ Warning: Could not load historical data for lag features: {e}")
            print(f"  Using default lag values instead")
        
        return model
    except FileNotFoundError as e:
        print(f"✗ Error: Could not find best_sigiriya_model.pkl in {models_dir}")
        print(f"  Make sure you have run crowd.ipynb first to train the model")
        raise


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def create_crowd_features(date: datetime) -> Dict:
    """
    Create features for crowd prediction at a specific date.
    
    Args:
        date: datetime object for the date to predict
    
    Returns:
        Dictionary with engineered features
    """
    features = {
        'month': date.month,
        'is_weekend': 1 if date.weekday() >= 5 else 0,
        'day_of_year': date.timetuple().tm_yday,
        'week_of_year': date.isocalendar()[1],
        'quarter': (date.month - 1) // 3 + 1,
    }
    
    # Determine peak season (school holidays & tourist season)
    features['peak_season_flag'] = 1 if date.month in [1, 7, 8, 12] else 0
    
    # Determine holiday flag (common Sri Lankan holidays)
    # This can be enhanced with a more comprehensive holiday list
    features['holiday_flag'] = 0
    
    return features


def get_lag_features(last_known_values: List[int]) -> Dict:
    """
    Get lag features from historical visitor counts.
    
    Args:
        last_known_values: List of last 7 days' visitor counts
    
    Returns:
        Dictionary with lag features
    """
    if not last_known_values or len(last_known_values) == 0:
        # Use more realistic defaults based on typical Sigiriya data
        return {
            'lag_1': 350,
            'lag_7': 350,
            'rolling_mean_7': 350
        }
    
    # Ensure we have at least some values
    values = np.array(last_known_values, dtype=float)
    
    features = {
        'lag_1': int(values[-1]) if len(values) > 0 else 350,
        'lag_7': int(values[0]) if len(values) >= 7 else int(np.mean(values)),
        'rolling_mean_7': int(np.mean(values))
    }
    
    return features


def build_prediction_dataframe(date: datetime, last_known_values: List[int] = None) -> pd.DataFrame:
    """
    Build a DataFrame with all features required for prediction.
    
    Args:
        date: datetime object for the date to predict
        last_known_values: List of last 7 days' visitor counts
    
    Returns:
        DataFrame ready for model prediction
    """
    # Create base features
    features = create_crowd_features(date)
    
    # Add lag features
    lag_features = get_lag_features(last_known_values or [])
    features.update(lag_features)
    
    # Ensure all required columns are present in correct order
    feature_columns = [
        'month', 'is_weekend', 'peak_season_flag', 'holiday_flag',
        'day_of_year', 'week_of_year', 'quarter',
        'lag_1', 'lag_7', 'rolling_mean_7'
    ]
    
    df = pd.DataFrame([features])
    return df[feature_columns]


# ============================================================================
# CROWD PREDICTION
# ============================================================================

def get_crowd_for_dates(dates: List[datetime]) -> str:
    """
    Predict visitor crowd for a list of dates.
    
    Args:
        dates: List of datetime objects to predict crowd for
    
    Returns:
        Formatted string with crowd predictions for each date
    """
    if not _models_loaded or best_sigiriya_model is None:
        return "❌ Crowd models not initialized. Please ensure models are trained."
    
    response = ""
    for d in dates:
        try:
            # Build feature dataframe for prediction
            df = build_prediction_dataframe(d, _last_known_values)
            
            # Predict crowd
            visitors = int(best_sigiriya_model.predict(df)[0])
            
            day_name = d.strftime('%A')
            date_str = d.strftime('%b %d, %Y')
            
            # Crowd level indicator
            if visitors > 500:
                level = "🔴 Very Busy"
                advice = "⏳ The waiting time would be around 20 mins, please prepare for that."
            elif visitors > 350:
                level = "🟠 Busy"
                advice = "⏳ The waiting time would be around 20 mins, please prepare for that."
            elif visitors > 200:
                level = "🟡 Moderate"
                advice = "⏳ The waiting time would be around 20 mins, please prepare for that."
            elif visitors > 100:
                level = "🟢 Light"
                advice = "✨ Enjoy the views!"
            else:
                level = "🟢 Quiet"
                advice = "✨ Enjoy the views!"
            
            response += (
                f"📅 {date_str} ({day_name})\n"
                f"👥 Expected Visitors: ~{visitors}\n"
                f"⚠️ Crowding Level: {level}\n"
                f"{advice}\n\n"
            )
        except Exception as e:
            response += f"📅 {d.strftime('%b %d, %Y')}: Error predicting crowd\n\n"
    
    return response.strip()


def get_crowd_dict_for_dates(dates: List[datetime]) -> List[Dict]:
    """
    Predict visitor crowd for a list of dates and return as list of dictionaries.
    
    Args:
        dates: List of datetime objects to predict crowd for
    
    Returns:
        List of dictionaries with crowd predictions
    """
    if not _models_loaded or best_sigiriya_model is None:
        return []
    
    results = []
    for d in dates:
        try:
            # Build feature dataframe for prediction
            df = build_prediction_dataframe(d, _last_known_values)
            
            # Predict crowd
            visitors = int(best_sigiriya_model.predict(df)[0])
            
            # Crowd level
            if visitors > 500:
                level = "Very Busy"
                advice = "⏳ The waiting time would be around 20 mins, please prepare for that."
            elif visitors > 350:
                level = "Busy"
                advice = "⏳ The waiting time would be around 20 mins, please prepare for that."
            elif visitors > 200:
                level = "Moderate"
                advice = "⏳ The waiting time would be around 20 mins, please prepare for that."
            elif visitors > 100:
                level = "Light"
                advice = "✨ Enjoy the views!"
            else:
                level = "Quiet"
                advice = "✨ Enjoy the views!"
            
            results.append({
                'date': d.strftime('%Y-%m-%d'),
                'day_name': d.strftime('%A'),
                'visitors': visitors,
                'crowding_level': level,
                'emoji': get_crowd_emoji(level),
                'advice': advice
            })
        except Exception as e:
            results.append({
                'date': d.strftime('%Y-%m-%d'),
                'error': str(e)
            })
    
    return results


def get_crowd_emoji(level: str) -> str:
    """Get emoji based on crowding level."""
    if level == "Very Busy":
        return "🔴"
    elif level == "Busy":
        return "🟠"
    elif level == "Moderate":
        return "🟡"
    elif level == "Light":
        return "🟢"
    else:
        return "🟢"


def predict_crowd_for_date(date: datetime) -> int:
    """
    Predict visitor count for a specific date.
    
    Args:
        date: datetime object for the date to predict
    
    Returns:
        Predicted visitor count
    """
    if not _models_loaded or best_sigiriya_model is None:
        return 0
    
    try:
        # Build feature dataframe for prediction
        df = build_prediction_dataframe(date, _last_known_values)
        
        # Predict and return
        return int(best_sigiriya_model.predict(df)[0])
    except Exception as e:
        print(f"Error predicting crowd: {e}")
        return 0
