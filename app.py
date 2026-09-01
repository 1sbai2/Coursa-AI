import http.server, socketserver, json, os, re
import google.genai as genai

# ===================================================
# 🔐 CONFIGURATION CLOUD GOOGLE GEMINI (PRODUCTION)
# ===================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

PORT = 5500
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "users_db.json")
DATA_FILE = os.path.join(BASE_DIR, "merged_output.json")

def load_data(file_path, fallback):
    if not os.path.exists(file_path): return fallback
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            d = json.load(f)
            return d if isinstance(d, list) or file_path == DB_FILE else [d]
        except: return fallback

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"[\u064B-\u0652]", "", text)
    text = text.replace("’", " ").replace("'", " ").replace("-", " ")
    return text.strip()

def local_search_engine(question, subject_filter, lessons):
    clean_q = question.lower().replace("/resume", "").strip()
    norm_q = normalize_text(clean_q)
    if not norm_q: return ""
        
    highest, match = -1, ""
    for item in lessons:
        item_subject = str(item.get("subject", "")).lower().strip()
        if item_subject != subject_filter.lower().strip(): continue
            
        content = item.get("content", "")
        norm_content = normalize_text(content)
        
        score = 0
        if norm_q in norm_content: score += 100
            
        query_words = [w for w in norm_q.split() if len(w) > 1]
        for word in query_words:
            if word in norm_content: score += 15
                
        if score > highest and score > 0: highest, match = score, content
            
    return match

# --- HIGH-END MULTI-ASSET STATIC FILE ROUTER SERVER ---
class SyllaphlyServer(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args): return
    
    def do_GET(self):
        # Determine the file location mapping path natively
        url_path = self.path.split("?")[0]
        if url_path == "/":
            file_to_serve = os.path.join(BASE_DIR, "index.html")
            content_type = "text/html; charset=utf-8"
        elif url_path == "/style.css":
            file_to_serve = os.path.join(BASE_DIR, "style.css")
            content_type = "text/css; charset=utf-8"
        elif url_path == "/script.js":
            file_to_serve = os.path.join(BASE_DIR, "script.js")
            content_type = "application/javascript; charset=utf-8"
        else:
            self.send_error(404, "File Not Found")
            return

        if os.path.exists(file_to_serve):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            with open(file_to_serve, "r", encoding="utf-8") as f:
                self.wfile.write(f.read().encode('utf-8'))
        else:
            self.send_error(404, "Asset Missing In Directory")

    def do_POST(self):
        raw_body = self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')
        payload = json.loads(raw_body)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        
        if self.path == "/api/login":
            key = payload.get("key", "").strip()
            users = load_data(DB_FILE, {})
            
            if key == "3AC-MATH-88": res = {"status": "success", "role": "admin"}
            elif key in users:
                if users[key].get("status") == "blocked":
                    res = {"status": "error", "message": "❌ Code élève suspendu."}
                else: res = {"status": "success", "role": "user"}
            else: res = {"status": "error", "message": "❌ Code invalide !"}
                
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
            return
            
        elif self.path == "/api/chat":
            q, subj = payload.get("question", ""), payload.get("subject", "pc")
            
            if q.startswith("/") and not q.strip().lower().startswith("/resume"):
                command_reply = "⚠️ Command unrecognized."
                if q == "/critique": command_reply = "⚙️ Core Engine Status: Online."
                self.wfile.write(json.dumps({"response": command_reply}, ensure_ascii=False).encode('utf-8'))
                return
                
            extrait = local_search_engine(q, subj, load_data(DATA_FILE, []))
            is_summary_mode = q.strip().lower().startswith("/resume")
            
            if not extrait:
                alert_lang = "Ce cours ou cette notion scientifique n'est pas disponible. Vérifie l'onglet sélectionné."
                if bool(re.search(r"[\u0600-\u06FF]", q)):
                    alert_lang = "❌ هذا المفهوم العلمي غير موجود في هذا القسم. يرجى اختيار المادة الصحيحة."
                self.wfile.write(json.dumps({"response": alert_lang}, ensure_ascii=False).encode('utf-8'))
                return
            
            p1 = "Tu es lA Syllaphly, un tuteur d elite expert du programme officiel du Brevet Marocain 3AC pour la matiere : " + str(subj.upper()) + "."
            p2 = "Si l'élève écrit en Arabe ou en Darija, tu DOIS rédiger strictement en Arabe الفصحى. Sinon, réponds en Français."
            
            if is_summary_mode:
                p3 = "CONTENU COMPLET DE LA LEÇON TROUVÉE DANS NOTRE FICHIER JSON : '" + str(extrait) + "'."
                p4 = "MODE RESUME DE COURS ACTIVÉ : L'élève te demande un résumé complet du cours spécifié dans sa requête. Si l'extrait fourni ci-dessus est vide ou incomplet, NE REFUSE PAS de répondre ! Utilise tes propres connaissances encyclopédiques parfaites de l'IA pour générer une fiche de synthèse complète, aérée et ultra-propre fidèle à 100% au programme officiel du Brevet Marocain (3AC). Utilise des titres clairs et des puces détaillant la règle et des exemples."
            else:
                p3 = "Utilise cet extrait de cours '" + str(extrait) + "' comme base si pertinent."
                p4 = "MODE DISCUSSION STANDARD : L'élève pose une question sur un detail précis. Si l'extrait est vide, utilise tes propres connaissances d'expert 3AC. Réponds de façon très concise en 2 lignes maximum avec un exemple court."
                
            prompt = p1 + "\n" + p2 + "\n" + p3 + "\n" + p4 + "\n" + "Requete de l eleve : " + str(q.replace("/resume", "").strip())
            
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
                ai_res = response.text.strip()
            except Exception as e: 
                print("\n[🚨 GEMINI API EXCEPTION]:", e)
                ai_res = "⚠️ Liaison Cloud interrompue. Extrait local trouve :\n\n" + str(extrait)
                
            self.wfile.write(json.dumps({"response": ai_res}, ensure_ascii=False).encode('utf-8'))

if __name__ == "__main__":
    print("🚀 Syllaphly Multi-Asset Server active on http://127.0.0.1:5500")
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", 5500), SyllaphlyServer) as server: 
        server.serve_forever()
