import os 
import requests
from dotenv import load_dotenv
from chunker import load_chunks
from retriever import retrieve, build_index

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env file! Please add it.")

url = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"}

messages = []

while True:
    
    question = input("You: ")

    context = retrieve(question)

    # context_text = "\n\n".join([item[1]['text'] for item in context])
    context_text = context_text = "\n\n".join(
                        context["documents"][0]
                    )

    #Prompt Augmentation
    prompt = f"""
    You are a helpful assistant.

    Answer ONLY using the context below.

    Context:
    {context_text}

    Question:
    {question}
    """
    
    if question.lower() in ["quit", "exit", "bye"]:
        print("Goodbye!")
        break
    
    messages.append({
        "role": "user",
        "content": prompt
    })
    
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages
    }
    
    try:
        response = response = requests.post(
            url,
            headers=headers,
            json=data
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Status Code: {response.status_code}")
        print(response.text)
        continue
    
    result = response.json()
    ai_content = result["choices"][0]["message"]["content"]
    print("Assitant:", ai_content)
   
    messages.append({
        "role": "assistant",
        "content": ai_content
    })