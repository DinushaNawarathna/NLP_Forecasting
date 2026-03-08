"""
Real-Time Question Handler for Sigiriya Tourism

Handles specific real-time questions about visiting Sigiriya including:
- Best days to visit next week
- Will next week be best to visit
- Crowd predictions for specific time periods
- Best months to visit
- Day recommendations

Uses trained crowd and weather models for predictions.
"""

import datetime
import re
from typing import Tuple, List, Dict, Optional, Union
import numpy
from crowd_prediction import get_crowd_for_dates, get_crowd_dict_for_dates, predict_crowd_for_date, initialize_crowd_models
from weather_prediction import get_weather_dict_for_dates, get_best_weather_dates, initialize_models as initialize_weather_models
from location_validator import should_reject_query


class RealTimeQuestionHandler:
    """Handles real-time visitor and weather related questions."""
    
    def __init__(self):
        """Initialize the handler with crowd and weather models."""
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
    
    def process_real_time_question(self, question: str) -> Optional[Union[str, dict]]:
        """
        Process a real-time question and return answer.
        Returns None if question doesn't match any patterns.
        """
        q_lower = question.lower().strip()
        
        # Remove common punctuation
        q_clean = q_lower.rstrip('?!')
        
        # Check for greetings FIRST (highest priority)
        if self._is_greeting(q_clean):
            return self._handle_greeting(question)
        
        # Check for comparison queries (days or months) - is X better than Y?
        if self._is_comparison_query(q_clean):
            return self._handle_comparison(question)
        
        # Check for specific day queries (is Sunday good? should I visit on Monday?)
        if self._is_specific_day_query(q_clean):
            return self._handle_specific_day(question)
        
        # Check for YES/NO crowd questions
        if self._is_yes_no_crowd_question(q_clean):
            return self._handle_yes_no_crowd_question(question)
        
        # Check for different question patterns
        if self._is_best_day_next_week_query(q_clean):
            return self._handle_best_day_next_week(question)
        
        if self._is_best_days_in_month_query(q_clean):
            return self._handle_best_days_in_month(question)
        
        if self._is_best_days_this_year_query(q_clean):
            return self._handle_best_days_this_year(question)
        
        if self._is_week_quality_query(q_clean):
            return self._handle_will_next_week_be_best(question)
        
        if self._is_crowd_next_week_query(q_clean):
            return self._handle_crowd_next_week(question)
        
        if self._is_best_months_query(q_clean):
            return self._handle_best_months_to_visit(question)
        
        if self._is_when_to_visit_query(q_clean):
            return self._handle_when_to_visit(question)
        
        if self._is_good_day_recommendation_query(q_clean):
            return self._handle_day_recommendation(question)
        
        if self._is_crowd_next_few_days_query(q_clean):
            return self._handle_crowd_next_few_days(question)
        
        if self._is_best_weekend_query(q_clean):
            return self._handle_best_weekend(question)
        
        if self._is_specific_month_recommendation_query(q_clean):
            return self._handle_specific_month_recommendation(question)
        
        if self._is_seasonal_recommendation_query(q_clean):
            return self._handle_seasonal_recommendation(question)
        
        return None
    
    # ========================================================================
    # GREETING HANDLER (Highest Priority - greet the user)
    # ========================================================================
    
    def _is_greeting(self, q: str) -> bool:
        """Check if user is greeting the bot."""
        greeting_patterns = [
            r'^hi\b', r'^hello\b', r'^hey\b',
            r'^good morning', r'^good afternoon', r'^good evening',
            r'^howdy', r'^greetings',
            r'^what\'s up', r'^whats up',
            r'^how are you', r'^how do you do',
            r'^welcome',
        ]
        return any(re.search(p, q) for p in greeting_patterns)
    
    def _handle_greeting(self, question: str) -> str:
        """Respond to user greetings with natural, simple responses."""
        greeting_responses = [
            "👋 Hi there! How can I help you with Sigiriya today?",
            "👋 Hello! What would you like to know?",
            "🏔️ Hey! What can I help you with?",
            "👋 Hi! Feel free to ask me anything about visiting Sigiriya.",
            "😊 Good to see you! What's on your mind?",
            "👋 Hello! How can I assist you?",
        ]
        
        import random
        return random.choice(greeting_responses)
    
    # ========================================================================
    # SPECIFIC DAY & COMPARISON HANDLERS
    # ========================================================================
    
    def _is_specific_day_query(self, q: str) -> bool:
        """Check if asking about a specific day (e.g., 'is Sunday good?', 'should I visit on Monday?')"""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        
        patterns = [
            r'is\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday).*good',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday).*good.*visit',
            r'should\s+i.*visit.*on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'is\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday).*to.*visit',
            r'can\s+i.*visit.*on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(mon|tue|wed|thu|fri|sat|sun).*good',
            # New patterns to catch "Is Sunday good to visit?" style
            r'is\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+good\s+to\s+visit',
            r'is\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+good\s+for\s+visiting',
            r'should\s+i\s+visit\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            # Catch "is it good on Friday?" pattern
            r'is\s+it\s+good\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'is\s+it\s+.*on\s+(friday|saturday|sunday|monday|tuesday|wednesday|thursday)',
            # Catch visit + day pattern
            r'visit.*on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday).*visit',
            r'how\s+is\s+the\s+situation.*on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'how\s+is.*(friday|saturday|sunday|monday|tuesday|wednesday|thursday)',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.*(next|this).*week',

        ]
        
        return any(re.search(p, q) for p in patterns)
    
    def _is_comparison_query(self, q: str) -> bool:
        """Check if comparing days or months (e.g., 'is Sunday better than Saturday?', 'January vs April?')"""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december',
                  'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                  'janury', 'janry']
        
        comparison_patterns = [
            r'\bor\b',
            r'\bvs\b',
            r'better than',
            r'which.*better',
            r'compare',
        ]
        
        has_compare_intent = any(re.search(p, q) for p in comparison_patterns)
        
        # Count mentions of days and months
        day_mentions = len([d for d in days if d in q])
        month_mentions = len([m for m in months if m in q])
        total_mentions = day_mentions + month_mentions
        
        return has_compare_intent and total_mentions >= 2
    
    def _extract_day_name(self, text: str) -> Optional[str]:
        """Extract a day name from text."""
        day_map = {
            'monday': 'Monday',
            'mon': 'Monday',
            'tuesday': 'Tuesday',
            'tue': 'Tuesday',
            'wednesday': 'Wednesday',
            'wed': 'Wednesday',
            'thursday': 'Thursday',
            'thu': 'Thursday',
            'friday': 'Friday',
            'fri': 'Friday',
            'saturday': 'Saturday',
            'sat': 'Saturday',
            'sunday': 'Sunday',
            'sun': 'Sunday',
        }
        
        text_lower = text.lower()
        # Check longer day names first (to avoid matching 'sat' in 'saturday')
        for day_name in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            if day_name in text_lower:
                return day_map[day_name]
        # Then check short names
        for day_name in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            if day_name in text_lower:
                return day_map[day_name]
        return None
    
    def _get_next_occurrence_of_day(self, target_day: str) -> datetime.datetime:
        """Get the next occurrence of a specific day of week."""
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        target_day_lower = target_day.lower()[:3]
        
        day_mapping = {
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
        }
        
        target_weekday = day_mapping.get(target_day_lower, 0)
        current_weekday = self.today.weekday()
        
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        return self.today + datetime.timedelta(days=days_ahead)
    
    def _handle_specific_day(self, question: str) -> str:
        """Handle specific day queries like 'is Sunday good to visit?'"""
        day_name = self._extract_day_name(question)
        if not day_name:
            return "Could you clarify which day you're asking about?"
        
        target_date = self._get_next_occurrence_of_day(day_name)
        
        try:
            crowd_list = get_crowd_dict_for_dates([target_date])
            weather_list = get_weather_dict_for_dates([target_date])
            
            # Lists are returned, so get the first (and only) item
            crowd_data = crowd_list[0] if crowd_list else {}
            weather_data = weather_list[0] if weather_list else {}
            
            crowd = crowd_data.get('visitors', 'unknown')
            temp = weather_data.get('temperature_celsius', None)
            rainfall = weather_data.get('rainfall_mm', None)
            
            # Format date nicely
            date_str = target_date.strftime('%A, %B %d')
            
            response = f"☀️ On {date_str}:\n"
            
            if crowd and crowd != 'unknown':
                crowd_level = 'light' if crowd < 2000 else 'moderate' if crowd < 4000 else 'busy'
                response += f"Expected crowd {crowd_level} (~{int(crowd)} visitors)\n"
            
            if temp is not None:
                response += f"Temperature {temp:.1f}°C\n"
            
            if rainfall is not None and rainfall > 0:
                response += f"Rainfall {rainfall:.1f}mm\n"
            elif rainfall is not None:
                response += f"No rain expected\n"
            
            # Give recommendation
            if crowd and crowd < 3000 and (temp is None or temp < 32):
                response += f"\nYes, {day_name} looks like a great day to visit"
            elif crowd and crowd < 4000:
                response += f"\n{day_name} should be good, though there might be some crowds"
            elif crowd and crowd >= 4000:
                response += f"\n{day_name} might be quite busy. Consider visiting early in the morning"
            
            return response
        except Exception as e:
            return f"I couldn't get specific data for {day_name}, but feel free to ask about general weather or crowd trends."
    
    def _handle_comparison(self, question: str) -> str:
        """Handle comparison queries for both days and months."""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december',
                  'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                  'janury', 'janry']
        
        q_lower = question.lower()
        
        # Check what type of comparison: days or months
        day_mentions = [d for d in days if d in q_lower]
        month_mentions = [m for m in months if m in q_lower]
        
        if len(day_mentions) >= 2 and len(month_mentions) == 0:
            return self._compare_days(day_mentions, question)
        elif len(month_mentions) >= 2 and len(day_mentions) == 0:
            return self._compare_months(month_mentions, question)
        elif len(month_mentions) >= 2:
            return self._compare_months(month_mentions, question)
        elif len(day_mentions) >= 2:
            return self._compare_days(day_mentions, question)
        else:
            return "Please specify two items to compare (e.g., 'January or April', 'Friday vs Saturday')."
    
    def _compare_days(self, day_mentions: List[str], question: str) -> str:
        """Compare specific days of the week."""
        day_names_map = {
            'monday': 'Monday', 'mon': 'Monday',
            'tuesday': 'Tuesday', 'tue': 'Tuesday',
            'wednesday': 'Wednesday', 'wed': 'Wednesday',
            'thursday': 'Thursday', 'thu': 'Thursday',
            'friday': 'Friday', 'fri': 'Friday',
            'saturday': 'Saturday', 'sat': 'Saturday',
            'sunday': 'Sunday', 'sun': 'Sunday',
        }
        
        day1_key = day_mentions[0]
        day2_key = day_mentions[1]
        day1_name = day_names_map.get(day1_key, day1_key.capitalize())
        day2_name = day_names_map.get(day2_key, day2_key.capitalize())
        
        try:
            date1 = self._get_next_occurrence_of_day(day1_name)
            date2 = self._get_next_occurrence_of_day(day2_name)
            
            crowd_list = get_crowd_dict_for_dates([date1, date2])
            weather_list = get_weather_dict_for_dates([date1, date2])
            
            crowd1 = crowd_list[0].get('visitors', 0) if crowd_list else 0
            crowd2 = crowd_list[1].get('visitors', 0) if len(crowd_list) > 1 else 0
            temp1 = weather_list[0].get('temperature_celsius', 25) if weather_list else 25
            temp2 = weather_list[1].get('temperature_celsius', 25) if len(weather_list) > 1 else 25
            rain1 = weather_list[0].get('rainfall_mm', 0) if weather_list else 0
            rain2 = weather_list[1].get('rainfall_mm', 0) if len(weather_list) > 1 else 0
            
            response = f"Comparing {day1_name} vs {day2_name}\n\n"
            
            response += f"{day1_name}\n"
            response += f"  Crowd {int(crowd1)} visitors\n"
            response += f"  Temp {temp1:.1f}°C\n"
            response += f"  Rain {rain1:.1f}mm\n\n"
            
            response += f"{day2_name}\n"
            response += f"  Crowd {int(crowd2)} visitors\n"
            response += f"  Temp {temp2:.1f}°C\n"
            response += f"  Rain {rain2:.1f}mm\n\n"
            
            # Winner analysis
            day1_score = (10 - (crowd1 / 500)) + (temp1 / 30 * 5) + (5 - (rain1 / 5))
            day2_score = (10 - (crowd2 / 500)) + (temp2 / 30 * 5) + (5 - (rain2 / 5))
            
            if day1_score > day2_score:
                response += f"Winner {day1_name} is better to visit"
            elif day2_score > day1_score:
                response += f"Winner {day2_name} is better to visit"
            else:
                response += f"Both days have similar conditions"
            
            return response
        except Exception as e:
            return f"I couldn't compare those days. Try asking about them separately."
    
    # ========================================================================
    # PATTERN DETECTION METHODS
    # ========================================================================
    
    def _is_yes_no_crowd_question(self, q: str) -> bool:
        """Check if question is a yes/no crowd question like 'is sigiriya crowded now/today?'"""
        patterns = [
            r'is.*crowd',
            r'crowded.*now',
            r'crowded.*today',
            r'is.*busy',
            r'busy.*today',
            r'busy.*now',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_best_days_this_year_query(self, q: str) -> bool:
        """Check if asking for best days to visit this year or throughout the year."""
        patterns = [
            r'best day.*this year',
            r'best day.*throughout.*year',
            r'best day.*year',
            r'best days.*this year',
            r'best days.*2026',
            r'good day.*this year',
            r'when.*best.*this year',
            r'best time.*this year',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_best_day_next_week_query(self, q: str) -> bool:
        """Check if question is asking for best day next week."""
        patterns = [
            r'best day.*next week',
            r'good day.*next week',
            r'when.*next week.*visit',
            r'next week.*when.*visit',
            r'which day.*next week',
            r'recommend.*day.*next week',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_best_days_in_month_query(self, q: str) -> bool:
        """Check if asking for best days/dates in a specific month - supports many phrasings."""
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december',
                  'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
                  'next month', 'this month']
        
        # More specific keywords that clearly indicate asking about best days
        # Removed overly generic words like 'visiting', 'suggest', 'recommend'
        best_keywords = [
            'best day', 'best days', 'best date', 'best dates',
            'good day', 'good days', 'good date', 'good dates',
            'ideal day', 'ideal days',
            'perfect day', 'perfect days',
            'when to visit', 'when should i visit', 'when can i visit',
            'when is best', 'best time',
            'what day', 'which day', 'which days',
        ]
        
        in_month_patterns = [
            r'in\s+\w+',  # "in april", "in may", etc
            r'during\s+\w+',
            r'for\s+\w+',
        ]
        
        # Check if it has a month keyword
        has_month = any(month in q for month in months)
        
        # Check if it has best/good/ideal keywords
        has_best_keyword = any(keyword in q for keyword in best_keywords)
        
        # Check for "in/during/for" + month pattern
        has_in_month = any(re.search(p, q) for p in in_month_patterns)
        
        return has_month and (has_best_keyword or has_in_month)
    
    def _is_week_quality_query(self, q: str) -> bool:
        """Check if asking if next week will be good to visit."""
        patterns = [
            r'will.*next week.*best',
            r'is.*next week.*good',
            r'next week.*best time',
            r'good time.*next week',
            r'next week.*crowded',
            r'expect.*crowds.*next week',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_crowd_next_week_query(self, q: str) -> bool:
        """Check if asking about crowd next week."""
        patterns = [
            r'crowd.*next week',
            r'how many.*next week',
            r'visitors.*next week',
            r'busy.*next week',
            r'packed.*next week',
            r'crowded.*next week',
            r'people.*next week',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_best_months_query(self, q: str) -> bool:
        """Check if asking about best months to visit."""
        patterns = [
            r'best months?.*visit',
            r'good months?.*visit',
            r'when.*best.*month',
            r'quietest months?',
            r'least crowded.*months?',
            r'ideal months?.*visit',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_when_to_visit_query(self, q: str) -> bool:
        """Check if asking when to visit in general."""
        patterns = [
            r'when.*best.*visit',
            r'when.*good.*visit',
            r'best time.*visit',
            r'when should i visit',
            r'any recommendation.*when',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_good_day_recommendation_query(self, q: str) -> bool:
        """Check if asking for a good day recommendation."""
        patterns = [
            r'give me.*good day',
            r'suggest.*good day',
            r'any good day.*recommend',
            r'what.*good day',
            r'recommend.*day.*visit',
            r'good day.*visit',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_crowd_next_few_days_query(self, q: str) -> bool:
        """Check if asking about crowd in next few days."""
        patterns = [
            r'crowd.*few days',
            r'visitors.*next.*days',
            r'busy.*coming days',
            r'packed.*this week',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_best_weekend_query(self, q: str) -> bool:
        """Check if asking about best weekend."""
        patterns = [
            r'best weekend',
            r'good weekend.*visit',
            r'crowded.*weekend',
            r'this weekend',
        ]
        return any(re.search(p, q) for p in patterns)
    
    def _is_specific_month_recommendation_query(self, q: str) -> bool:
        """Check if asking about specific month - but NOT about weather or crowd specifically."""
        # If asking specifically about weather or crowd, don't match this pattern
        weather_keywords = ['weather', 'temperature', 'temp', 'rain', 'rainfall', 'wind', 'celsius', 'degrees', 'hot', 'cold', 'warm']
        crowd_keywords = ['crowd', 'busy', 'visitor', 'people', 'how many', 'crowded', 'crowds', 'packed']
        
        # If explicitly asking about weather or crowd, DON'T match this pattern
        if any(kw in q for kw in weather_keywords + crowd_keywords):
            return False
        
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december']
        for month in months:
            if month in q:
                return True
        return False

    def _compare_months(self, month_mentions: List[str], question: str) -> str:
        """Compare specific months."""
        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            'janury': 1, 'janry': 1
        }

        month_names_full = ['January', 'February', 'March', 'April', 'May', 'June',
                            'July', 'August', 'September', 'October', 'November', 'December']
        
        # Get unique month numbers from mentions
        month_nums = list(set([month_map.get(m) for m in month_mentions if month_map.get(m)]))
        
        if len(month_nums) < 2:
            return "Please specify two different months to compare."
        
        month1, month2 = month_nums[0], month_nums[1]
        month1_name = month_names_full[month1 - 1]
        month2_name = month_names_full[month2 - 1]

        def compute_month_metrics(month_num: int) -> Dict:
            dates = [datetime.datetime(2026, month_num, d) for d in [5, 10, 15, 20]]
            crowd_data = get_crowd_dict_for_dates(dates)
            weather_data = get_weather_dict_for_dates(dates)

            avg_crowd = numpy.mean([c['visitors'] for c in crowd_data])
            avg_temp = numpy.mean([w['temperature_celsius'] for w in weather_data])
            avg_rain = numpy.mean([w['rainfall_mm'] for w in weather_data])

            crowd_score = 10 - (avg_crowd / 600 * 10)
            crowd_score = max(0, min(10, crowd_score))

            temp_score = 10 - abs(avg_temp - 26) * 0.3
            temp_score = max(0, min(10, temp_score))

            rain_score = 10 - (avg_rain / 20 * 10)
            rain_score = max(0, min(10, rain_score))

            overall = (crowd_score * 0.5) + (temp_score * 0.25) + (rain_score * 0.25)

            return {
                'month': month_names_full[month_num - 1],
                'avg_crowd': avg_crowd,
                'avg_temp': avg_temp,
                'avg_rain': avg_rain,
                'score': overall
            }

        month_1_data = compute_month_metrics(month1)
        month_2_data = compute_month_metrics(month2)

        response = f"Comparing {month_1_data['month']} vs {month_2_data['month']}\n\n"

        response += f"{month_1_data['month']}\n"
        response += f"  Avg Crowd {int(month_1_data['avg_crowd'])} visitors\n"
        response += f"  Avg Temp {month_1_data['avg_temp']:.1f}°C\n"
        response += f"  Avg Rain {month_1_data['avg_rain']:.1f}mm\n\n"

        response += f"{month_2_data['month']}\n"
        response += f"  Avg Crowd {int(month_2_data['avg_crowd'])} visitors\n"
        response += f"  Avg Temp {month_2_data['avg_temp']:.1f}°C\n"
        response += f"  Avg Rain {month_2_data['avg_rain']:.1f}mm\n\n"

        score_gap = abs(month_1_data['score'] - month_2_data['score'])
        
        if month_1_data['score'] > month_2_data['score']:
            response += f"Winner {month_1_data['month']} is better to visit"
        elif month_2_data['score'] > month_1_data['score']:
            response += f"Winner {month_2_data['month']} is better to visit"
        else:
            response += f"Both months have similar conditions"

        return response
    
    def _is_seasonal_recommendation_query(self, q: str) -> bool:
        """Check if asking about seasons."""
        patterns = [
            r'dry season',
            r'wet season',
            r'monsoon',
            r'summer',
            r'winter',
            r'spring',
            r'autumn',
        ]
        return any(re.search(p, q) for p in patterns)
    
    # ========================================================================
    # RESPONSE GENERATION METHODS
    # ========================================================================
    
    def _handle_yes_no_crowd_question(self, question: str) -> str:
        """Handle yes/no crowd questions like 'Is Sigiriya crowded now?' 'Is it crowded today?'"""
        today_visitors = get_crowd_dict_for_dates([self.today])[0]['visitors']
        
        # Determine if crowded (using 7-day average as reference)
        dates_7day = [self.today + datetime.timedelta(days=i) for i in range(7)]
        crowds_7day = get_crowd_dict_for_dates(dates_7day)
        avg_7day = numpy.mean([c['visitors'] for c in crowds_7day])
        
        is_crowded = today_visitors > avg_7day * 1.1
        
        date_str = self.today.strftime('%A, %B %d')
        
        if is_crowded:
            response = f"Yes, Sigiriya is quite crowded today. We're expecting around {int(today_visitors)} visitors, "
            response += f"which is higher than the average of about {int(avg_7day)} this week. "
            response += f"💡 If you prefer fewer crowds, I'd suggest visiting on a weekday or checking back later in the week."
        else:
            response = f"No, it's not too crowded today. We're expecting around {int(today_visitors)} visitors, "
            response += f"which is about average for this week. "
            response += f"🌄 It should be a pleasant day to visit Sigiriya!"
        
        return response
    
    def _handle_best_days_this_year(self, question: str) -> str:
        """Handle: 'What are the best days to visit this year?' - show top 10 days in 2026"""
        # Get full year 2026 (starting from today)
        remaining_days_2026 = (datetime.datetime(2026, 12, 31) - self.today).days + 1
        dates = [self.today + datetime.timedelta(days=i) for i in range(remaining_days_2026)]
        
        # Limit to reasonable range (e.g., next 200 days)
        dates = dates[:200]
        
        weather_data = get_weather_dict_for_dates(dates)
        crowd_data = get_crowd_dict_for_dates(dates)
        
        # Score each day
        scores = []
        for i, date in enumerate(dates):
            w = weather_data[i]
            c = crowd_data[i]
            
            # Weather score
            temp_score = 10 - abs(w['temperature_celsius'] - 25) * 0.4
            temp_score = max(0, min(10, temp_score))
            rain_penalty = w['rainfall_mm'] * 0.5
            wind_penalty = w['wind_speed_ms'] * 0.1
            weather_score = max(0, temp_score - rain_penalty - wind_penalty)
            
            # Crowd score
            visitors = c['visitors']
            if 150 <= visitors <= 400:
                crowd_score = 10
            elif visitors < 100:
                crowd_score = 5
            elif visitors > 500:
                crowd_score = max(2, 10 - (visitors - 400) / 100)
            else:
                crowd_score = 7
            
            # Combined score
            overall_score = (weather_score * 0.4) + (crowd_score * 0.6)
            
            scores.append({
                'date': date,
                'weather': w,
                'crowd': c,
                'weather_score': weather_score,
                'crowd_score': crowd_score,
                'overall_score': overall_score
            })
        
        # Get top 10 days
        best_days = sorted(scores, key=lambda x: x['overall_score'], reverse=True)[:10]
        
        if not best_days:
            return "I'm having trouble finding the best days. Please try again."
        
        # Create natural language response
        top_day = best_days[0]
        top_date = top_day['date'].strftime('%B %d, %Y')
        top_day_name = top_day['date'].strftime('%A')
        
        response = f"Based on weather and crowd predictions for 2026, the best day to visit Sigiriya this year would be {top_day_name}, {top_date}. "
        response += f"The weather should be nice with a temperature around {top_day['weather']['temperature_celsius']:.0f}°C, "
        
        if top_day['weather']['rainfall_mm'] < 5:
            response += "and it should be dry. "
        else:
            response += f"though there might be some rain ({top_day['weather']['rainfall_mm']:.1f}mm). "
        
        crowd_val = top_day['crowd']['visitors']
        if crowd_val < 2000:
            response += f"😊 You can expect light crowds with around {int(crowd_val)} visitors."
        elif crowd_val < 4000:
            response += f"👥 The crowds should be moderate with around {int(crowd_val)} visitors."
        else:
            response += f"⚠️ It might be a bit busy with around {int(crowd_val)} visitors."
        
        # Mention other good options
        if len(best_days) > 1:
            second_date = best_days[1]['date'].strftime('%B %d')
            third_date = best_days[2]['date'].strftime('%B %d') if len(best_days) > 2 else None
            
            response += f"\n\n✨ Other excellent options would be {second_date}"
            if third_date:
                response += f" or {third_date}"
            response += ". These dates also have great weather and manageable crowds."
        
        return response
    
    def _handle_best_day_next_week(self, question: str) -> str:
        """Handle: 'What is the best day next week to visit?'"""
        # Get next 7 days
        dates = [self.today + datetime.timedelta(days=i) for i in range(7)]
        
        weather_data = get_weather_dict_for_dates(dates)
        crowd_data = get_crowd_dict_for_dates(dates)
        
        # Score each day
        scores = []
        for i, date in enumerate(dates):
            w = weather_data[i]
            c = crowd_data[i]
            
            # Weather score (0-10): prefer 25°C, penalize rain and wind
            temp_score = 10 - abs(w['temperature_celsius'] - 25) * 0.4
            temp_score = max(0, min(10, temp_score))
            rain_penalty = w['rainfall_mm'] * 0.5
            wind_penalty = w['wind_speed_ms'] * 0.1
            weather_score = max(0, temp_score - rain_penalty - wind_penalty)
            
            # Crowd score (0-10): prefer moderate crowds (200-400 visitors)
            visitors = c['visitors']
            if 150 <= visitors <= 400:
                crowd_score = 10
            elif visitors < 100:
                crowd_score = 5
            elif visitors > 500:
                crowd_score = max(2, 10 - (visitors - 400) / 100)
            else:
                crowd_score = 7
            
            overall_score = (weather_score * 0.4) + (crowd_score * 0.6)
            
            scores.append({
                'date': date,
                'weather': w,
                'crowd': c,
                'weather_score': weather_score,
                'crowd_score': crowd_score,
                'overall_score': overall_score
            })
        
        # Get top 3 days
        best_days = sorted(scores, key=lambda x: x['overall_score'], reverse=True)[:3]
        
        if not best_days:
            return "I'm having trouble getting data for next week. Try asking about a specific day."
        
        # Create natural language response
        best = best_days[0]
        best_date = best['date'].strftime('%A')
        
        response = f"The best day next week to visit Sigiriya would be {best_date}. "
        response += f"It'll be around {best['weather']['temperature_celsius']:.0f}°C "
        
        if best['weather']['rainfall_mm'] < 5:
            response += "with clear, dry weather. "
        else:
            response += f"with some rain expected. "
        
        crowd_val = best['crowd']['visitors']
        if crowd_val < 2000:
            response += f"You can expect light crowds with about {int(crowd_val)} visitors."
        elif crowd_val < 4000:
            response += f"The crowds should be moderate, around {int(crowd_val)} visitors."
        else:
            response += f"It might be busier with around {int(crowd_val)} visitors."
        
        # Mention alternatives
        if len(best_days) > 1:
            alt_day = best_days[1]['date'].strftime('%A')
            response += f"\n\nIf that doesn't work, {alt_day} is also a good option."
        
        return response
    
    def _handle_best_days_in_month(self, question: str) -> str:
        """Handle: 'I'm visiting Sigiriya in April, what are the best days?' or similar."""
        # Extract month from question
        months_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        target_month = None
        target_year = 2026
        
        q_lower = question.lower()
        
        # Check for "next month"
        if 'next month' in q_lower:
            if self.today.month == 12:
                target_month = 1
                target_year = 2027
            else:
                target_month = self.today.month + 1
        # Check for "this month"
        elif 'this month' in q_lower:
            target_month = self.today.month
            target_year = self.today.year
        else:
            # Look for month name
            for month_name, month_num in months_map.items():
                if month_name in q_lower:
                    target_month = month_num
                    # If month has passed, assume next year
                    if month_num < self.today.month or (month_num == self.today.month and self.today.day > 15):
                        target_year = 2027
                    break
        
        if not target_month:
            # If no month specified and user asks about best days, use current month
            target_month = self.today.month
            target_year = self.today.year
        
        # Get all dates in target month
        if target_month == 12:
            month_end = datetime.datetime(target_year + 1, 1, 1)
        else:
            month_end = datetime.datetime(target_year, target_month + 1, 1)
        month_start = datetime.datetime(target_year, target_month, 1)
        days_in_month = (month_end - month_start).days
        dates = [month_start + datetime.timedelta(days=i) for i in range(days_in_month)]
        
        weather_data = get_weather_dict_for_dates(dates)
        crowd_data = get_crowd_dict_for_dates(dates)
        
        # Score each day
        scores = []
        for i, date in enumerate(dates):
            w = weather_data[i]
            c = crowd_data[i]
            
            # Weather score (0-10)
            temp_score = 10 - abs(w['temperature_celsius'] - 25) * 0.4
            temp_score = max(0, min(10, temp_score))
            rain_penalty = w['rainfall_mm'] * 0.5
            wind_penalty = w['wind_speed_ms'] * 0.1
            weather_score = max(0, temp_score - rain_penalty - wind_penalty)
            
            # Crowd score (0-10)
            visitors = c['visitors']
            if 150 <= visitors <= 400:
                crowd_score = 10
            elif visitors < 100:
                crowd_score = 5
            elif visitors > 500:
                crowd_score = max(2, 10 - (visitors - 400) / 100)
            else:
                crowd_score = 7
            
            overall_score = (weather_score * 0.4) + (crowd_score * 0.6)
            
            scores.append({
                'date': date,
                'weather': w,
                'crowd': c,
                'weather_score': weather_score,
                'crowd_score': crowd_score,
                'overall_score': overall_score
            })
        
        # Sort by overall score
        scores.sort(key=lambda x: x['overall_score'], reverse=True)
        
        month_name = month_start.strftime('%B %Y')
        response = f"Best Days to Visit Sigiriya in {month_name.upper()}\n\n"
        response += f"Here are your top recommendations:\n\n"
        
        # Build best days data for frontend
        best_days_data = []
        
        # Show top 5 days
        for rank, day_data in enumerate(scores[:5], 1):
            date = day_data['date']
            w = day_data['weather']
            c = day_data['crowd']
            
            date_str = date.strftime('%a, %b %d')
            day_of_week = date.strftime('%A')
            
            # Weather icon
            if 'clear' in w['weather_condition'].lower() or 'sunny' in w['weather_condition'].lower():
                weather_icon = '☀️'
            elif 'rain' in w['weather_condition'].lower():
                weather_icon = '🌧️'
            elif 'cloud' in w['weather_condition'].lower():
                weather_icon = '☁️'
            else:
                weather_icon = '🌤️'
            
            # Get crowd level
            crowd_level, crowd_emoji, _ = self._get_crowd_level(c['visitors'])
            
            response += f"{rank}. {date_str}\n"
            response += f"  🌡️ {weather_icon} {w['temperature_celsius']:.1f}°C - {w['weather_condition']}\n"
            response += f"  👥 {crowd_emoji} {crowd_level} - ~{c['visitors']} visitors\n"
            response += f"  ⭐ Overall Score: {day_data['overall_score']:.1f}/10\n\n"
            
            # Add to best_days_data for frontend
            best_days_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'day_of_week': day_of_week,
                'weather_score': float(day_data['weather_score']),
                'crowd_score': float(day_data['crowd_score']),
                'overall_score': float(day_data['overall_score']),
                'temperature': float(w['temperature_celsius']),
                'rainfall': float(w['rainfall_mm']),
                'crowd_level': crowd_level
            })
        
        response += "Tip Book early on recommended days as they attract visitors\n"
        
        # Return structured data with text and best days
        return {
            'text': response,
            'best_days': best_days_data,
            'month': month_name
        }
    
    def _handle_will_next_week_be_best(self, question: str) -> str:
        """Handle: 'Will next week be the best time to visit?'"""
        # Compare next week with overall 2026 statistics
        next_week_dates = [self.today + datetime.timedelta(days=i) for i in range(7)]
        
        crowd_data = get_crowd_dict_for_dates(next_week_dates)
        weather_data = get_weather_dict_for_dates(next_week_dates)
        
        # Calculate next week average
        avg_visitors_next_week = numpy.mean([c['visitors'] for c in crowd_data])
        avg_temp_next_week = numpy.mean([w['temperature_celsius'] for w in weather_data])
        avg_rain_next_week = numpy.mean([w['rainfall_mm'] for w in weather_data])
        
        # Get full year data for comparison
        dates_full_year = [datetime.datetime(2026, m, 15) for m in range(1, 13)]
        crowd_full_year = get_crowd_dict_for_dates(dates_full_year)
        weather_full_year = get_weather_dict_for_dates(dates_full_year)
        
        avg_visitors_year = numpy.mean([c['visitors'] for c in crowd_full_year])
        avg_temp_year = numpy.mean([w['temperature_celsius'] for w in weather_full_year])
        avg_rain_year = numpy.mean([w['rainfall_mm'] for w in weather_full_year])
        
        # Analyze
        response = "Analysis Will Next Week Be Best to Visit\n\n"
        
        response += "Next Week Statistics\n"
        response += f"  Average Visitors {int(avg_visitors_next_week)} people\n"
        response += f"  Average Temperature {avg_temp_next_week:.1f}°C\n"
        response += f"  Average Rainfall {avg_rain_next_week:.1f}mm\n\n"
        
        response += "2026 Overall Average\n"
        response += f"  Average Visitors {int(avg_visitors_year)} people\n"
        response += f"  Average Temperature {avg_temp_year:.1f}°C\n"
        response += f"  Average Rainfall {avg_rain_year:.1f}mm\n\n"
        
        # Determine if next week is good
        is_crowd_good = avg_visitors_next_week < avg_visitors_year * 0.85
        is_weather_good = avg_temp_next_week > 20 and avg_rain_next_week < avg_rain_year * 1.2
        
        response += "Verdict\n"
        
        if is_crowd_good and is_weather_good:
            response += "Excellent Timing Next week has lighter crowds and good weather\n"
            response += f"   - Crowds are {((avg_visitors_year - avg_visitors_next_week) / avg_visitors_year * 100):.0f}% lighter than average\n"
            response += f"   - Weather conditions are favorable\n"
        elif is_crowd_good:
            response += "Good for Crowds Next week will be quieter, but weather could be better\n"
            response += f"   - Crowds are {((avg_visitors_year - avg_visitors_next_week) / avg_visitors_year * 100):.0f}% lighter than average\n"
        elif is_weather_good:
            response += "Good Weather - But expect moderate to high crowds next week\n"
            response += f"   Crowds are {((avg_visitors_next_week - avg_visitors_year) / avg_visitors_year * 100):.0f}% higher than average\n"
        else:
            response += "Not the Best Time - Higher crowds and less favorable weather expected\n"
            response += "   Consider planning for a different week.\n"
        
        return response
    
    def _handle_crowd_next_week(self, question: str) -> str:
        """Handle: 'Will there be a crowd next week?' - Shows BOTH crowd and weather data"""
        next_week_dates = [self.today + datetime.timedelta(days=i) for i in range(7)]
        crowd_data = get_crowd_dict_for_dates(next_week_dates)
        weather_data = get_weather_dict_for_dates(next_week_dates)
        
        response = "Crowd and Weather Forecast Next 7 Days\n\n"
        
        weekday_visitors = []
        weekend_visitors = []
        
        for i, date in enumerate(next_week_dates):
            c = crowd_data[i]
            w = weather_data[i]
            day_name = date.strftime('%A')
            level, emoji, _ = self._get_crowd_level(c['visitors'])
            
            # Weather icon
            if 'Clear' in w['weather_condition']:
                weather_icon = "☀️"
            elif 'Rain' in w['weather_condition']:
                weather_icon = "🌧️"
            elif 'Cloudy' in w['weather_condition']:
                weather_icon = "☁️"
            else:
                weather_icon = "🌤️"
            
            response += f"{day_name} ({date.strftime('%b %d')})\n"
            response += f"  {emoji} Crowd {level} (~{c['visitors']} visitors)\n"
            response += f"  {weather_icon} Weather {w['temperature_celsius']:.0f}°C - {w['weather_condition']}\n"
            response += f"  Rain {w['rainfall_mm']:.1f}mm | Wind {w['wind_speed_ms']:.1f} m/s\n\n"
            
            if date.weekday() >= 5:  # Weekend
                weekend_visitors.append(c['visitors'])
            else:
                weekday_visitors.append(c['visitors'])
        
        # Statistics
        all_visitors = [c['visitors'] for c in crowd_data]
        all_temps = [w['temperature_celsius'] for w in weather_data]
        all_rain = [w['rainfall_mm'] for w in weather_data]
        
        avg_crowd = numpy.mean(all_visitors)
        avg_temp = numpy.mean(all_temps)
        avg_rain = numpy.mean(all_rain)
        
        max_day_idx = all_visitors.index(max(all_visitors))
        min_day_idx = all_visitors.index(min(all_visitors))
        
        response += "Summary\n"
        response += f"  Avg Crowd {int(avg_crowd)} visitors/day\n"
        response += f"  Avg Temperature {avg_temp:.1f}°C\n"
        response += f"  Avg Rainfall {avg_rain:.1f}mm\n\n"
        response += f"  Busiest {next_week_dates[max_day_idx].strftime('%A')} (~{all_visitors[max_day_idx]} visitors)\n"
        response += f"  Quietest {next_week_dates[min_day_idx].strftime('%A')} (~{all_visitors[min_day_idx]} visitors)\n"
        
        if weekday_visitors and weekend_visitors:
            response += f"\n  Weekday average {int(numpy.mean(weekday_visitors))} visitors\n"
            response += f"  Weekend average {int(numpy.mean(weekend_visitors))} visitors\n"
        
        return response
    
    def _handle_best_months_to_visit(self, question: str) -> str:
        """Handle: 'What are the best months to visit?'"""
        # Analyze each month
        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        
        month_data = []
        for month in range(1, 13):
            # Get 4 dates throughout the month
            dates = [datetime.datetime(2026, month, d) for d in [5, 10, 15, 20]]
            crowd_data = get_crowd_dict_for_dates(dates)
            weather_data = get_weather_dict_for_dates(dates)
            
            avg_crowd = numpy.mean([c['visitors'] for c in crowd_data])
            avg_temp = numpy.mean([w['temperature_celsius'] for w in weather_data])
            avg_rain = numpy.mean([w['rainfall_mm'] for w in weather_data])
            
            # Score: lower crowd + good weather
            crowd_score = 10 - (avg_crowd / 600 * 10)  # Normalize to typical max
            crowd_score = max(0, min(10, crowd_score))
            
            temp_score = 10 - abs(avg_temp - 26) * 0.3
            temp_score = max(0, min(10, temp_score))
            
            rain_score = 10 - (avg_rain / 20 * 10)
            rain_score = max(0, min(10, rain_score))
            
            overall = (crowd_score * 0.5) + (temp_score * 0.25) + (rain_score * 0.25)
            
            month_data.append({
                'month': month_names[month - 1],
                'month_num': month,
                'avg_crowd': avg_crowd,
                'avg_temp': avg_temp,
                'avg_rain': avg_rain,
                'score': overall
            })
        
        # Sort by score
        sorted_months = sorted(month_data, key=lambda x: x['score'], reverse=True)
        
        response = "Best Months to Visit Sigiriya\n\n"
        response += "Ranked by crowd levels, weather, and rainfall\n\n"
        
        for rank, month in enumerate(sorted_months[:6], 1):  # Top 6 months
            response += f"{rank}. {month['month']}\n"
            response += f"    Avg Crowd {int(month['avg_crowd'])} visitors\n"
            response += f"    Avg Temp {month['avg_temp']:.1f}°C\n"
            response += f"    Rainfall {month['avg_rain']:.1f}mm\n"
            response += f"    Score {month['score']:.1f}/10\n\n"
        
        response += "Recommendation "
        best_months = sorted_months[:3]
        best_month_names = [m['month'] for m in best_months]
        response += f"Visit during {', '.join(best_month_names)} for the best experience"
        
        return response
    
    def _handle_when_to_visit(self, question: str) -> str:
        """Handle: 'When should I visit?' - general recommendation"""
        return self._handle_best_months_to_visit(question)
    
    def _handle_day_recommendation(self, question: str) -> str:
        """Handle: 'I want to visit next week, give me a good day'"""
        return self._handle_best_day_next_week(question)
    
    def _handle_crowd_next_few_days(self, question: str) -> str:
        """Handle crowd & weather predictions for next few days."""
        dates = [self.today + datetime.timedelta(days=i) for i in range(3)]
        crowd_data = get_crowd_dict_for_dates(dates)
        weather_data = get_weather_dict_for_dates(dates)
        
        response = "📊 CROWD & WEATHER FORECAST - NEXT 3 DAYS 📊\n\n"
        
        for i, date in enumerate(dates):
            c = crowd_data[i]
            w = weather_data[i]
            level, emoji, desc = self._get_crowd_level(c['visitors'])
            day_name = date.strftime('%A, %b %d')
            
            # Weather icon
            if 'Clear' in w['weather_condition']:
                weather_icon = "☀️"
            elif 'Rain' in w['weather_condition']:
                weather_icon = "🌧️"
            elif 'Cloudy' in w['weather_condition']:
                weather_icon = "☁️"
            else:
                weather_icon = "🌤️"
            
            response += f"📅 {day_name}\n"
            response += f"  {emoji} Crowd: {level} - {c['visitors']} visitors\n"
            response += f"     💭 {desc}\n"
            response += f"  {weather_icon} Weather: {w['temperature_celsius']:.0f}°C - {w['weather_condition']}\n"
            response += f"     💧 {w['rainfall_mm']:.1f}mm rain | 💨 {w['wind_speed_ms']:.1f} m/s wind\n\n"
        
        return response
    
    def _handle_best_weekend(self, question: str) -> str:
        """Handle: 'What's the best weekend to visit?'"""
        # Get next 4 weekends
        weekends = []
        current = self.today
        while len(weekends) < 8:
            if current.weekday() >= 5:  # Saturday or Sunday
                weekends.append(current)
            current += datetime.timedelta(days=1)
        
        weather_data = get_weather_dict_for_dates(weekends)
        crowd_data = get_crowd_dict_for_dates(weekends)
        
        # Score weekends
        weekend_pairs = []
        for i in range(0, len(weekends), 2):
            if i + 1 < len(weekends):
                avg_crowd = (crowd_data[i]['visitors'] + crowd_data[i + 1]['visitors']) / 2
                avg_temp = (weather_data[i]['temperature_celsius'] + weather_data[i + 1]['temperature_celsius']) / 2
                
                crowd_score = 10 - (avg_crowd / 500 * 10)
                crowd_score = max(0, min(10, crowd_score))
                
                temp_score = 10 - abs(avg_temp - 26) * 0.3
                temp_score = max(0, min(10, temp_score))
                
                overall = (crowd_score * 0.6) + (temp_score * 0.4)
                
                weekend_pairs.append({
                    'start_date': weekends[i],
                    'end_date': weekends[i + 1],
                    'avg_crowd': avg_crowd,
                    'avg_temp': avg_temp,
                    'score': overall
                })
        
        best_weekends = sorted(weekend_pairs, key=lambda x: x['score'], reverse=True)[:2]
        
        response = "Best Weekends to Visit\n\n"
        
        for rank, wknd in enumerate(best_weekends, 1):
            response += f"{rank}. {wknd['start_date'].strftime('%b %d')} - {wknd['end_date'].strftime('%b %d')}\n"
            response += f"  Avg Crowd {int(wknd['avg_crowd'])} visitors\n"
            response += f"  Avg Temp {wknd['avg_temp']:.1f}°C\n"
            response += f"  Score {wknd['score']:.1f}/10\n\n"
        
        return response

    def _handle_month_comparison(self, question: str) -> str:
        """Handle month comparison queries like 'Is January or April better to visit?'"""
        # This is deprecated - use _compare_months instead
        return self._compare_months([], question)
    
    def _handle_specific_month_recommendation(self, question: str) -> str:
        """Handle: 'How's January?' or 'What about March 16?' or 'Tell me about March'"""
        # Extract month from question
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # Check if asking about a specific date (e.g., "March 16")
        date_pattern = r'(\d{1,2})(?:st|nd|rd|th)?'
        date_match = re.search(date_pattern, question)
        specific_day = None
        
        if date_match:
            specific_day = int(date_match.group(1))
        
        month_num = None
        for month_name, num in months.items():
            if month_name in question.lower():
                month_num = num
                break
        
        if not month_num:
            return self._handle_best_months_to_visit(question)
        
        month_name = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December'][month_num - 1]
        
        # If specific day is mentioned, show day-wise summary
        if specific_day and 1 <= specific_day <= 31:
            try:
                target_date = datetime.datetime(2026, month_num, specific_day)
                crowd_data = get_crowd_dict_for_dates([target_date])
                weather_data = get_weather_dict_for_dates([target_date])
                
                if crowd_data and weather_data:
                    c = crowd_data[0]
                    w = weather_data[0]
                    
                    # Get crowd level
                    level, emoji, description = self._get_crowd_level(c['visitors'])
                    
                    # Get weather icon
                    condition = w['weather_condition'].lower()
                    if 'clear' in condition or 'sunny' in condition:
                        weather_icon = '☀️'
                    elif 'rain' in condition:
                        weather_icon = '🌧️'
                    elif 'cloud' in condition:
                        weather_icon = '☁️'
                    else:
                        weather_icon = '🌤️'
                    
                    response = f"{month_name} {specific_day}, 2026\n\n"
                    response += f"Crowd Forecast\n"
                    response += f"  {emoji} {level} (~{c['visitors']} visitors)\n"
                    response += f"  {description}\n\n"
                    
                    response += f"Weather Details\n"
                    response += f"  {weather_icon} Condition {w['weather_condition']}\n"
                    response += f"  Temperature {w['temperature_celsius']:.1f}°C\n"
                    response += f"  Rainfall {w['rainfall_mm']:.1f}mm\n"
                    response += f"  Wind Speed {w['wind_speed_ms']:.1f} m/s\n\n"
                    
                    # Recommendation
                    response += "Recommendation\n"
                    if c['visitors'] < 300 and w['rainfall_mm'] < 5:
                        response += "Great Day - Perfect conditions for visiting\n"
                    elif c['visitors'] < 350 and w['rainfall_mm'] < 10:
                        response += "Good Day - Good conditions overall\n"
                    elif c['visitors'] > 450 or w['rainfall_mm'] > 15:
                        response += "Challenging Day - Consider another date\n"
                    else:
                        response += "👍 OKAY DAY - Manageable conditions.\n"
                    
                    return response
            except (ValueError, IndexError):
                pass
        
        # If no specific day, show month-wide summary
        dates = [datetime.datetime(2026, month_num, d) for d in [5, 10, 15, 20]]
        crowd_data = get_crowd_dict_for_dates(dates)
        weather_data = get_weather_dict_for_dates(dates)
        
        avg_crowd = numpy.mean([c['visitors'] for c in crowd_data])
        avg_temp = numpy.mean([w['temperature_celsius'] for w in weather_data])
        avg_rain = numpy.mean([w['rainfall_mm'] for w in weather_data])
        max_crowd = max([c['visitors'] for c in crowd_data])
        min_crowd = min([c['visitors'] for c in crowd_data])
        
        response = f"{month_name.upper()} Detailed Analysis\n\n"
        response += f"Crowd Forecast\n"
        response += f"  Average {int(avg_crowd)} visitors/day\n"
        response += f"  Peak ~{int(max_crowd)} visitors\n"
        response += f"  Lowest ~{int(min_crowd)} visitors\n\n"
        
        response += f"Weather Conditions\n"
        response += f"  Temperature {avg_temp:.1f}°C (average)\n"
        response += f"  Rainfall {avg_rain:.1f}mm (average)\n\n"
        
        # Recommendation
        response += "Recommendation\n"
        if avg_crowd < 300 and avg_rain < 10:
            response += f"Excellent Month - Light crowds and good weather\n"
        elif avg_crowd < 350 or avg_rain < 15:
            response += f"Good Month - Decent for visiting\n"
        else:
            response += f"Busy Month - Consider alternatives\n"
        
        return response
    
    def _handle_seasonal_recommendation(self, question: str) -> str:
        """Handle: 'What about the dry season?'"""
        return "🌍 Based on the forecast data for 2026, I recommend checking specific months for the best experience. Would you like me to tell you about a particular month?\n\n💡 Generally, drier months with moderate temperatures and lighter crowds are ideal!"
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_crowd_level(self, visitors: int) -> Tuple[str, str, str]:
        """Get crowd level category, emoji, and description."""
        if visitors > 500:
            return "Very Busy", "🔴", "High crowds - expect long waits"
        elif visitors > 400:
            return "Busy", "🟠", "Moderate-high crowds"
        elif visitors > 300:
            return "Moderate", "🟡", "Moderate crowds - manage your time"
        elif visitors > 150:
            return "Light", "🟢", "Few crowds - great for exploring"
        else:
            return "Quiet", "🟢", "Very few crowds - peaceful visit"


def process_real_time_question(question: str) -> Optional[Union[str, dict]]:
    """
    Main entry point for processing real-time questions.
    
    Args:
        question: User's question
    
    Returns:
        Response string if question matches a pattern, None otherwise
    """
    # Check location validation first
    should_reject, error_message = should_reject_query(question)
    if should_reject:
        return error_message
    
    handler = RealTimeQuestionHandler()
    return handler.process_real_time_question(question)
