import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            self.model = None
            return
            
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('models/gemini-2.5-flash')


    def generate_explanation(self, question: str, model_data: str) -> str:
        """
        Generate a human-readable explanation using Gemini Pro.
        """
        if not self.model:
            return "Gemini AI is not configured. Please check your API key."

        prompt = f"""
        You are a data-driven Sigiriya Fortress expert guide.
        Analyize the provided technical data to give an insightful and short summary.
        
        Guidelines:
        1. Context: Use the technical data to explain crowds and weather.
        2. Analysis: Identify "Best" vs "Bad" days for visiting based on the scores and data.
        3. Tone: Confident, informative, and professional. NO "I'm in trouble" or "I don't know" style responses for Sigiriya.
        4. Length: Keep it short (max 4-5 sentences).
        
        Technical Data:
        {model_data}
        
        Question: "{question}"
        
        Response Format:
        ### Sigiriya Forecast Analysis
        - **Crowds & Weather:** [Summary]
        - **Best vs Bad Days:** [Identification]
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating Gemini explanation: {e}")
            return model_data

gemini_service = GeminiService()
