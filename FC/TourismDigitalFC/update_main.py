#!/usr/bin/env python3
import sys

# Read main.py
with open('main.py', 'r') as f:
    lines = f.readlines()

# Find the chat endpoint and modify it
modified = False
i = 0
while i < len(lines):
    # Look for the start of the chat function
    if '@app.post("/chat"' in lines[i] and 'response_model=ChatResponse' in lines[i]:
        # Find the async def chat line
        j = i
        while j < len(lines) and 'async def chat' not in lines[j]:
            j += 1
        
        if j < len(lines):
            # Find the docstring end and the function body start
            k = j + 1
            in_docstring = False
            while k < len(lines):
                if '"""' in lines[k]:
                    if not in_docstring:
                        in_docstring = True
                    else:
                        # Found closing docstring, next line is where we insert
                        k += 1
                        break
                k += 1
            
            # Now find where the function ends (next @app or end of file)
            end = k
            indent_level = None
            while end < len(lines):
                line = lines[end]
                if line.strip() and not line.startswith(' ' * 4):
                    if line.strip().startswith('@app'):
                        break
                end += 1
            
            # Extract function body (lines from k to end)
            func_body_start = k
            
            # Find the last non-empty line of this function
            func_end = end
            for idx in range(end - 1, k - 1, -1):
                if lines[idx].strip():
                    func_end = idx + 1
                    break
            
            # Replace the function body
            new_body = '''    message = request.message
    q = message.lower()
    
    # Check if this is a weather query
    weather_keywords = ['weather', 'temperature', 'temp', 'rain', 'rainfall', 'wind', 'forecast', 'climate', 'hot', 'cold', 'warm', 'windy', 'celsius', 'degrees']
    time_keywords = ['2026', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec', 'week', 'month']
    is_weather_query = any(keyword in q for keyword in weather_keywords) and any(time_word in q for time_word in time_keywords)
    
    # Handle weather query
    if is_weather_query:
        try:
            response = get_weather_response(message)
        except Exception as e:
            response = "Expected weather forecast: Unable to process weather query at this time."
    else:
        # Handle visitor forecast query
        if fc_df is None:
            raise HTTPException(status_code=503, detail="Forecast model not initialized")
        response = chat_visitor_forecast(message, fc_df)
    
    return ChatResponse(
        user_message=request.message,
        assistant_response=response
    )
'''
            
            lines = lines[:func_body_start] + [new_body + '\n'] + lines[func_end:]
            modified = True
            break
    i += 1

if modified:
    with open('main.py', 'w') as f:
        f.writelines(lines)
    print("Successfully updated main.py")
else:
    print("Could not find chat endpoint")
    sys.exit(1)
