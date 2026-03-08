"""
FastAPI application for Sigiriya Visitor Count Forecasting and Analysis.

Endpoints:
- GET  /forecast          - Get next 90-day forecast
- GET  /recommendations   - Get crowd analysis and recommendations for a date
- POST /chat             - Conversational chat interface
- GET  /best-dates       - Get top 10 best (least crowded) dates
- GET  /day-patterns     - Get day-of-week visitor patterns
- GET  /weather          - Get weather forecast
- POST /weather/query    - Query weather with natural language
- GET  /health           - Health check
"""

from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from prophet import Prophet
import os
import re
import threading
import json
import logging
from weather_query_handler import get_weather_response
from weather_prediction import get_weather_dict_for_dates, initialize_models
from crowd_prediction import initialize_crowd_models, get_crowd_for_dates, get_crowd_dict_for_dates
from openweather_integration import get_hourly_weather, format_hourly_for_display, get_current_weather, get_daily_weather
from crowd_query_handler import process_crowd_query
from real_time_questions import process_real_time_question
from location_validator import should_reject_query
from db_config import initialize_database, DatabaseOperations, db_config
from admin_auth import (
    AdminOperations, AdminRegisterRequest, AdminLoginRequest, TokenResponse
)

# Initialize logger
logger = logging.getLogger(__name__)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def convert_numpy_to_python(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    elif isinstance(obj, np.generic):
        return obj.item()
    elif isinstance(obj, dict):
        return {k: convert_numpy_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_to_python(item) for item in obj]
    else:
        return obj


def sanitize_chat_output(text: str) -> str:
    """Remove markdown-like symbols from chat text for cleaner UI output."""
    if not isinstance(text, str):
        return text

    # Remove markdown bold markers and hash prefixes used in headings/lists
    text = text.replace('**', '')
    text = re.sub(r'(^|\n)\s*#+\s*', r'\1', text)
    text = text.replace('#', '')

    return text


# ============================================================================
# INITIALIZATION
# ============================================================================

# Global variables for forecast data
df = None
fc_df = None
prophet_model = None
full_forecast = None
forecast_ready = False
weather_models_ready = False
crowd_models_ready = False

def _load_forecast():
    """Load forecast in background thread."""
    global df, fc_df, prophet_model, full_forecast, forecast_ready
    try:
        # Load data
        csv_path = os.path.join(os.getcwd(), "sigiriya_synthetic_visitors_2023_2025.csv")
        df = pd.read_csv(csv_path, parse_dates=["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        
        # Handle missing values
        df['Visitor_Count'] = df['Visitor_Count'].ffill().fillna(0)
        
        # Generate forecast
        fc_df, prophet_model, full_forecast = save_prophet_forecast(
            df=df,
            date_col='Date',
            target_col='Visitor_Count',
            regressor_cols=['Avg_Temperature', 'Rainfall_mm', 'Public_Holiday_Count'],
            horizon=90,
            add_holidays=True,
            country='LK'
        )
        forecast_ready = True
        print("✓ Forecast model initialized successfully")
    except Exception as e:
        print(f"✗ Error loading forecast: {e}")
        forecast_ready = False

def _load_weather_models():
    """Load weather prediction models in background thread."""
    global weather_models_ready
    try:
        initialize_models()
        weather_models_ready = True
        print("✓ Weather models initialized successfully")
    except Exception as e:
        print(f"✗ Error loading weather models: {e}")
        weather_models_ready = False

def _load_crowd_models():
    """Load crowd prediction models in background thread."""
    global crowd_models_ready
    try:
        initialize_crowd_models()
        crowd_models_ready = True
        print("✓ Crowd models initialized successfully")
    except Exception as e:
        print(f"✗ Error loading crowd models: {e}")
        crowd_models_ready = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background forecast loading and database initialization."""
    # Initialize database
    threading.Thread(target=initialize_database, daemon=True).start()
    # Start forecast loading in background thread (don't wait)
    threading.Thread(target=_load_forecast, daemon=True).start()
    # Start weather model loading in background thread
    threading.Thread(target=_load_weather_models, daemon=True).start()
    # Start crowd model loading in background thread
    threading.Thread(target=_load_crowd_models, daemon=True).start()
    yield
    # Cleanup on shutdown (if needed)

app = FastAPI(
    title="Sigiriya Visitor Forecast API",
    description="Real-time forecasting and crowd analysis for Sigiriya Rock Fortress",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for browser requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    
class BestDayData(BaseModel):
    date: str
    day_of_week: str
    weather_score: float
    crowd_score: float
    overall_score: float
    temperature: float
    rainfall: float
    crowd_level: str
    
class ChatResponse(BaseModel):
    user_message: str
    assistant_response: str
    best_days: Optional[List[BestDayData]] = None
    target_month: Optional[str] = None
    
class ForecastItem(BaseModel):
    date: str
    forecast_visitor_count: int
    lower_bound: int
    upper_bound: int
    
class RecommendationResponse(BaseModel):
    date: str
    day_of_week: str
    expected_visitors: int
    percent_vs_average: float
    crowd_level: str
    is_crowded: bool
    average_visitors: int
    
class BestDateItem(BaseModel):
    date: str
    day_of_week: str
    expected_visitors: int
    percent_vs_average: float
    crowd_level: str
    
class DayPatternItem(BaseModel):
    day_of_week: str
    average_visitors: float
    min_visitors: float
    max_visitors: float
    
# ============================================================================
# CORE FUNCTIONS (From Notebook)
# ============================================================================

def save_prophet_forecast(
    df,
    date_col='Date',
    target_col='Visitor_Count',
    regressor_cols=None,
    horizon=90,
    output_csv='prophet_forecast.csv',
    weekly_seasonality=True,
    yearly_seasonality=True,
    daily_seasonality=False,
    add_holidays=True,
    country='LK',
    changepoint_prior_scale=0.05,
    seasonality_prior_scale=10.0,
    seasonality_mode='multiplicative'
):
    """Fit Prophet model and return forecast data."""
    
    # Prepare data for Prophet
    cols_to_select = [date_col, target_col]
    if regressor_cols:
        cols_to_select.extend(regressor_cols)
    
    df_prophet = df[cols_to_select].copy()
    col_mapping = {date_col: 'ds', target_col: 'y'}
    df_prophet = df_prophet.rename(columns=col_mapping)
    
    # Initialize Prophet
    m = Prophet(
        weekly_seasonality=weekly_seasonality,
        yearly_seasonality=yearly_seasonality,
        daily_seasonality=daily_seasonality,
        changepoint_prior_scale=changepoint_prior_scale,
        seasonality_prior_scale=seasonality_prior_scale,
        seasonality_mode=seasonality_mode,
        interval_width=0.95
    )
    
    # Add holidays
    if add_holidays and country:
        m.add_country_holidays(country_name=country)
    
    # Add regressors
    if regressor_cols:
        for reg in regressor_cols:
            m.add_regressor(reg)
    
    # Fit model (suppress Prophet logging)
    with open(os.devnull, 'w') as devnull:
        import sys
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            m.fit(df_prophet)
        finally:
            sys.stdout = old_stdout
    
    # Create future dataframe
    future = m.make_future_dataframe(periods=horizon, freq='D')
    
    # Add regressor values for future dates
    if regressor_cols:
        for reg in regressor_cols:
            future[reg] = df_prophet[reg].mean()
    
    # Predict
    forecast = m.predict(future)
    
    # Extract forecast for future periods only
    fc_df = forecast.tail(horizon)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
    fc_df = fc_df.rename(columns={
        'ds': 'Date',
        'yhat': 'Forecast_Visitor_Count',
        'yhat_lower': 'Lower_Bound',
        'yhat_upper': 'Upper_Bound'
    })
    
    # Clamp negative values to zero and round
    fc_df['Forecast_Visitor_Count'] = np.maximum(fc_df['Forecast_Visitor_Count'], 0).round().astype(int)
    fc_df['Lower_Bound'] = np.maximum(fc_df['Lower_Bound'], 0).round().astype(int)
    fc_df['Upper_Bound'] = np.maximum(fc_df['Upper_Bound'], 0).round().astype(int)
    
    return fc_df, m, forecast


def suggest_visiting_times(
    forecast_df,
    date_col='Date',
    visitor_col='Forecast_Visitor_Count',
    crowded_threshold=0.75,
    best_days_count=10,
    worst_days_count=10,
    check_date=None
):
    """Analyze forecast to suggest best visiting times."""
    
    df = forecast_df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    
    # Calculate statistics
    mean_visitors = df[visitor_col].mean()
    median_visitors = df[visitor_col].median()
    std_visitors = df[visitor_col].std()
    crowded_cutoff = df[visitor_col].quantile(crowded_threshold)
    
    # Add day of week
    df['day_name'] = df[date_col].dt.day_name()
    df['is_weekend'] = df[date_col].dt.dayofweek.isin([5, 6])
    
    # Classify crowd levels
    df['crowd_level'] = pd.cut(
        df[visitor_col],
        bins=[0, mean_visitors * 0.7, mean_visitors * 1.3, np.inf],
        labels=['Low', 'Moderate', 'High']
    )
    
    # Best days (least crowded)
    best_days = df.nsmallest(best_days_count, visitor_col)[[date_col, visitor_col, 'day_name', 'crowd_level']].copy()
    
    # Worst days (most crowded)
    worst_days = df.nlargest(worst_days_count, visitor_col)[[date_col, visitor_col, 'day_name', 'crowd_level']].copy()
    
    # Check specific date
    today_info = None
    if check_date:
        check_date = pd.to_datetime(check_date)
    else:
        check_date = pd.Timestamp.today().normalize()
    
    today_match = df[df[date_col] == check_date]
    if not today_match.empty:
        today_visitors = today_match[visitor_col].iloc[0]
        today_day = today_match['day_name'].iloc[0]
        today_level = today_match['crowd_level'].iloc[0]
        
        is_crowded = today_visitors >= crowded_cutoff
        percent_vs_avg = ((today_visitors - mean_visitors) / mean_visitors) * 100
        
        today_info = {
            'date': check_date,
            'day': today_day,
            'expected_visitors': int(today_visitors),
            'crowd_level': str(today_level),
            'is_crowded': is_crowded,
            'percent_vs_average': round(percent_vs_avg, 1),
            'average_visitors': round(mean_visitors, 0)
        }
    
    # Day of week patterns
    dow_stats = df.groupby('day_name')[visitor_col].agg(['mean', 'min', 'max']).round(0)
    dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    dow_stats = dow_stats.reindex([d for d in dow_order if d in dow_stats.index])
    
    results = {
        'statistics': {
            'mean': round(mean_visitors, 0),
            'median': round(median_visitors, 0),
            'std': round(std_visitors, 0),
            'crowded_threshold': round(crowded_cutoff, 0)
        },
        'best_days': best_days,
        'worst_days': worst_days,
        'today': today_info,
        'day_of_week_patterns': dow_stats
    }
    
    return results


def get_general_response(user_message):
    """Generate response for out-of-scope questions - redirect to crowd/weather focus."""
    # Simple, convenient redirection for any out-of-scope question
    return """📋 I focus on crowd & weather forecasting!

✅ I can help with:
• 👥 Crowd predictions for any date or month
• 🌤️ Weather forecasts (temperature, rain, wind)
• 📅 Best days to visit (low crowds + great weather)
• 📊 Weekly & monthly visitor analysis

Try asking me:
• "What's the crowd on March 15?"
• "Crowd forecast for April"
• "Will it rain next week?"
• "When are the best days to visit?"
• "How many visitors this weekend?"

📝 Just pick a date and I'll show you everything! ☀️👥"""


def chat_visitor_forecast(user_message, forecast_df):
    """Conversational chat interface for visitor forecast queries."""
    
    # Check if user is asking about best dates
    best_date_keywords = r'(best|quiet|least crowded|least busy|uncrowded|empty|when is best|optimal|good time|suggest.*date)'
    if re.search(best_date_keywords, user_message, re.IGNORECASE):
        return get_best_dates_response(forecast_df)
    
    # Extract date from user message
    date_pattern = r'(\d{4}-\d{2}-\d{2}|(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}[,\s]+\d{4}?|\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4})'
    dates_found = re.findall(date_pattern, user_message, re.IGNORECASE)
    
    # Try to parse dates
    check_date = None
    for date_match in dates_found:
        date_str = date_match[0] if isinstance(date_match, tuple) else date_match
        try:
            check_date = pd.to_datetime(date_str)
            break
        except:
            pass
    
    # If no date found, check if it's a general question
    if check_date is None or pd.isna(check_date):
        # Try to answer general questions about Sigiriya
        general_keywords = r'(about|tell|sigiriya|history|attraction|near|activity|do|visit|explore|rock|fortress|climb|what|how|where)'
        if re.search(general_keywords, user_message, re.IGNORECASE):
            return get_general_response(user_message)
        
        # Default helpful message
        return "I'd love to help! 😊 Could you please tell me a specific date? (e.g., '2025-12-25' or 'Dec 25, 2025') Or ask me 'What are the best dates to visit?' or 'Tell me about Sigiriya'."
    
    # Analyze the forecast for that date
    analysis = suggest_visiting_times(forecast_df, check_date=check_date)
    
    # If date not in forecast
    if analysis['today'] is None:
        min_date = pd.to_datetime(forecast_df['Date'].iloc[0]).strftime('%B %d, %Y')
        max_date = pd.to_datetime(forecast_df['Date'].iloc[-1]).strftime('%B %d, %Y')
        return f"❌ Sorry! The date {check_date.strftime('%B %d, %Y')} is outside my forecast period. Please choose a date between {min_date} and {max_date}."
    
    t = analysis['today']
    
    # Build conversational response
    response = ""
    
    # Determine crowd status
    if t['is_crowded']:
        emoji = "🔴"
        sentiment = "might be crowded"
        warning = True
    elif t['percent_vs_average'] < -15:
        emoji = "🟢"
        sentiment = "is a great time to visit"
        warning = False
    else:
        emoji = "🟡"
        sentiment = "is moderately busy"
        warning = False
    
    # Main response
    response += f"{emoji} {t['date'].strftime('%B %d, %Y')} ({t['day']}) {sentiment}!\n\n"
    
    # Details
    response += f"📊 Expected Visitors: ~{t['expected_visitors']:,} people\n"
    response += f"📈 vs. Average: {t['percent_vs_average']:+.0f}% ({t['average_visitors']:.0f} is typical)\n"
    response += f"🚦 Crowd Level: {t['crowd_level']}\n"
    
    # Recommendations
    if warning:
        response += f"\n⚠️ Heads up! This day is {abs(t['percent_vs_average']):.0f}% busier than usual.\n\n"
        response += "✨ Better alternatives (less crowded):\n"
        for idx, (_, row) in enumerate(analysis['best_days'].head(3).iterrows(), 1):
            date_str = pd.to_datetime(row['Date']).strftime('%b %d, %Y (%a)')
            visitors = row['Forecast_Visitor_Count']
            response += f"  {idx}. {date_str} → ~{visitors:,} visitors\n"
    else:
        response += f"\n✅ You're in luck! It's {abs(t['percent_vs_average']):.0f}% quieter than average. Perfect for exploring! 🎉\n"
    
    # Weekly pattern insight
    dow_stats = analysis['day_of_week_patterns']
    if t['day'] in dow_stats.index:
        dow_avg = dow_stats.loc[t['day'], 'mean']
        dow_rank = pd.Series(dow_stats['mean']).rank()
        dow_rank = dow_rank[t['day']]
        total_days = len(dow_stats)
        
        response += f"\n📅 Day of Week Insight: {t['day']}s are the #{int(dow_rank)} day of the week\n"
        response += f"   (Average: ~{dow_avg:,.0f} visitors)\n"
    
    return response


def get_best_dates_response(forecast_df):
    """Generate response showing best dates to visit."""
    
    analysis = suggest_visiting_times(forecast_df, check_date=None)
    
    response = "✨ TOP 10 BEST DATES TO VISIT (Least Crowded) ✨\n\n"
    response += "Here are the quietest days in the forecast period:\n\n"
    
    for idx, (_, row) in enumerate(analysis['best_days'].head(10).iterrows(), 1):
        date_obj = pd.to_datetime(row[analysis['best_days'].columns[0]])
        date_str = date_obj.strftime('%b %d, %Y (%A)')
        visitors = int(row[analysis['best_days'].columns[1]])
        crowd = row[analysis['best_days'].columns[3]]
        
        # Calculate vs average
        avg = analysis['statistics']['mean']
        pct_vs_avg = ((visitors - avg) / avg) * 100
        
        response += f"{idx:2d}. 🟢 {date_str}\n"
        response += f"     Expected: ~{visitors:,} visitors ({pct_vs_avg:+.0f}% vs avg)\n"
        response += f"     Crowd: {crowd}\n\n"
    
    # Day of week summary
    response += "📅 BEST DAYS OF THE WEEK (Overall)\n"
    response += "-" * 50 + "\n"
    dow_stats = analysis['day_of_week_patterns'].sort_values('mean')
    for idx, (day, stats) in enumerate(dow_stats.iterrows(), 1):
        avg = stats['mean']
        response += f"{idx}. {day} → ~{avg:,.0f} visitors (range: {stats['min']:.0f}-{stats['max']:.0f})\n"
    
    response += f"\n💡 Tip: Mid-March weekdays (especially Tuesdays-Fridays) are your best bet!\n"
    
    return response


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API documentation."""
    return {
        "name": "Sigiriya Visitor Forecast API",
        "description": "Forecasting and crowd analysis for Sigiriya Rock Fortress",
        "version": "1.0.0",
        "endpoints": {
            "forecast": "/forecast",
            "recommendations": "/recommendations?date=YYYY-MM-DD",
            "chat": "/chat",
            "best_dates": "/best-dates",
            "day_patterns": "/day-patterns",
            "health": "/health"
        }
    }


@app.get("/health", tags=["Info"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "forecast_loaded": fc_df is not None,
        "forecast_periods": len(fc_df) if fc_df is not None else 0
    }


# ============================================================================
# ADMIN AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/admin/register", tags=["Admin Auth"])
async def admin_register(request: AdminRegisterRequest):
    """
    Register a new admin user.
    
    Request Body:
    - name: Admin full name
    - email: Admin email address
    - password: Admin password
    - phone: Admin phone number (optional)
    
    Returns: Token and admin information
    """
    if not db_config.is_connected():
        raise HTTPException(status_code=503, detail="Database not connected. Please try again in a moment.")
    
    success, data = AdminOperations.register_admin(
        db_config=db_config,
        db_operations=DatabaseOperations,
        name=request.name,
        email=request.email,
        password=request.password,
        phone=request.phone
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=data.get('error', 'Registration failed'))
    
    return TokenResponse(
        access_token=data['token'],
        token_type="bearer",
        admin={'name': data['name'], 'email': data['email']},
        name=data['name']
    )


@app.post("/admin/login", tags=["Admin Auth"])
async def admin_login(request: AdminLoginRequest):
    """
    Login admin user.
    
    Supports both database authentication and demo credentials when offline.
    
    Demo Credentials (when database is unavailable):
    - Email: admin@sigiriya.local
    - Password: demo123
    
    Request Body:
    - email: Admin email address
    - password: Admin password
    
    Returns: Token and admin information
    """
    # Note: We don't check db_config.is_connected() here to allow demo login
    # The AdminOperations.login_admin method handles both scenarios
    
    success, data = AdminOperations.login_admin(
        db_config=db_config,
        email=request.email,
        password=request.password
    )
    
    if not success:
        raise HTTPException(status_code=401, detail=data.get('error', 'Login failed'))
    
    return TokenResponse(
        access_token=data['token'],
        token_type="bearer",
        admin={'name': data['name'], 'email': data['email']},
        name=data['name']
    )


@app.get("/admin/stats", tags=["Admin"])
async def get_admin_stats(authorization: str = Header(None)):
    """
    Get admin dashboard statistics.
    
    Returns summary statistics for the dashboard including:
    - Total visitors
    - Active chats
    - Today's visits
    - Total messages
    """
    if not db_config.is_connected():
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        # Get collection
        analytics_collection = db_config.db['analytics']
        chat_collection = db_config.db['chat_conversations']
        
        # Calculate statistics from database
        total_analytics = analytics_collection.count_documents({})
        active_chats = chat_collection.count_documents({'status': 'active'})
        
        # Calculate daily average from 30-day forecast
        daily_average = 0
        if crowd_models_ready:
            try:
                # Get 30-day forecast starting from today
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                forecast_dates = [today + timedelta(days=i) for i in range(30)]
                crowd_predictions = get_crowd_dict_for_dates(forecast_dates)
                
                if crowd_predictions:
                    # Calculate average visitors over 30 days
                    valid_predictions = [p.get('visitors', 0) for p in crowd_predictions if 'error' not in p]
                    if valid_predictions:
                        daily_average = int(sum(valid_predictions) / len(valid_predictions))
                        logger.info(f"✓ Daily average calculated: {daily_average} visitors (from {len(valid_predictions)} days)")
            except Exception as e:
                logger.warning(f"⚠ Could not calculate daily average: {e}")
                # Fallback to today's visitors only
                try:
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    crowd_data = get_crowd_dict_for_dates([today])
                    if crowd_data and 'error' not in crowd_data[0]:
                        daily_average = crowd_data[0].get('visitors', 0)
                except:
                    pass
        
        # Count total messages
        total_messages = chat_collection.count_documents({})
        
        return {
            'total_visitors': total_analytics,
            'active_chats': active_chats,
            'daily_average': daily_average,
            'total_messages': total_messages,
        }
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/capacity", tags=["Admin"])
async def get_facility_capacity(authorization: str = Header(None)):
    """
    Get facility capacity based on forecast models.
    
    Returns the maximum expected visitors (110% of max predicted visitors)
    from the XGBoost crowd prediction model.
    """
    try:
        # Get monthly forecast
        if crowd_models_ready:
            try:
                end_date = datetime.now() + timedelta(days=90)
                start_date = datetime.now()
                
                # Generate forecast for 90 days
                date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                crowd_forecast = get_crowd_dict_for_dates(date_range.tolist())
                
                if crowd_forecast and len(crowd_forecast) > 0:
                    # Find maximum visitors in forecast
                    max_visitors = max(item.get('visitors', 0) for item in crowd_forecast)
                    # Set capacity as 110% of max
                    capacity = int(max_visitors * 1.1)
                    
                    logger.info(f"✓ Capacity calculated from model: {capacity} (max forecast: {max_visitors})")
                    return {
                        'capacity': capacity,
                        'max_forecast': max_visitors,
                        'buffer_percent': 10,
                        'source': 'XGBoost model'
                    }
            except Exception as e:
                logger.error(f"Error calculating capacity from forecast: {e}")
        
        # Default fallback
        logger.info("✓ Using default capacity: 6000")
        return {
            'capacity': 6000,
            'max_forecast': 5454,
            'buffer_percent': 10,
            'source': 'default'
        }
    except Exception as e:
        logger.error(f"Error getting facility capacity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecast", response_model=List[ForecastItem], tags=["Forecast"])
async def get_forecast(limit: int = Query(90, ge=1, le=90), year: int = Query(2026)):
    """
    Get visitor forecast for the specified year using the best Sigiriya XGBoost model.
    
    Query Parameters:
    - limit: Number of days to return (1-90, default: 90)
    - year: Year to get forecast for (default: 2026)
    """
    from crowd_prediction import get_crowd_dict_for_dates
    from datetime import datetime, timedelta
    
    result = []
    
    # Get the starting date for the requested year
    if year == 2026:
        start_date = datetime(2026, 1, 1)
    else:
        start_date = datetime(year, 1, 1)
    
    # Generate list of dates for the forecast period
    dates = [start_date + timedelta(days=i) for i in range(limit)]
    
    # Get predictions from the best Sigiriya model
    crowd_predictions = get_crowd_dict_for_dates(dates)
    
    # Convert to Flutter-compatible format
    for pred in crowd_predictions:
        try:
            # Handle both possible field names
            date = pred.get('date') or pred.get('ds') or datetime.now().strftime('%Y-%m-%d')
            visitors = int(pred.get('expected_visitors') or pred.get('visitors') or pred.get('yhat') or 0)
            
            # Calculate bounds as percentage of expected
            lower = int(visitors * 0.8) if visitors > 0 else 0
            upper = int(visitors * 1.2) if visitors > 0 else 0
            
            result.append({
                'date': str(date),
                'forecast_visitor_count': visitors,
                'lower_bound': lower,
                'upper_bound': upper
            })
        except (ValueError, TypeError) as e:
            print(f"Error parsing prediction: {e}")
            continue
    
    # If we got no results, return synthetic data
    if not result:
        for i in range(limit):
            date = start_date + timedelta(days=i)
            base_visitors = 3500 + (i % 30) * 100
            result.append({
                'date': date.strftime('%Y-%m-%d'),
                'forecast_visitor_count': base_visitors,
                'lower_bound': int(base_visitors * 0.8),
                'upper_bound': int(base_visitors * 1.2)
            })
    
    return result


@app.get("/forecast/monthly", tags=["Forecast"])
async def get_monthly_forecast(year: int = Query(2026)):
    """
    Get monthly aggregated visitor forecast for full year from XGBoost model.
    Uses the best_sigiriya_model trained on all historical data.
    
    Query Parameters:
    - year: Year to get forecast for (default: 2026)
    
    Returns:
        List of monthly aggregates with average visitors per day
    """
    from crowd_prediction import get_crowd_dict_for_dates
    from datetime import datetime, timedelta
    
    result = []
    
    # Get the starting date
    if year == 2026:
        start_date = datetime(2026, 1, 1)
    else:
        start_date = datetime(year, 1, 1)
    
    month_names = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ]
    
    # Get all 365 days of predictions
    dates = [start_date + timedelta(days=i) for i in range(365)]
    crowd_predictions = get_crowd_dict_for_dates(dates)
    
    # Group predictions by month
    monthly_totals = {}
    monthly_counts = {}
    
    for pred in crowd_predictions:
        try:
            date_str = pred.get('date') or pred.get('ds') or ''
            visitors = int(pred.get('expected_visitors') or pred.get('visitors') or pred.get('yhat') or 0)
            
            # Parse date
            if isinstance(date_str, str):
                pred_date = datetime.strptime(date_str.split()[0], '%Y-%m-%d')
            else:
                pred_date = date_str
            
            month_idx = pred_date.month - 1
            month_name = month_names[month_idx]
            
            if month_name not in monthly_totals:
                monthly_totals[month_name] = 0
                monthly_counts[month_name] = 0
            
            monthly_totals[month_name] += visitors
            monthly_counts[month_name] += 1
        except Exception as e:
            print(f"Error processing monthly data: {e}")
            continue
    
    # Calculate averages and build result
    for month in month_names:
        if month in monthly_totals and monthly_counts[month] > 0:
            avg_visitors = monthly_totals[month] // monthly_counts[month]
            result.append({
                'month': month,
                'average_visitors': avg_visitors,
                'total_visitors': monthly_totals[month],
                'days': monthly_counts[month]
            })
        else:
            # No data for this month, add placeholder
            result.append({
                'month': month,
                'average_visitors': 0,
                'total_visitors': 0,
                'days': 0
            })
    
    return result


@app.get("/crowd/today", response_model=RecommendationResponse, tags=["Forecast"])
async def get_today_crowd():
    """Get today's crowd prediction."""
    if fc_df is None:
        raise HTTPException(status_code=503, detail="Forecast model not initialized")
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    analysis = suggest_visiting_times(fc_df, check_date=today)
    
    if analysis['today'] is None:
        raise HTTPException(status_code=404, detail="Could not get today's forecast")
    
    t = analysis['today']
    # Convert all numpy types to Python types
    return RecommendationResponse(
        date=str(t['date'].strftime('%Y-%m-%d')),
        day_of_week=str(convert_numpy_to_python(t['day'])),
        expected_visitors=int(convert_numpy_to_python(t['expected_visitors'])),
        percent_vs_average=float(convert_numpy_to_python(t['percent_vs_average'])),
        crowd_level=str(convert_numpy_to_python(t['crowd_level'])),
        is_crowded=bool(convert_numpy_to_python(t['is_crowded'])),
        average_visitors=int(convert_numpy_to_python(t['average_visitors']))
    )


@app.get("/crowd/week", response_model=List[RecommendationResponse], tags=["Forecast"])
async def get_week_crowd():
    """Get next 7 days crowd predictions."""
    if fc_df is None:
        raise HTTPException(status_code=503, detail="Forecast model not initialized")
    
    result = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(7):
        date = today + timedelta(days=i)
        analysis = suggest_visiting_times(fc_df, check_date=date)
        
        if analysis['today'] is not None:
            t = analysis['today']
            # Convert all numpy types to Python types
            result.append(RecommendationResponse(
                date=str(t['date'].strftime('%Y-%m-%d')),
                day_of_week=str(convert_numpy_to_python(t['day'])),
                expected_visitors=int(convert_numpy_to_python(t['expected_visitors'])),
                percent_vs_average=float(convert_numpy_to_python(t['percent_vs_average'])),
                crowd_level=str(convert_numpy_to_python(t['crowd_level'])),
                is_crowded=bool(convert_numpy_to_python(t['is_crowded'])),
                average_visitors=int(convert_numpy_to_python(t['average_visitors']))
            ))
    
    return result


@app.get("/recommendations", response_model=RecommendationResponse, tags=["Analysis"])
async def get_recommendations(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Get crowd analysis and recommendations for a specific date.
    
    Query Parameters:
    - date: Date to analyze (required, format: YYYY-MM-DD)
    """
    if fc_df is None:
        raise HTTPException(status_code=503, detail="Forecast model not initialized")
    
    try:
        check_date = pd.to_datetime(date)
    except:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    analysis = suggest_visiting_times(fc_df, check_date=check_date)
    
    if analysis['today'] is None:
        raise HTTPException(
            status_code=404,
            detail=f"Date {date} is outside forecast period"
        )
    
    t = analysis['today']
    return RecommendationResponse(
        date=t['date'].strftime('%Y-%m-%d'),
        day_of_week=str(t['day']),
        expected_visitors=int(t['expected_visitors']),
        percent_vs_average=float(t['percent_vs_average']),
        crowd_level=str(t['crowd_level']),
        is_crowded=bool(t['is_crowded']),
        average_visitors=int(t['average_visitors'])
    )


@app.get("/best-dates", response_model=List[BestDateItem], tags=["Analysis"])
async def get_best_dates():
    """Get top 10 best (least crowded) dates in forecast period."""
    if fc_df is None:
        raise HTTPException(status_code=503, detail="Forecast model not initialized")
    
    analysis = suggest_visiting_times(fc_df)
    result = []
    
    for _, row in analysis['best_days'].head(10).iterrows():
        date_obj = pd.to_datetime(row['Date'])
        visitors = int(row['Forecast_Visitor_Count'])
        avg = analysis['statistics']['mean']
        pct_vs_avg = ((visitors - avg) / avg) * 100
        
        result.append(BestDateItem(
            date=date_obj.strftime('%Y-%m-%d'),
            day_of_week=row['day_name'],
            expected_visitors=visitors,
            percent_vs_average=round(pct_vs_avg, 1),
            crowd_level=str(row['crowd_level'])
        ))
    
    return result


@app.get("/day-patterns", response_model=List[DayPatternItem], tags=["Analysis"])
async def get_day_patterns():
    """Get average visitor patterns by day of week."""
    if fc_df is None:
        raise HTTPException(status_code=503, detail="Forecast model not initialized")
    
    analysis = suggest_visiting_times(fc_df)
    result = []
    
    for day, stats in analysis['day_of_week_patterns'].iterrows():
        result.append(DayPatternItem(
            day_of_week=day,
            average_visitors=round(stats['mean'], 0),
            min_visitors=round(stats['min'], 0),
            max_visitors=round(stats['max'], 0)
        ))
    
    return result


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Conversational chat interface for visitor queries.
    
    Request Body:
    - message: User's natural language question (e.g., "Is Dec 25 good to visit?")
    
    Examples:
    - "What are the best dates to visit?"
    - "Is 2025-12-25 good to visit?"
    - "When is the best time to go?"
    - "Should I go on January 15, 2026?"
    - "I want to visit Sigiriya next week, give me a good day?"
    - "Will the next week be best to visit?"
    - "Will there be a crowd next week?"
    - "What will be the best months to visit?"
    """
    message = request.message
    q = message.lower()
    
    # ====================================================================
    # PRIORITY 0: Validate location - reject non-Sigiriya queries
    # ====================================================================
    should_reject, error_message = should_reject_query(message)
    if should_reject:
        return ChatResponse(
            user_message=request.message,
            assistant_response=sanitize_chat_output(error_message)
        )
    
    # ====================================================================
    # PRIORITY 1: Check for real-time questions first
    # ====================================================================
    try:
        realtime_response = process_real_time_question(message)
        if realtime_response:
            # Check if this is a best days response (contains structured data)
            best_days = None
            target_month = None
            response_text = realtime_response
            
            # If response is a dict with best days data, extract it
            if isinstance(realtime_response, dict):
                best_days_raw = realtime_response.get('best_days', [])
                target_month = realtime_response.get('month')
                response_text = realtime_response.get('text', '')
                
                # Convert best days data to BestDayData objects
                best_days = []
                for day_data in best_days_raw:
                    best_days.append(BestDayData(
                        date=day_data.get('date', ''),
                        day_of_week=day_data.get('day_of_week', ''),
                        weather_score=day_data.get('weather_score', 0.0),
                        crowd_score=day_data.get('crowd_score', 0.0),
                        overall_score=day_data.get('overall_score', 0.0),
                        temperature=day_data.get('temperature', 0.0),
                        rainfall=day_data.get('rainfall', 0.0),
                        crowd_level=day_data.get('crowd_level', '')
                    ))
            
            # Use Gemini to enhance the explanation (for both string and dict responses)
            try:
                from gemini_integration import gemini_service
                gemini_explanation = gemini_service.generate_explanation(message, response_text)
                if gemini_explanation:
                    response_text = gemini_explanation
            except Exception as e:
                print(f"Warning: Gemini explanation for real-time response failed: {e}")
            
            return ChatResponse(
                user_message=request.message,
                assistant_response=sanitize_chat_output(response_text),
                best_days=best_days,
                target_month=target_month
            )
    except Exception as e:
        print(f"Warning: Real-time question processing failed: {e}")
    
    # ====================================================================
    # PRIORITY 2: Check if this is a crowd query or weather query
    # ====================================================================
    crowd_keywords = ['crowd', 'busy', 'visitor', 'people', 'how many', 'crowded', 'crowds', 'packed']
    is_crowd_query = any(keyword in q for keyword in crowd_keywords)
    
    # Check if this is a weather query (exclude month names)
    weather_keywords = ['weather', 'temperature', 'temp', 'rain', 'rainfall', 'wind', 'forecast', 'climate', 'hot', 'cold', 'warm', 'windy', 'celsius', 'degrees']
    is_weather_query = any(keyword in q for keyword in weather_keywords)
    
    response = ""
    # Handle crowd query - PRIORITIZE CROWD OVER WEATHER
    if is_crowd_query:
        try:
            response = process_crowd_query(message)
        except Exception as e:
            response = f"Error processing crowd query: {str(e)}"
    # Handle weather query - ONLY if NOT a crowd query
    elif is_weather_query:
        try:
            response = get_weather_response(message)
        except Exception as e:
            response = "Expected weather forecast: Unable to process weather query at this time."
    else:
        # Try visitor forecast query as fallback
        try:
            if fc_df is None:
                response = "I'm not able to provide data for this location right now. But I can help with Sigiriya! Ask me about the weather, crowds, or the best time to visit."
            else:
                response = chat_visitor_forecast(message, fc_df)
                # If response looks like an error or is too generic, provide helpful guidance
                if not response or response.strip() == "":
                    response = "I'm sorry, I don't have specific information about that. Feel free to ask me about weather, crowds, or when would be a good time to visit Sigiriya."
        except Exception as e:
            response = "I'm sorry, I couldn't process that question. Try asking me about weather, crowds, or the best days to visit Sigiriya."

    # ====================================================================
    # PRIORITY 3: Enhance response with Gemini AI (NEW)
    # ====================================================================
    from gemini_integration import gemini_service
    
    # Use Gemini to generate a human-readable explanation based on the model's output
    try:
        if response and response.strip() != "" and "error" not in response.lower():
            # Pass the user question and the data-driven response to Gemini
            gemini_explanation = gemini_service.generate_explanation(message, response)
            if gemini_explanation:
                response = gemini_explanation
    except Exception as e:
        print(f"Warning: Gemini explanation failed: {e}")
        # Fallback to original response if Gemini fails
    
    return ChatResponse(
        user_message=request.message,
        assistant_response=sanitize_chat_output(response)
    )


# ============================================================================
# WEATHER API ENDPOINTS
# ============================================================================

class WeatherRequest(BaseModel):
    """Weather query request"""
    query: str

class WeatherQueryResponse(BaseModel):
    """Weather query response"""
    query: str
    response: str

class WeatherDataResponse(BaseModel):
    """Weather data response"""
    date: str
    day_of_week: str
    temperature_celsius: float
    rainfall_mm: float
    wind_speed_ms: float
    weather_condition: str
    is_rainy: bool
    is_windy: bool


@app.get("/weather", tags=["Weather"])
async def get_weather(
    date: str = Query(..., description="Date in format YYYY-MM-DD or 'today' or 'tomorrow'"),
):
    """
    Get weather prediction for a specific date.
    
    Parameters:
    - date: Date in YYYY-MM-DD format, or 'today', or 'tomorrow'
    
    Returns weather prediction including:
    - Temperature in Celsius
    - Rainfall in mm
    - Wind speed in m/s
    - Weather condition description
    """
    if not weather_models_ready:
        raise HTTPException(status_code=503, detail="Weather models not initialized yet. Please try again in a moment.")
    
    try:
        # Handle natural language dates
        date_lower = date.lower().strip()
        if date_lower == 'today':
            date_obj = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_lower == 'tomorrow':
            date_obj = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        
        if date_obj.year != 2026:
            raise HTTPException(status_code=400, detail="Weather forecasts only available for 2026")
        
        weather_data = get_weather_dict_for_dates([date_obj])
        
        if not weather_data:
            raise HTTPException(status_code=404, detail="Could not generate weather prediction")
        
        return weather_data[0]
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD, 'today', or 'tomorrow'")


@app.get("/weather/range", tags=["Weather"])
async def get_weather_range(
    start_date: str = Query(..., description="Start date in format YYYY-MM-DD"),
    end_date: str = Query(..., description="End date in format YYYY-MM-DD"),
):
    """
    Get weather predictions for a date range.
    
    Parameters:
    - start_date: Start date in YYYY-MM-DD format
    - end_date: End date in YYYY-MM-DD format
    
    Returns list of weather predictions for the date range
    """
    if not weather_models_ready:
        raise HTTPException(status_code=503, detail="Weather models not initialized yet. Please try again in a moment.")
    
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start.year != 2026 or end.year != 2026:
            raise HTTPException(status_code=400, detail="Weather forecasts only available for 2026")
        
        if start > end:
            raise HTTPException(status_code=400, detail="start_date must be before end_date")
        
        # Generate date range
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        
        weather_data = get_weather_dict_for_dates(dates)
        return weather_data
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


@app.get("/weather/month", tags=["Weather"])
async def get_weather_month(
    year: int = Query(2026, description="Year"),
    month: int = Query(..., description="Month (1-12)"),
):
    """
    Get weather summary for a specific month.
    
    Parameters:
    - year: Year (only 2026 supported)
    - month: Month number (1-12)
    
    Returns monthly weather summary with temperature, rainfall, and wind statistics
    """
    if not weather_models_ready:
        raise HTTPException(status_code=503, detail="Weather models not initialized yet. Please try again in a moment.")
    
    if year != 2026:
        raise HTTPException(status_code=400, detail="Weather forecasts only available for 2026")
    
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    try:
        # Determine days in month
        if month == 2:
            days_in_month = 28  # 2026 is not a leap year
        elif month in [4, 6, 9, 11]:
            days_in_month = 30
        else:
            days_in_month = 31
        
        # Generate dates
        dates = [datetime(2026, month, day) for day in range(1, days_in_month + 1)]
        weather_data = get_weather_dict_for_dates(dates)
        
        # Calculate summary
        temps = [d['temperature_celsius'] for d in weather_data]
        rains = [d['rainfall_mm'] for d in weather_data]
        winds = [d['wind_speed_ms'] for d in weather_data]
        
        month_name = datetime(2026, month, 1).strftime('%B')
        
        summary = {
            'month': month_name,
            'year': year,
            'days': len(weather_data),
            'temperature': {
                'avg': round(sum(temps) / len(temps), 1),
                'min': round(min(temps), 1),
                'max': round(max(temps), 1),
            },
            'rainfall': {
                'total': round(sum(rains), 1),
                'avg_per_day': round(sum(rains) / len(rains), 1),
                'rainy_days': sum(1 for r in rains if r > 0.5),
            },
            'wind': {
                'avg': round(sum(winds) / len(winds), 1),
                'max': round(max(winds), 1),
            },
            'daily_data': weather_data
        }
        
        return summary
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weather/yearly", tags=["Weather"])
async def get_weather_yearly(
    year: int = Query(2026, description="Year"),
):
    """
    Get yearly weather summary for 2026.
    
    Returns yearly weather statistics and summaries by month
    """
    if not weather_models_ready:
        raise HTTPException(status_code=503, detail="Weather models not initialized yet. Please try again in a moment.")
    
    if year != 2026:
        raise HTTPException(status_code=400, detail="Weather forecasts only available for 2026")
    
    try:
        # Load yearly summary if available
        summary_file = os.path.join(os.getcwd(), "weather_yearly_summary_2026.json")
        monthly_file = os.path.join(os.getcwd(), "weather_monthly_summary_2026.json")
        
        yearly_summary = {}
        monthly_summary = {}
        
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                yearly_summary = json.load(f)
        
        if os.path.exists(monthly_file):
            with open(monthly_file, 'r') as f:
                monthly_summary = json.load(f)
        
        return {
            'year': year,
            'yearly_summary': yearly_summary,
            'monthly_summary': monthly_summary
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/weather/query", response_model=WeatherQueryResponse, tags=["Weather"])
async def query_weather(request: WeatherRequest):
    """
    Query weather using natural language.
    
    Request Body:
    - query: Natural language weather question
    
    Examples:
    - "What's the weather on January 15?"
    - "Will it rain in March?"
    - "What's the temperature tomorrow?"
    - "Weather forecast for next week"
    - "How much rainfall in April?"
    - "Wind speed in the first week of July?"
    - "Monthly weather summary for December"
    - "Is February 2026 rainy?"
    """
    if not weather_models_ready:
        raise HTTPException(status_code=503, detail="Weather models not initialized yet. Please try again in a moment.")
    
    try:
        response = get_weather_response(request.query)
        return WeatherQueryResponse(
            query=request.query,
            response=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather query error: {str(e)}")


@app.get("/weather/hourly", tags=["Weather"])
async def get_hourly_weather_forecast(hours: int = Query(48, ge=1, le=120, description="Number of hours to forecast (1-120)")):
    """
    Get hourly weather forecast for Sigiriya from OpenWeatherMap.
    
    Parameters:
    - hours: Number of hours to forecast (1-120, default 48)
    
    Returns real-time hourly forecast data including:
    - Temperature, feels like, wind speed
    - Rainfall probability and amount
    - Cloud coverage, visibility
    - Weather description and recommendation
    """
    try:
        hourly_data = get_hourly_weather(hours=hours)
        
        if not hourly_data:
            raise HTTPException(status_code=503, detail="Unable to fetch hourly weather data. OpenWeatherMap API may be unavailable.")
        
        formatted_data = format_hourly_for_display(hourly_data)
        
        return {
            "location": "Sigiriya, Sri Lanka",
            "coordinates": {"lat": 7.9570, "lon": 80.7595},
            "forecast_hours": hours,
            "total_forecasts": len(formatted_data),
            "data": formatted_data,
            "source": "OpenWeatherMap API",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching hourly weather: {str(e)}")


@app.get("/weather/current", tags=["Weather"])
async def get_current_weather_endpoint():
    """
    Get current weather conditions for Sigiriya.
    
    Returns:
    - Current temperature, feels like, humidity
    - Wind speed and direction
    - Cloud coverage, visibility
    - Weather description
    - Visit recommendation based on current conditions
    """
    try:
        weather_data = get_current_weather()
        
        if not weather_data:
            raise HTTPException(status_code=503, detail="Unable to fetch current weather data.")
        
        return {
            "location": "Sigiriya, Sri Lanka",
            "coordinates": {"lat": 7.9570, "lon": 80.7595},
            "current_weather": {
                "temperature": f"{weather_data['temp']:.1f}°C",
                "feels_like": f"{weather_data['feels_like']:.1f}°C",
                "condition": weather_data['main'],
                "description": weather_data['description'],
                "humidity": f"{weather_data['humidity']}%",
                "wind_speed": f"{weather_data['wind_speed']:.1f} m/s",
                "wind_direction": weather_data['wind_deg'],
                "clouds": f"{weather_data['clouds']}%",
                "pressure": f"{weather_data['pressure']} hPa",
                "timestamp": weather_data['timestamp'].isoformat()
            },
            "source": "OpenWeatherMap API"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching current weather: {str(e)}")


@app.get("/weather_forecast", tags=["Weather"])
async def get_weather_forecast_simple(limit: int = Query(30, ge=1, le=90)):
    """
    Get weather forecast data in Flutter-compatible format.
    
    Parameters:
    - limit: Number of days to return (1-90, default 30)
    
    Returns flat list of weather data compatible with Flutter app.
    """
    try:
        from datetime import datetime, timedelta
        daily_data = get_daily_weather(days=min(limit, 5))
        
        if not daily_data:
            # Return synthetic data if API fails
            synthetic_data = []
            for i in range(min(limit, 30)):
                date = datetime.now() + timedelta(days=i)
                synthetic_data.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "temperature": 28.0 + (i % 5),
                    "rainfall": (i % 10) * 2.5,
                    "wind_speed": 5.0 + (i % 4),
                    "condition": "Partly Cloudy" if i % 3 == 0 else "Sunny"
                })
            return synthetic_data
        
        result = []
        for day in daily_data:
            result.append({
                "date": day['date'].strftime('%Y-%m-%d'),
                "temperature": float(f"{day['temp_avg']:.1f}"),
                "rainfall": float(f"{day['rainfall']:.1f}"),
                "wind_speed": float(f"{day['wind_speed']:.1f}"),
                "condition": day['description'].title()
            })
        
        # Pad with synthetic data if we don't have enough days
        while len(result) < limit:
            last_date = datetime.strptime(result[-1]['date'], '%Y-%m-%d')
            next_date = last_date + timedelta(days=1)
            result.append({
                "date": next_date.strftime('%Y-%m-%d'),
                "temperature": 28.0,
                "rainfall": 0.0,
                "wind_speed": 5.0,
                "condition": "Sunny"
            })
        
        return result[:limit]
    except Exception as e:
        print(f"Error in weather forecast: {str(e)}")
        # Return synthetic data on error
        synthetic_data = []
        for i in range(limit):
            date = datetime.now() + timedelta(days=i)
            synthetic_data.append({
                "date": date.strftime('%Y-%m-%d'),
                "temperature": 28.0 + (i % 5),
                "rainfall": (i % 10) * 2.5,
                "wind_speed": 5.0 + (i % 4),
                "condition": "Partly Cloudy"
            })
        return synthetic_data


@app.get("/weather/daily", tags=["Weather"])
async def get_daily_weather_forecast(days: int = Query(7, ge=1, le=5, description="Number of days to forecast (1-5)")):
    """
    Get daily weather forecast for Sigiriya from OpenWeatherMap.
    
    Parameters:
    - days: Number of days to forecast (1-5, default 7)
    
    Returns daily forecast data including:
    - Min/Max/Average temperature
    - Rainfall probability and amount
    - Wind speed, humidity, cloud coverage
    - Weather description and recommendation
    """
    try:
        daily_data = get_daily_weather(days=days)
        
        if not daily_data:
            raise HTTPException(status_code=503, detail="Unable to fetch daily weather data.")
        
        formatted_data = []
        for day in daily_data:
            temp_desc = _format_temperature(day['temp_avg'])
            rain_desc = _format_rainfall(day['rainfall'])
            wind_desc = _format_wind(day['wind_speed'])
            
            formatted_data.append({
                "date": day['date'].strftime('%A, %B %d, %Y'),
                "temperature": {
                    "max": f"{day['temp_max']:.1f}°C",
                    "min": f"{day['temp_min']:.1f}°C",
                    "avg": f"{day['temp_avg']:.1f}°C",
                    "description": temp_desc
                },
                "condition": day['main'],
                "description": day['description'],
                "rainfall": {
                    "amount": f"{day['rainfall']:.1f} mm",
                    "probability": f"{int(day['pop'] * 100)}%",
                    "description": rain_desc
                },
                "wind": {
                    "speed": f"{day['wind_speed']:.1f} m/s",
                    "description": wind_desc
                },
                "humidity": f"{day['humidity']}%",
                "clouds": f"{day['clouds']}%"
            })
        
        return {
            "location": "Sigiriya, Sri Lanka",
            "coordinates": {"lat": 7.9570, "lon": 80.7595},
            "forecast_days": days,
            "total_forecasts": len(formatted_data),
            "data": formatted_data,
            "source": "OpenWeatherMap API",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching daily weather: {str(e)}")


def _format_temperature(temp: float) -> str:
    """Helper function to format temperature description."""
    if temp < 15:
        return "Very Cold"
    elif temp < 18:
        return "Cold"
    elif temp < 22:
        return "Cool"
    elif temp < 26:
        return "Comfortable"
    elif temp < 30:
        return "Warm"
    elif temp < 35:
        return "Hot"
    else:
        return "Very Hot"


def _format_rainfall(rainfall: float) -> str:
    """Helper function to format rainfall description."""
    if rainfall == 0:
        return "No Rain"
    elif rainfall < 2:
        return "Light Drizzle"
    elif rainfall < 5:
        return "Light Rain"
    elif rainfall < 10:
        return "Moderate Rain"
    elif rainfall < 20:
        return "Heavy Rain"
    else:
        return "Very Heavy Rain"


def _format_wind(wind_speed: float) -> str:
    """Helper function to format wind description."""
    if wind_speed < 2:
        return "Calm"
    elif wind_speed < 5:
        return "Light Breeze"
    elif wind_speed < 10:
        return "Moderate Wind"
    elif wind_speed < 15:
        return "Strong Wind"
    else:
        return "Very Strong Wind"


# ============================================================================
# CROWD FORECASTING ENDPOINTS
# ============================================================================

@app.get("/crowd", tags=["Crowd"])
async def get_crowd(date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format or 'today', 'tomorrow'")):
    """
    Get crowd forecast for a specific date.
    
    Parameters:
    - date: Date in YYYY-MM-DD format (or 'today', 'tomorrow')
    
    Returns crowd prediction and crowding level
    """
    if not crowd_models_ready:
        raise HTTPException(status_code=503, detail="Crowd models not initialized yet. Please try again in a moment.")
    
    try:
        if not date:
            date = 'today'
        
        if date.lower() == 'today':
            target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif date.lower() == 'tomorrow':
            target_date = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            target_date = datetime.strptime(date, '%Y-%m-%d')
        
        result = get_crowd_dict_for_dates([target_date])
        if result:
            return result[0]
        else:
            raise HTTPException(status_code=400, detail="Could not predict crowd for this date")
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/crowd/week", tags=["Crowd"])
async def get_crowd_week(start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format")):
    """
    Get crowd forecast for a week starting from the given date.
    
    Parameters:
    - start_date: Start date in YYYY-MM-DD format (default: today)
    
    Returns crowd predictions for 7 days
    """
    if not crowd_models_ready:
        raise HTTPException(status_code=503, detail="Crowd models not initialized yet. Please try again in a moment.")
    
    try:
        if not start_date:
            start_date_obj = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        
        dates = [start_date_obj + timedelta(days=i) for i in range(7)]
        results = get_crowd_dict_for_dates(dates)
        
        return {
            'start_date': start_date_obj.strftime('%Y-%m-%d'),
            'week_forecast': results
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/crowd/query", tags=["Crowd"])
async def query_crowd(request: WeatherRequest):
    """
    Query crowd using natural language.
    
    Request Body:
    - query: Natural language crowd question
    
    Examples:
    - "What's the crowd today?"
    - "How busy will it be tomorrow?"
    - "Expected visitors this week?"
    - "When is it least busy?"
    - "Crowd forecast for next month?"
    """
    if not crowd_models_ready:
        raise HTTPException(status_code=503, detail="Crowd models not initialized yet. Please try again in a moment.")
    
    try:
        response = process_crowd_query(request.query)
        return WeatherQueryResponse(
            query=request.query,
            response=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Crowd query error: {str(e)}")


# ============================================================================
# ADMIN ANALYTICS ENDPOINTS
# ============================================================================

@app.get("/admin/daily-analytics", tags=["Admin Analytics"])
async def get_daily_analytics(limit: int = Query(7, ge=1, le=90)):
    """
    Get daily visitor analytics for the specified number of days.
    Returns data in format expected by admin dashboard.
    
    Query Parameters:
    - limit: Number of days to return (1-90, default: 7)
    """
    try:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        dates = [start_date + timedelta(days=i) for i in range(limit)]
        
        # Get crowd predictions
        crowd_predictions = get_crowd_dict_for_dates(dates)
        
        if not crowd_predictions:
            # Return synthetic data if no predictions available
            result = []
            for i in range(limit):
                date = start_date + timedelta(days=i)
                result.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'day': date.strftime('%A'),
                    'visitors': 3500 + (i % 7) * 500,
                    'temperature': 28 + (i % 5),
                    'crowd_level': 'Moderate'
                })
            return result
        
        # Transform crowd predictions to dashboard format
        result = []
        for pred in crowd_predictions:
            if 'error' not in pred:
                result.append({
                    'date': pred.get('date', ''),
                    'day': pred.get('day_name', ''),
                    'visitors': pred.get('visitors', 0),
                    'temperature': 28,  # Default, can be enhanced with weather data
                    'crowd_level': pred.get('crowding_level', 'Moderate')
                })
        
        return result
    except Exception as e:
        logger.error(f"Error getting daily analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/weekly-analytics", tags=["Admin Analytics"])
async def get_weekly_analytics(weeks: int = Query(4, ge=1, le=12)):
    """
    Get weekly visitor analytics aggregated from daily forecasts.
    
    Query Parameters:
    - weeks: Number of weeks to return (1-12, default: 4)
    """
    try:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        dates = [start_date + timedelta(days=i) for i in range(weeks * 7)]
        
        # Get crowd predictions
        crowd_predictions = get_crowd_dict_for_dates(dates)
        
        if not crowd_predictions:
            # Return synthetic weekly data
            result = []
            for w in range(weeks):
                week_start = start_date + timedelta(days=w*7)
                week_total = sum(3500 + ((w*7+d) % 7) * 500 for d in range(7))
                result.append({
                    'week': w + 1,
                    'start_date': week_start.strftime('%Y-%m-%d'),
                    'total_visitors': week_total,
                    'daily_average': week_total // 7,
                    'peak_day_visitors': max(3500 + ((w*7+d) % 7) * 500 for d in range(7))
                })
            return result
        
        # Aggregate daily predictions into weekly summaries
        result = []
        for w in range(weeks):
            week_predictions = crowd_predictions[w*7:(w+1)*7]
            week_start = start_date + timedelta(days=w*7)
            
            if week_predictions:
                week_visitors = [p.get('visitors', 0) for p in week_predictions if 'error' not in p]
                if week_visitors:
                    result.append({
                        'week': w + 1,
                        'start_date': week_start.strftime('%Y-%m-%d'),
                        'total_visitors': sum(week_visitors),
                        'daily_average': sum(week_visitors) // len(week_visitors),
                        'peak_day_visitors': max(week_visitors)
                    })
        
        return result
    except Exception as e:
        logger.error(f"Error getting weekly analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/monthly-analytics", tags=["Admin Analytics"])
async def get_monthly_analytics(year: int = Query(2026)):
    """
    Get monthly visitor analytics for the specified year.
    
    Query Parameters:
    - year: Year to get analytics for (default: 2026)
    """
    try:
        result = []
        
        for month in range(1, 13):
            # Get days in month
            if month == 12:
                last_day = (datetime(year + 1, 1, 1) - timedelta(days=1)).day
            else:
                last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
            
            # Get predictions for all days in month
            dates = [datetime(year, month, day) for day in range(1, last_day + 1)]
            crowd_predictions = get_crowd_dict_for_dates(dates)
            
            month_name = datetime(year, month, 1).strftime('%B')
            
            if crowd_predictions:
                month_visitors = [p.get('visitors', 0) for p in crowd_predictions if 'error' not in p]
                if month_visitors:
                    result.append({
                        'month': month_name,
                        'month_number': month,
                        'total_visitors': sum(month_visitors),
                        'average_visitors': sum(month_visitors) // len(month_visitors),
                        'peak_day_visitors': max(month_visitors),
                        'days': len(month_visitors)
                    })
                    continue
            
            # Synthetic fallback
            synthetic_visitors = [3500 + (d % 7) * 500 for d in range(1, last_day + 1)]
            result.append({
                'month': month_name,
                'month_number': month,
                'total_visitors': sum(synthetic_visitors),
                'average_visitors': sum(synthetic_visitors) // len(synthetic_visitors),
                'peak_day_visitors': max(synthetic_visitors),
                'days': last_day
            })
        
        return result
    except Exception as e:
        logger.error(f"Error getting monthly analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
