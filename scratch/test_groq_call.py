import os, json, time, traceback
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

client = Groq(api_key=api_key)

try:
    print("Testing models.list() first...")
    m = client.models.list()
    print("models.list() OK! Total models:", len(m.data))
    
    print(f"Testing chat.completions.create with model '{model}'...")
    t0 = time.time()
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Reply with one word: hello"}
        ],
        timeout=20.0,
    )
    print("Completed in:", time.time() - t0)
    print("Content:", completion.choices[0].message.content)
except Exception as e:
    print("Exception type:", type(e))
    traceback.print_exc()
