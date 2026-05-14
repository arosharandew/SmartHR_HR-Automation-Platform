import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found")

client = Groq(api_key=GROQ_API_KEY)
DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

def get_completion(prompt, system_prompt=None, model=DEFAULT_MODEL, temperature=0.7, max_tokens=800):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_tokens,
        stream=False,
    )
    return completion.choices[0].message.content, None