import os 
import requests

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

url = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

data = {
    "model": "llama-3.3-70b-versatile",
    "messages": [
        {
            "role": "user",
            "content": "what was the last thing i asked ?"
        }
    ]
}

response = requests.post(
    url,
    headers=headers,
    json=data
)

if response.status_code == 200:
    result = response.json()
    print(result["choices"][0]["message"]["content"])
else:
    print(response.status_code)
    print(response.text)

# ai = result['choices']
# ai_res = ai[0]
# ai_response = ai_res['message']['content']
