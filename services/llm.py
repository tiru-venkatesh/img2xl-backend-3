import os
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage

# GitHub Models endpoint
ENDPOINT = "https://models.github.ai/inference"
MODEL = "gpt-4.1-mini"   # works for chat

TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN not found in environment")

client = ChatCompletionsClient(
    endpoint=ENDPOINT,
    credential=AzureKeyCredential(TOKEN),
)

def call_llm(prompt: str):
    response = client.complete(
        model=MODEL,
        messages=[
            SystemMessage("You are a helpful assistant."),
            UserMessage(prompt)
        ],
        temperature=0.2,
        max_tokens=800
    )

    return response.choices[0].message.content
