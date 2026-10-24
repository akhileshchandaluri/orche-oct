import os, json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
api_key = os.environ.get("GROQ_API_KEY")
model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
client = Groq(api_key=api_key)

prompt = """You are Northstar Shop's forensic audit assistant.
A customer submitted an account deletion request:
- Email: thandiwe.m6866@zoho.com
- Requested at: 2026-09-02T12:00:00Z
- Reported status: NOT_STARTED (reported at 2026-09-05T12:00:00Z)

In the deletion worker execution window on 2026-09-05, multiple failed primary account deletion attempts occurred:
1. resource_id: account_7015, event_time: 2026-09-05T11:01:52Z, status: FAILED
2. resource_id: account_410, event_time: 2026-09-05T11:10:55Z, status: FAILED
3. resource_id: account_9155, event_time: 2026-09-05T11:12:36Z, status: FAILED

Which candidate resource_id is the most plausible primary account for this request?
STRICT RULE: You MUST choose ONLY from ['account_7015', 'account_410', 'account_9155'], or null if completely ambiguous.
Output ONLY valid JSON: {"selected_resource_id": string or null, "confidence": float, "reasoning": string}
"""

completion = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.0,
    response_format={"type": "json_object"},
    timeout=15.0,
)
print("Groq candidate ranking response:")
print(completion.choices[0].message.content)
