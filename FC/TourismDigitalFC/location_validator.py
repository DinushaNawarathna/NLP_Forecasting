"""
Location Validator

Checks if a query is explicitly asking about a location OTHER than Sigiriya.
Only rejects specific location names, not generic terms.
Allows all Sigiriya-related queries to pass through.
"""

import re
from typing import Tuple, Optional

# Specific city/town names (not generic terms)
SPECIFIC_LOCATIONS = [
    # Major Sri Lankan cities and regions (specific names only)
    'galle', 'colombo', 'kandy', 'nuwara eliya', 
    'anuradhapura', 'polonnaruwa', 'mirissa', 'arugambe', 'arugam bay',
    'ella', 'hikkaduwa', 'matara', 'unawatuna', 'dambulla', 'jaffna',
    'trincomalee', 'batticaloa', 'badulla', 'ratnapura', 'puttalam',
    'negombo', 'horton plains', 'pigeon island', 'adam\'s peak',
    # Suburbs and towns near Colombo
    'malabe', 'sri jayawardenepura', 'kotte', 'dehiwala', 'mount lavinia',
    'moratuwa', 'ratmalana', 'kelaniya', 'kaduwela', 'godagama',
    'kolonnawa', 'padukka', 'avissawella', 'boralesgamuwa', 'angulana',
    # International locations
    'paris', 'london', 'new york', 'tokyo', 'dubai', 'singapore',
    'bangkok', 'bali', 'phuket', 'koh samui', 'hanoi', 'ho chi minh',
    'yangon', 'mandalay', 'phnom penh', 'laos', 'vietnam', 'thailand',
    'malaysia', 'indonesia', 'india', 'nepal', 'bhutan'
]

ERROR_MESSAGE = "I'm unable to process this request. I can only help with Sigiriya weather and crowd information 🏔️"

def is_asking_about_other_location(query: str) -> Tuple[bool, Optional[str]]:
    """
    Check if query is explicitly asking about a location OTHER than Sigiriya.
    
    Only rejects specific location names, not generic terms.
    Allows queries that mention Sigiriya even with generic descriptors.
    
    Args:
        query: User's natural language question
        
    Returns:
        Tuple[is_other_location, detected_location_name]
        - is_other_location: True if explicitly asking about other specific location
        - detected_location_name: The location name detected (or None)
    """
    query_lower = query.lower().strip()
    
    # ALLOW: Any query mentioning Sigiriya (even with generic terms)
    if 'sigiriya' in query_lower or 'sigiri' in query_lower:
        return False, None
    
    # REJECT: Only if asking specifically about OTHER named locations
    # Check for specific city/town names with location prepositions
    location_patterns = [
        r'(?:in|at|near|at the|around|within)\s+({locations})',
        r'(?:weather|crowd|visitors?|busy|crowded)\s+(?:in|at|near)\s+({locations})',
        r'(?:fort|city|town)\s+(?:in|of)\s+({locations})',
    ]
    
    # Build regex with all specific locations
    locations_pattern = '|'.join(re.escape(loc) for loc in SPECIFIC_LOCATIONS)
    
    for pattern_template in location_patterns:
        pattern = pattern_template.format(locations=locations_pattern)
        match = re.search(pattern, query_lower)
        if match:
            # Found a match - extract the location name
            matched_text = match.group(0).lower()
            for location in SPECIFIC_LOCATIONS:
                if location in matched_text:
                    return True, location
    
    # Also check for direct mentions of specific locations with context
    for location in SPECIFIC_LOCATIONS:
        # Must be a whole word match for specific locations
        word_boundary_pattern = r'\b' + re.escape(location) + r'\b'
        if re.search(word_boundary_pattern, query_lower):
            # Check if it's in a context that indicates asking about that location
            # (not just mentioning it incidentally)
            before_match = query_lower[:query_lower.find(location)]
            
            # If preceded by weather/crowd keywords, it's asking about that location
            if any(keyword in before_match for keyword in ['weather', 'crowd', 'crowd in', 'weather in', 'visitor', 'busy', 'crowded']):
                return True, location
    
    return False, None


def validate_sigiriya_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if query is about Sigiriya or related content.
    Only rejects queries about other specific locations.
    
    Args:
        query: User's question
        
    Returns:
        Tuple[is_valid_sigiriya_query, error_message_if_invalid]
        - is_valid: True if it's about Sigiriya or doesn't mention other locations
        - error_message: Error message if it's about other location, None if valid
    """
    is_other, location = is_asking_about_other_location(query)
    
    if is_other:
        return False, ERROR_MESSAGE
    
    return True, None


def should_reject_query(query: str) -> Tuple[bool, str]:
    """
    Check if query should be rejected (asking about non-Sigiriya location).
    
    Args:
        query: User's question
        
    Returns:
        Tuple[should_reject, error_message]
    """
    is_valid, error = validate_sigiriya_query(query)
    return not is_valid, error or ERROR_MESSAGE
