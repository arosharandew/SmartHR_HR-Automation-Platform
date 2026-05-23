import os
import time
from functools import wraps
from dotenv import load_dotenv
from groq import Groq
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def retry(max_attempts=3, delay=1.0, backoff=2, timeout=30):
    """Decorator for retry and timeout logic."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            # Simple timeout using signal (works on Unix, for Windows we'll use a simpler approach)
            # For cross-platform, we'll use a loop with time checks
            attempt = 0
            last_exception = None
            current_delay = delay
            while attempt < max_attempts:
                start = time.time()
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    elapsed = time.time() - start
                    last_exception = e
                    attempt += 1
                    if attempt >= max_attempts:
                        break
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exception or Exception("Max retries exceeded")
        return wrapper
    return decorator

class LLMConfig:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"
    TEMPERATURE = 0.2
    MAX_TOKENS = 1024
    TOP_P = 0.95

    @classmethod
    def get_groq_client(cls) -> Groq:
        if not cls.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in .env")
        return Groq(api_key=cls.GROQ_API_KEY)

    @classmethod
    @retry(max_attempts=3, delay=1.0, timeout=30)
    def get_llm_response(cls, system_prompt: str, user_prompt: str) -> str:
        client = cls.get_groq_client()
        response = client.chat.completions.create(
            model=cls.MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=cls.TEMPERATURE,
            max_tokens=cls.MAX_TOKENS,
            top_p=cls.TOP_P,
        )
        return response.choices[0].message.content