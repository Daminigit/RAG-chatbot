"""
scripts/verify_groq.py — Phase 0: Groq API Connectivity Check

Sends a minimal "hello world" completion to verify the GROQ_API_KEY
is valid and the API is reachable.

Usage:
    source .venv/bin/activate
    python scripts/verify_groq.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GROQ_API_KEY", "")
if not api_key or api_key == "your_groq_api_key_here":
    print("❌  GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")
    print("    Get your key at: https://console.groq.com")
    sys.exit(1)

try:
    from groq import Groq
except ImportError:
    print("❌  groq package not installed. Run: pip install groq")
    sys.exit(1)

print(f"🔑  Using API key: {api_key[:8]}{'*' * (len(api_key) - 8)}")
print("📡  Sending test completion to Groq API...")

try:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", "llama3-8b-8192"),
        messages=[{"role": "user", "content": "Reply with exactly: GROQ_OK"}],
        max_tokens=10,
        temperature=0.0,
    )
    reply = response.choices[0].message.content.strip()
    model_used = response.model
    print(f"✅  Groq API connected successfully!")
    print(f"    Model   : {model_used}")
    print(f"    Response: {reply}")
except Exception as e:
    print(f"❌  Groq API call failed: {e}")
    sys.exit(1)
