"""
Crowd Query Handler

Processes natural language queries about visitor crowds and returns predictions.
Also handles combined weather + crowd queries for best days recommendations.
"""

import datetime
import numpy
from crowd_prediction import get_crowd_for_dates, get_crowd_dict_for_dates, predict_crowd_for_date, initialize_crowd_models
from weather_prediction import get_weather_dict_for_dates, get_best_weather_dates, initialize_models as initialize_weather_models
from location_validator import should_reject_query


class CrowdHandler:
    """Handles natural language crowd queries."""
    
    def __init__(self):
        # Initialize models if not already done
        try:
            initialize_weather_models()
        except Exception as e:
            print(f"Warning: Could not initialize weather models: {e}")
        
        try:
            initialize_crowd_models()
        except Exception as e:
            print(f"Warning: Could not initialize crowd models: {e}")
        
        self.year = 2026
        now = datetime.datetime.now()
        if now.year == 2026:
            self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            self.today = datetime.datetime(2026, now.month, now.day)
    
    def parse_date(self, date_str: str) -> datetime.datetime:
        """Parse date string to datetime object."""
        date_str = date_str.strip().lower()
        
        # Today
        if date_str in ['today', 'today?']:
            return self.today
        
        # Tomorrow
        if date_str in ['tomorrow', 'tomorrow?']:
            return self.today + datetime.timedelta(days=1)
        
        # Day of week
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day in enumerate(day_names):
            if date_str.startswith(day):
                days_ahead = i - self.today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return self.today + datetime.timedelta(days=days_ahead)
        
        # Try parsing as date
        for fmt in ['%Y-%m-%d', '%b %d, %Y', '%B %d, %Y', '%m/%d/%Y']:
            try:
                return datetime.datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return self.today
    
    def parse_month(self, query: str) -> datetime.datetime:
        """
        Parse month from query and return first day of that month.
        Handles: 'next month', specific month names, and month offsets.
        
        Returns:
            datetime object for the first day of the target month
        """
        query_lower = query.lower()
        
        # Next month
        if 'next month' in query_lower:
            if self.today.month == 12:
                return datetime.datetime(self.today.year + 1, 1, 1)
            else:
                return datetime.datetime(self.today.year, self.today.month + 1, 1)
        
        # Previous/last month
        if 'last month' in query_lower or 'previous month' in query_lower:
            if self.today.month == 1:
                return datetime.datetime(self.today.year - 1, 12, 1)
            else:
                return datetime.datetime(self.today.year, self.today.month - 1, 1)
        
        # Month names
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        for month_name, month_num in month_names.items():
            if month_name in query_lower:
                # If the month hasn't occurred yet this year, assume current year
                # Only use next year if the entire month has already passed
                target_date = datetime.datetime(self.today.year, month_num, 1)
                
                # Check if the entire month has passed (compare end of month, not start)
                # Get the last day of the target month
                if month_num == 12:
                    month_end = datetime.datetime(self.today.year + 1, 1, 1)
                else:
                    month_end = datetime.datetime(self.today.year, month_num + 1, 1)
                month_end = month_end - datetime.timedelta(days=1)  # Last day of month
                
                # If the entire month has passed, use next year
                if month_end < self.today and 'last' not in query_lower and 'previous' not in query_lower:
                    target_date = datetime.datetime(self.today.year + 1, month_num, 1)
                return target_date
        
        # Default to current month
        return datetime.datetime(self.today.year, self.today.month, 1)
    
    def parse_specific_date(self, query: str) -> datetime.datetime:
        """
        Parse a specific date from the query (e.g., "March 15", "Mar 15", "15th March").
        
        Returns:
            datetime object for the specified date
        """
        import re
        query_lower = query.lower()
        
        # Month names and their numeric values
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # Find day number (1-31)
        day_match = re.search(r'\b(\d{1,2})(st|nd|rd|th)?\b', query_lower)
        day = None
        if day_match:
            day = int(day_match.group(1))
        
        # Find month name
        month = None
        for month_name, month_num in month_names.items():
            if month_name in query_lower:
                month = month_num
                break
        
        if month and day:
            # Create date in 2026
            try:
                target_date = datetime.datetime(2026, month, day)
                # If this date is in the past, don't adjust - it's a valid date to query
                return target_date
            except ValueError:
                # Invalid date (e.g., Feb 30)
                pass
        
        # Fallback to current date
        return self.today
    
    def parse_dynamic_date(self, days_offset: int) -> datetime.datetime:
        """Parse relative date with day offset."""
        return self.today + datetime.timedelta(days=days_offset)
    
    def get_weekend_status(self, date: datetime.datetime) -> str:
        """Check if date is weekend (Saturday or Sunday)."""
        weekday = date.weekday()
        if weekday == 5:  # Saturday
            return "🟦 WEEKEND (Saturday)"
        elif weekday == 6:  # Sunday
            return "🟦 WEEKEND (Sunday)"
        else:
            return ""
    
    def get_crowd_level_category(self, visitors: int) -> tuple:
        """Get crowd level category, emoji, and description using trained model statistics."""
        # Use model-based percentile thresholds instead of hardcoded values
        # This dynamically adjusts based on the trained model's predictions
        
        # Calculate percentile thresholds from model forecasts (7-day average)
        dates = [self.today + datetime.timedelta(days=i) for i in range(7)]
        predictions = []
        for date in dates:
            pred = predict_crowd_for_date(date)
            if pred > 0:
                predictions.append(pred)
        
        if predictions:
            # Use statistical percentiles from model predictions
            p75 = numpy.percentile(predictions, 75)  # High crowd threshold
            p50 = numpy.percentile(predictions, 50)  # Medium crowd threshold
            p25 = numpy.percentile(predictions, 25)  # Low crowd threshold
        else:
            # Fallback to default percentiles if no predictions available
            p75 = 400
            p50 = 250
            p25 = 150
        
        # Classify based on model-derived percentiles
        if visitors > p75:
            return "Very Busy", "🔴", "High crowds - consider alternative times"
        elif visitors > p50:
            return "Busy", "🟠", "Moderate crowds - plan ahead"
        elif visitors > p25:
            return "Moderate", "🟡", "Decent crowds - manage your time"
        elif visitors > (p25 * 0.5):  # Below 50% of low threshold
            return "Light", "🟢", "Few crowds - great for exploring"
        else:
            return "Quiet", "🟢", "Very few crowds - peaceful visit"
    
    def handle_best_days_query(self, query: str = "") -> str:
        """
        Return best 7 days to visit combining weather and crowd data.
        If a specific month is mentioned, show best days in that month.
        """
        # Check if a specific month is mentioned
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        query_lower = query.lower()
        target_month = None
        
        for month_name, month_num in month_names.items():
            if month_name in query_lower:
                target_month = month_num
                break
        
        # If a specific month is mentioned, get all days in that month
        if target_month:
            if target_month <= self.today.month and target_month != 12:
                # If asking for a past month, assume next year
                year = self.today.year + 1
            else:
                year = self.today.year
            
            # Get first and last day of target month
            if target_month == 12:
                month_start = datetime.datetime(year, 12, 1)
                month_end = datetime.datetime(year + 1, 1, 1)
            else:
                month_start = datetime.datetime(year, target_month, 1)
                month_end = datetime.datetime(year, target_month + 1, 1)
            
            days_in_month = (month_end - month_start).days
            dates = [month_start + datetime.timedelta(days=i) for i in range(days_in_month)]
            month_label = month_start.strftime('%B %Y')
        else:
            # Default: next 7 days
            dates = [self.today + datetime.timedelta(days=i) for i in range(7)]
            month_label = "This Week"
        
        # Get weather data
        weather_data = get_weather_dict_for_dates(dates)
        
        # Get crowd data
        crowd_data = get_crowd_dict_for_dates(dates)
        
        # Create combined scoring
        combined_scores = []
        for i, date in enumerate(dates):
            weather = weather_data[i]
            crowd = crowd_data[i]
            
            # Weather score (0-10, higher is better)
            temp_score = 10 - abs(weather['temperature_celsius'] - 26) * 0.4
            temp_score = max(0, min(10, temp_score))
            rain_penalty = weather['rainfall_mm'] * 0.8
            wind_penalty = weather['wind_speed_ms'] * 0.2
            weather_score = max(0, temp_score - rain_penalty - wind_penalty)
            
            # Crowd score (0-10, where moderate crowds are ideal for tourists)
            visitors = crowd['visitors']
            if 150 <= visitors <= 400:
                crowd_score = 10
            elif visitors < 100:
                crowd_score = 5 + (visitors / 100) * 5
            elif visitors > 500:
                crowd_score = max(2, 10 - (visitors - 400) / 100)
            else:
                crowd_score = 7
            
            # Combined score
            overall_score = (weather_score * 0.4) + (crowd_score * 0.6)
            
            is_weekend = date.weekday() >= 5
            
            combined_scores.append({
                'date': date,
                'weather': weather,
                'crowd': crowd,
                'weather_score': weather_score,
                'crowd_score': crowd_score,
                'overall_score': overall_score,
                'is_weekend': is_weekend
            })
        
        # Sort by overall score (best first) and take top 7
        best_days = sorted(combined_scores, key=lambda x: x['overall_score'], reverse=True)[:7]
        
        # Build response
        response = f"🏆 BEST DAYS TO VISIT SIGIRIYA - {month_label} 🏆\n"
        response += "═" * 50 + "\n\n"
        response += "📊 Ranked by weather & crowd conditions:\n\n"
        
        for rank, day_data in enumerate(best_days, 1):
            date = day_data['date']
            weather = day_data['weather']
            crowd = day_data['crowd']
            
            date_str = date.strftime('%b %d')
            day_name = date.strftime('%A')
            weekend_icon = "🟦 " if date.weekday() >= 5 else ""
            crowd_level, crowd_emoji, _ = self.get_crowd_level_category(crowd['visitors'])
            
            # Weather icon
            if 'Clear' in weather['weather_condition']:
                weather_icon = "☀️"
            elif 'Rain' in weather['weather_condition']:
                weather_icon = "🌧️"
            elif 'Cloudy' in weather['weather_condition']:
                weather_icon = "☁️"
            else:
                weather_icon = "🌤️"
            
            # Build day entry - CROWD ONLY, NO WEATHER
            response += f"#{rank}. {weekend_icon}{date_str} ({day_name})\n"
            response += f"    👥 {crowd_emoji} {crowd_level} ({crowd['visitors']} visitors)\n"
            response += f"    ⭐ Score: {day_data['overall_score']:.1f}/10\n\n"
        
        return response.strip()
    
    def handle_today_crowd_query(self) -> str:
        """Handle 'is it crowded today?' type queries - show only crowd data."""
        date = self.today
        crowd_data = get_crowd_dict_for_dates([date])[0]
        
        level, symbol, desc = self.get_crowd_level_category(crowd_data['visitors'])
        is_weekend = "on the weekend" if date.weekday() >= 5 else "on a weekday"
        
        date_str = date.strftime('%A, %B %d')
        response = f"Today, {date_str} ({is_weekend}), we're expecting around {int(crowd_data['visitors'])} visitors to Sigiriya. "
        response += f"That's {level}. {desc}"
        
        return response.strip()
    
    def handle_specific_date_crowd_weather_query(self, date: datetime.datetime) -> str:
        """
        Handle queries about crowd on a specific date.
        Shows ONLY crowd data (not weather).
        """
        crowd_data = get_crowd_dict_for_dates([date])[0]
        
        date_str = date.strftime('%A, %B %d, %Y')
        level, symbol, desc = self.get_crowd_level_category(crowd_data['visitors'])
        is_weekend = "on the weekend" if date.weekday() >= 5 else "on a weekday"
        
        response = f"On {date_str} ({is_weekend}), we're expecting around {int(crowd_data['visitors'])} visitors. "
        response += f"That's {level}. {desc}"
        
        return response.strip()
    
    def handle_week_crowd_query(self) -> str:
        """Handle 'what will be the crowd this week?' type queries - show only crowd data."""
        dates = [self.today + datetime.timedelta(days=i) for i in range(7)]
        crowd_data = get_crowd_dict_for_dates(dates)
        
        # Find best and worst days
        all_visitors = [d['visitors'] for d in crowd_data]
        avg_visitors = sum(all_visitors) / len(all_visitors)
        quiet_day_idx = min(enumerate(all_visitors), key=lambda x: x[1])[0]
        busy_day_idx = max(enumerate(all_visitors), key=lambda x: x[1])[0]
        
        quiet_day_name = dates[quiet_day_idx].strftime('%A')
        busy_day_name = dates[busy_day_idx].strftime('%A')
        quiet_crowd = int(all_visitors[quiet_day_idx])
        busy_crowd = int(all_visitors[busy_day_idx])
        
        response = f"Over the next week, we're expecting varying crowds. On average, about {int(avg_visitors)} visitors a day. "
        response += f"{quiet_day_name} looks like the quietest day with around {quiet_crowd} visitors expected, "
        response += f"while {busy_day_name} will be busier with approximately {busy_crowd} visitors. "
        response += f"If you prefer fewer crowds, I'd recommend visiting on a weekday rather than the weekend."
        
        return response.strip()
    
    def handle_weekend_crowd_query(self) -> str:
        """Handle 'what will be the crowd on weekends?' type queries - show only crowd data."""
        # Get upcoming Saturdays and Sundays for the next month
        weekends = []
        current_date = self.today
        while len(weekends) < 8:  # Get 4 weekends (8 weekend days)
            if current_date.weekday() >= 5:  # Saturday or Sunday
                weekends.append(current_date)
            current_date += datetime.timedelta(days=1)
        
        crowd_data = get_crowd_dict_for_dates(weekends)
        
        # Calculate weekend statistics
        all_visitors = [c['visitors'] for c in crowd_data]
        avg_weekend = int(sum(all_visitors) / len(all_visitors))
        peak_weekend_idx = all_visitors.index(max(all_visitors))
        quiet_weekend_idx = all_visitors.index(min(all_visitors))
        
        busiest_day = weekends[peak_weekend_idx].strftime('%A')
        quietest_day = weekends[quiet_weekend_idx].strftime('%A')
        
        response = f"On weekends, the crowds tend to be higher than weekdays. On average, you can expect about {avg_weekend} visitors. "
        response += f"{quietest_day} tends to be the quietest with around {int(all_visitors[quiet_weekend_idx])} visitors, "
        response += f"while {busiest_day} is usually the busiest with about {int(all_visitors[peak_weekend_idx])} visitors expected."
        
        return response.strip()
    
    def handle_year_crowd_query(self) -> str:
        """Handle 'what will be the crowd this year?' type queries - show only crowd data."""
        # Get data for entire 2026 year (12 months, one date per month)
        dates = []
        for month in range(1, 13):
            # Use 15th of each month for overview
            dates.append(datetime.datetime(2026, month, 15))
        
        crowd_data = get_crowd_dict_for_dates(dates)
        
        response = "ANNUAL CROWD FORECAST - 2026\n"
        response += "─" * 40 + "\n\n"
        
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        
        for i, crowd in enumerate(crowd_data):
            level, symbol, _ = self.get_crowd_level_category(crowd['visitors'])
            
            response += f"{months[i]}\n"
            response += f"  Crowd: {symbol} {level} ({crowd['visitors']} visitors)\n\n"
        
        # Annual statistics
        all_visitors = [c['visitors'] for c in crowd_data]
        avg_year = int(sum(all_visitors) / len(all_visitors))
        peak_month_idx = all_visitors.index(max(all_visitors))
        quiet_month_idx = all_visitors.index(min(all_visitors))
        
        response += "ANNUAL SUMMARY\n"
        response += f"  Average: {avg_year} visitors per month\n"
        response += f"  Peak Month: {months[peak_month_idx]} ({all_visitors[peak_month_idx]} visitors)\n"
        response += f"  Quietest Month: {months[quiet_month_idx]} ({all_visitors[quiet_month_idx]} visitors)\n"
        
        return response.strip()
    
    def handle_month_crowd_query(self, query: str) -> str:
        """
        Handle 'what will be the crowd in [month]?' type queries.
        Shows monthly summary with weather and crowd data.
        """
        month_start = self.parse_month(query)
        month_name = month_start.strftime('%B %Y')
        
        # Get all days in the month
        if month_start.month == 12:
            month_end = datetime.datetime(month_start.year + 1, 1, 1)
        else:
            month_end = datetime.datetime(month_start.year, month_start.month + 1, 1)
        
        days_in_month = (month_end - month_start).days
        dates = [month_start + datetime.timedelta(days=i) for i in range(days_in_month)]
        
        # Get crowd and weather data for the month
        crowd_data = get_crowd_dict_for_dates(dates)
        weather_data = get_weather_dict_for_dates(dates)
        
        # Validate we got data
        if not crowd_data or len(crowd_data) == 0:
            return f"❌ Unable to retrieve crowd data for {month_name}. Please ensure models are initialized."
        
        if not weather_data or len(weather_data) == 0:
            return f"❌ Unable to retrieve weather data for {month_name}. Please ensure models are initialized."
        
        response = f"MONTHLY CROWD FORECAST - {month_name}\n"
        response += "─" * 50 + "\n\n"
        
        # Monthly statistics
        all_visitors = [d['visitors'] for d in crowd_data if 'visitors' in d]
        
        if not all_visitors:
            return f"Error: No valid crowd data available for {month_name}."
        
        avg_visitors = int(sum(all_visitors) / len(all_visitors))
        peak_visitors = max(all_visitors)
        min_visitors = min(all_visitors)
        
        peak_day_idx = all_visitors.index(peak_visitors)
        quiet_day_idx = all_visitors.index(min_visitors)
        
        peak_date = dates[peak_day_idx]
        quiet_date = dates[quiet_day_idx]
        
        response += f"MONTHLY OVERVIEW\n"
        response += f"  Average: {avg_visitors} visitors/day\n"
        response += f"  Peak Day: {peak_date.strftime('%b %d')} ({peak_visitors} visitors)\n"
        response += f"  Quietest: {quiet_date.strftime('%b %d')} ({min_visitors} visitors)\n"
        response += f"  Range: {min_visitors} - {peak_visitors}\n\n"
        
        # Best weeks in the month
        response += f"CROWD LEVELS BY WEEK\n"
        week_starts = [0, 7, 14, 21, 28]
        
        for week_start in week_starts:
            if week_start < len(dates):
                week_end = min(week_start + 7, len(dates))
                week_visitors = all_visitors[week_start:week_end]
                week_avg = int(sum(week_visitors) / len(week_visitors))
                week_num = (week_start // 7) + 1
                
                week_level, week_symbol, _ = self.get_crowd_level_category(week_avg)
                response += f"  Week {week_num}: {week_symbol} {week_level} ({week_avg} avg visitors)\n"
        
        response += f"\nNote: Crowds in {month_name} range from {min_visitors} to {peak_visitors} visitors per day.\n"
        
        return response.strip()
    
    def handle_best_months_query(self) -> str:
        """
        Return best months to visit combining weather and crowd data.
        """
        dates = []
        for month in range(1, 13):
            dates.append(datetime.datetime(2026, month, 15))
        
        # Get weather data
        weather_data = get_weather_dict_for_dates(dates)
        
        # Get crowd data
        crowd_data = get_crowd_dict_for_dates(dates)
        
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        
        # Create combined scoring
        combined_scores = []
        for i, date in enumerate(dates):
            weather = weather_data[i]
            crowd = crowd_data[i]
            
            # Weather score (0-10, higher is better)
            temp_score = 10 - abs(weather['temperature_celsius'] - 26) * 0.4
            temp_score = max(0, min(10, temp_score))
            rain_penalty = weather['rainfall_mm'] * 0.8
            wind_penalty = weather['wind_speed_ms'] * 0.2
            weather_score = max(0, temp_score - rain_penalty - wind_penalty)
            
            # Crowd score (0-10, where moderate crowds are ideal for tourists)
            visitors = crowd['visitors']
            if 150 <= visitors <= 400:
                crowd_score = 10
            elif visitors < 100:
                crowd_score = 5 + (visitors / 100) * 5
            elif visitors > 500:
                crowd_score = max(2, 10 - (visitors - 400) / 100)
            else:
                crowd_score = 7
            
            # Combined score
            overall_score = (weather_score * 0.4) + (crowd_score * 0.6)
            
            combined_scores.append({
                'month': months[i],
                'weather': weather,
                'crowd': crowd,
                'weather_score': weather_score,
                'crowd_score': crowd_score,
                'overall_score': overall_score
            })
        
        # Sort by overall score (best first)
        best_months = sorted(combined_scores, key=lambda x: x['overall_score'], reverse=True)
        
        # Build response
        response = "🏆 BEST MONTHS TO VISIT SIGIRIYA 🏆\n"
        response += "═" * 50 + "\n\n"
        response += "📊 Ranked by weather & crowd conditions:\n\n"
        
        for rank, month_data in enumerate(best_months, 1):
            month = month_data['month']
            weather = month_data['weather']
            crowd = month_data['crowd']
            
            crowd_level, crowd_emoji, _ = self.get_crowd_level_category(crowd['visitors'])
            
            # Weather icon
            if 'Clear' in weather['weather_condition']:
                weather_icon = "☀️"
            elif 'Rain' in weather['weather_condition']:
                weather_icon = "🌧️"
            elif 'Cloudy' in weather['weather_condition']:
                weather_icon = "☁️"
            else:
                weather_icon = "🌤️"
            
            # Build month entry
            response += f"#{rank}. {month}\n"
            response += f"    🌡️ {weather_icon} {weather['temperature_celsius']}°C | {weather['weather_condition']}\n"
            response += f"    👥 {crowd_emoji} {crowd_level} ({crowd['visitors']} visitors)\n"
            response += f"    ⭐ Score: {month_data['overall_score']:.1f}/10\n\n"
        
        return response.strip()

    def handle_query(self, query: str) -> str:
        """
        Handle crowd-related queries with comprehensive pattern matching.
        Uses trained model data for all crowd predictions.
        
        Args:
            query: Natural language question about crowd
        
        Returns:
            Crowd prediction response
        """
        query_lower = query.lower()
        
        # ============================================================
        # Pattern detection for various question types
        # ============================================================
        
        # Keywords to detect
        crowd_keywords = ['crowd', 'busy', 'visitor', 'people', 'how many', 'crowded', 'crowds', 'packed', 'busy']
        weather_keywords = ['weather', 'temperature', 'temp', 'rain', 'rainfall', 'wind', 'forecast', 'climate', 'hot', 'cold', 'warm', 'windy', 'sunny', 'clear', 'sky']
        
        weather_specific = any(kw in query_lower for kw in weather_keywords)
        crowd_specific = any(kw in query_lower for kw in crowd_keywords)
        
        # Extract date/time indicators
        import re
        has_day_number = re.search(r'\b(\d{1,2})(st|nd|rd|th)?\b', query_lower) is not None
        has_month_name = any(month in query_lower for month in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])
        
        # ============================================================
        # PRIORITY 1: TODAY/NOW CROWD (all variations)
        # ============================================================
        if any(phrase in query_lower for phrase in ['today', 'now', 'right now', 'at the moment', 'currently', 'is it crowded', 'how crowded', 'how many people', 'how many visitors']):
            if any(word in query_lower for word in ['crowd', 'busy', 'visitor', 'people', 'crowded']) or 'today' in query_lower or 'now' in query_lower:
                return self.handle_today_crowd_query()
        
        # ============================================================
        # PRIORITY 2: BEST DAYS/DATES TO VISIT
        # ============================================================
        best_keywords = ['best day', 'best days', 'best date', 'best dates', 'good day', 'good days', 'ideal day', 'perfect day', 'when should', 'when to visit', 'best time', 'recommend', 'suggest', 'which day', 'which days', 'quiet', 'least crowded', 'empty']
        if any(keyword in query_lower for keyword in best_keywords):
            return self.handle_best_days_query(query)
        
        # ============================================================
        # PRIORITY 3: SPECIFIC DATE CROWD
        # ============================================================
        if has_day_number and has_month_name and crowd_specific:
            date = self.parse_specific_date(query)
            return self.handle_specific_date_crowd_weather_query(date)
        
        # ============================================================
        # PRIORITY 4: MONTH CROWD FORECAST
        # ============================================================
        month_keywords = ['month', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec', 'next month', 'this month', 'last month']
        if any(keyword in query_lower for keyword in month_keywords):
            if has_month_name or 'next month' in query_lower or 'this month' in query_lower or 'last month' in query_lower:
                return self.handle_month_crowd_query(query)
        
        # ============================================================
        # PRIORITY 5: BEST MONTHS TO VISIT
        # ============================================================
        if any(keyword in query_lower for keyword in ['best month', 'best months', 'ideal month', 'ideal months', 'quiet month', 'quietest month']):
            return self.handle_best_months_query()
        
        # ============================================================
        # PRIORITY 6: YEAR FORECAST
        # ============================================================
        if any(keyword in query_lower for keyword in ['year', 'entire year', 'throughout the year', 'all year', '2026', 'this year', 'annual']):
            if 'month' not in query_lower or (has_month_name and 'year' in query_lower):
                return self.handle_year_crowd_query()
        
        # ============================================================
        # PRIORITY 7: WEEKEND CROWD
        # ============================================================
        if any(keyword in query_lower for keyword in ['weekend', 'weekends', 'saturday', 'sunday', 'sat', 'sun']):
            return self.handle_weekend_crowd_query()
        
        # ============================================================
        # PRIORITY 8: WEEK CROWD FORECAST
        # ============================================================
        if any(keyword in query_lower for keyword in ['week', 'this week', 'next week', 'weekly', '7 days', 'seven days']):
            return self.handle_week_crowd_query()
        
        # ============================================================
        # DEFAULT: Handle generic crowd questions
        # ============================================================
        if crowd_specific:
            # If it's a crowd question but no pattern matched, show weekly forecast
            return self.handle_week_crowd_query()
        
        return "I can help you with crowd predictions! Ask about:\n- Crowd today/now\n- Crowd on a specific date\n- Best days/dates to visit\n- Crowd this week/next week\n- Crowd in a specific month\n- Best months to visit\n- Weekend crowds\n- Annual patterns"


# Global instance
_crowd_handler = None


def get_crowd_handler():
    """Get or create crowd handler instance."""
    global _crowd_handler
    if _crowd_handler is None:
        _crowd_handler = CrowdHandler()
    return _crowd_handler


def process_crowd_query(query: str) -> str:
    """Process a crowd-related query."""
    # Check location validation first
    should_reject, error_message = should_reject_query(query)
    if should_reject:
        return error_message
    
    handler = get_crowd_handler()
    return handler.handle_query(query)

