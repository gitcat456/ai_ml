import os
import requests
from dotenv import load_dotenv

from retriever import retrieve

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file!")

url = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

messages = []

MAX_HISTORY = 20

while True:

    question = input("You: ")

    # Exit immediately
    if question.lower() in ["quit", "exit", "bye"]:
        print("Goodbye!")
        break

    # -------------------------
    # Retrieve relevant context
    # -------------------------

    context = retrieve(question)

    context_text = "\n\n".join(
        context["documents"][0]
    )

    # -------------------------
    # Build temporary API prompt
    # -------------------------

    api_messages = [

        {
            "role": "system",
            "content":
            """
You are a helpful AI assistant.

Use the provided context to answer factual questions.

If the answer is not contained in the context,
say you don't know based on the available documents.

For greetings, thanks, and casual conversation,
respond naturally.
"""
        }

    ]

    # Previous conversation
    api_messages.extend(messages)

    # Today's retrieved context
    api_messages.append(
        {
            "role": "system",
            "content": f"""
Context:

{context_text}
"""
        }
    )

    # Current user question
    api_messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": api_messages
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=data
        )

        response.raise_for_status()

    except requests.exceptions.RequestException:

        print(f"Status Code: {response.status_code}")
        print(response.text)
        continue

    result = response.json()

    ai_content = result["choices"][0]["message"]["content"]

    print("Assistant:", ai_content)

    # -------------------------
    # Save conversation history
    # -------------------------

    messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    messages.append(
        {
            "role": "assistant",
            "content": ai_content
        }
    )

    # Keep only the latest conversation
    messages = messages[-MAX_HISTORY:]