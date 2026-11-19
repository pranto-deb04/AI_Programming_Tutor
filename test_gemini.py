
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=20000)
)

print("Testing Gemini model:", model, flush=True)
print("Sending request...", flush=True)

start = time.time()

try:
    response = client.models.generate_content(
        model=model,
        contents="Reply with only the word OK."
    )

    print("SUCCESS!", flush=True)
    print("Response:", response.text, flush=True)

except Exception as e:
    print("FAILED!", flush=True)
    print("Error:", str(e), flush=True)

finally:
    print("Time:", round(time.time() - start, 2), "seconds", flush=True)
