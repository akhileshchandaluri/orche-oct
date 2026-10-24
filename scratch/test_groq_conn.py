import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)
try:
    models = client.models.list()
    model_ids = [m.id for m in models.data]
    print(f"Groq API reachable: True, total models: {len(model_ids)}")
    print("Available models sample:", model_ids[:10])
    req_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    print(f"Is requested model '{req_model}' available? {req_model in model_ids}")
except Exception as e:
    print("Groq API call error:", type(e).__name__, str(e))
