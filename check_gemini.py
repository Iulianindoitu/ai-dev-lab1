from dotenv import load_dotenv
from google import genai

load_dotenv()                  # citește .env
client = genai.Client()        # preia automat GEMINI_API_KEY
r = client.models.generate_content(
       model="gemini-2.5-flash",
       contents="Ce este un algoritm? Răspunde în 2 propoziții.",
   )
print(r.text)