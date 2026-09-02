import os
import re
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from google.genai import types

# ===================================================
# 🔐 SECURE ENVIRONMENT INITIALIZATION
# ===================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 8000))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "users_db.json")
DATA_FILE = os.path.join(BASE_DIR, "merged_output.json")

app = FastAPI(title="Syllaphly Core AI Engine")

# ===================================================
# 🛠️ CORE SCHEMAS & UTILITIES
# ===================================================
class LoginRequest(BaseModel):
    key: str

class ChatRequest(BaseModel):
    question: str
    subject: str = "pc"

def load_json_data(file_path: str, fallback_type: type):
    if not os.path.exists(file_path):
        return fallback_type()
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return fallback_type()

def clean_arabic_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[\u064B-\u0652]", "", text) # Strips out short vowels/diacritics
    return text.replace("’", " ").replace("'", " ").replace("-", " ").strip()

def local_search(question: str, subject: str, lessons: list) -> str:
    query = clean_arabic_text(question.lower().replace("/resume", "").strip())
    if not query:
        return ""
        
    best_score = 0
    matched_content = ""
    
    for lesson in lessons:
        if str(lesson.get("subject", "")).lower().strip() != subject.lower().strip():
            continue
            
        content = lesson.get("content", "")
        normalized_content = clean_arabic_text(content)
        
        score = 0
        if query in normalized_content: 
            score += 100
            
        words = [w for w in query.split() if len(w) > 1]
        for word in words:
            if word in normalized_content: 
                score += 15
                
        if score > best_score:
            best_score = score
            matched_content = content
            
    return matched_content

# ===================================================
# 🛣️ API ROUTING ENDPOINTS
# ===================================================

@app.post("/api/login")
async def api_login(payload: LoginRequest):
    input_key = payload.key.strip()
    
    if input_key == "3AC-MATH-88":
        return {"status": "success", "role": "admin"}
        
    users = load_json_data(DB_FILE, dict)
    if input_key in users:
        if users[input_key].get("status") == "blocked":
            return {"status": "error", "message": "❌ Code élève suspendu."}
        return {"status": "success", "role": "user"}
        
    return {"status": "error", "message": "❌ Code invalide !"}

@app.post("/api/chat")
async def api_chat(payload: ChatRequest):
    q = payload.question.strip()
    subj = payload.subject.strip()
    
    # Process developer commands shortcut 
    if q.startswith("/") and not q.lower().startswith("/resume"):
        if q == "/critique":
            return {"response": "⚙️ Core Engine Status: Online."}
        return {"response": "⚠️ Command unrecognized."}
        
    lessons_db = load_json_data(DATA_FILE, list)
    extracted_context = local_search(q, subj, lessons_db)
    is_summary_mode = q.lower().startswith("/resume")
    
    if not extracted_context:
        alert = "Ce cours ou cette notion scientifique n'est pas disponible. Vérifie l'onglet sélectionné."
        if re.search(r"[\u0600-\u06FF]", q): # Regex rule checks if user typed in Arabic scripts
            alert = "❌ هذا المفهوم العلمي غير موجود في هذا القسم. يرجى اختيار المادة الصحيحة."
        return {"response": alert}

    # Setup the unified prompt structure for Moroccan 3AC curriculum compliance
    system_instruction = (
        f"Tu es l'IA Syllaphly, un tuteur d'élite expert du programme officiel du Brevet Marocain 3AC pour la matière : {subj.upper()}.\n"
        "Si l'élève écrit en Arabe ou en Darija, tu DOIS rédiger strictement en Arabe الفصحى. Sinon, réponds en Français.\n"
    )
    
    if is_summary_mode:
        clean_query = q.replace("/resume", "").strip()
        user_prompt = (
            f"CONTENU DE LA LEÇON TROUVÉE DANS LE JSON: '{extracted_context}'\n"
            f"MODE RESUME DE COURS ACTIVÉ: L'élève te demande un résumé complet du cours concernant: {clean_query}. "
            "Génère une fiche de synthèse complète, aérée, propre et fidèle à 100% au programme officiel 3AC. "
            "Utilise des titres clairs et des puces détaillant les règles fondamentales et des exemples."
        )
    else:
        user_prompt = (
            f"Utilise cet extrait de cours comme base si pertinent: '{extracted_context}'\n"
            f"MODE DISCUSSION STANDARD: Réponds de façon très concise en 2 lignes maximum avec un exemple court à la requête de l'élève: {q}"
        )

    try:
        # Calls the unified latest production Google GenAI Client wrapper 
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=system_instruction)
        )
        return {"response": response.text.strip()}
    except Exception as e:
        return {"response": f"⚠️ Liaison Cloud interrompue. Extrait local trouvé:\n\n{extracted_context}"}

# ===================================================
# 🎨 STATIC FILES FRONTEND DELIVERY PIPELINE
# ===================================================
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# Automatically maps folder assets inside /static if you break files out later
if os.path.isdir(os.path.join(BASE_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=True)
