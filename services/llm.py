from google import genai

# API key is automatically read from GEMINI_API_KEY
client = genai.Client()

def call_llm(prompt: str):
    response = client.models.generate_content(
        model="gemini-3-flash",
        contents=prompt
    )
    return response.text
