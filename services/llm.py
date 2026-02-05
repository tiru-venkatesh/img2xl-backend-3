import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def call_llm(prompt: str):
    response = client.models.generate_content(
        model="gemini-1.5-flash-latest",
        contents=prompt
    )
    return response.text
