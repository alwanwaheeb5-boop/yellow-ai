from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def ask_ai(message: str, context: str = ""):
    prompt = f"""أنت Yellow AI مساعد ذكي باللغة العربية.

السياق السابق:
{context}

المستخدم: {message}"""

    response = client.chat.completions.create(
model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def build_context(history: list) -> str:
    if not history:
        return "لا يوجد سياق سابق"
    text = "\n".join([f"{r}: {m}" for r, m in history[-10:]])
    return text[:800] + "..." if len(text) > 800 else text
