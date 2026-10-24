import os, json, time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

client = Groq(api_key=api_key)

print("Testing JSON output with response_format...")
try:
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a deletion intent analyzer. Output ONLY valid JSON: {\"is_deletion\": boolean, \"confidence\": float, \"intent_category\": string, \"reasons\": string}"
            },
            {
                "role": "user",
                "content": "<user_request_text>Please permanently delete my customer profile and all order records.</user_request_text>"
            }
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
        timeout=15.0,
    )
    resp_text = completion.choices[0].message.content
    print("Response text:", resp_text)
    print("Usage:", completion.usage)
    parsed = json.loads(resp_text)
    print("Parsed JSON successfully:", parsed)
except Exception as e:
    print("Error with response_format:", type(e).__name__, str(e))
