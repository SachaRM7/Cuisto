import streamlit as st
import yt_dlp
import google.generativeai as genai
import json
import os
import time
import instaloader
import re

# --- 1. CONFIGURATION PAGE ---
st.set_page_config(page_title="Chef AI", layout="centered")

# --- 2. GESTION DES SECRETS & API ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except Exception as e:
    st.error("⚠️ Clé GEMINI_API_KEY manquante dans .streamlit/secrets.toml")
    st.stop()

# Modèle : Gemini 2.0 Flash est le plus rapide pour ce projet
model = genai.GenerativeModel('gemini-2.5-flash')

# --- 3. DESIGN SYSTEM (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;600&display=swap');
    .stApp { background-color: #F9F9F5; }
    h1, h2, h3 { font-family: 'Playfair Display', serif !important; color: #2C3E50; }
    div[data-testid="stSegmentedControl"] button {
        border-radius: 20px !important; border: 1px solid #E0E0E0 !important; font-family: 'Inter', sans-serif;
    }
    div[data-testid="stSegmentedControl"] button[data-selected="true"] {
        background-color: #2C3E50 !important; color: white !important;
    }
    .stInfo { background-color: white; border-radius: 15px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

st.title("🍳 Le Clone 'Clipper' Cuisine")
st.caption("Analyse multimodale : Audio + Texte via Gemini Flash")

# --- 4. FONCTION D'EXTRACTION ---
def get_instagram_text(url):
    L = instaloader.Instaloader()
    shortcode_match = re.search(r'(p|reel)/([^/?#&]+)', url)
    if not shortcode_match: return "ID Instagram introuvable"
    shortcode = shortcode_match.group(2)
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        full_text = f"LÉGENDE: {post.caption}\n\nCOMS:\n"
        for i, comment in enumerate(post.get_comments()):
            full_text += f"- {comment.text}\n"
            if i >= 3: break
        return full_text
    except: return "Erreur lecture texte Instagram"

def get_video_data(url):
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'format': 'bestaudio/best',
        'outtmpl': 'temp_audio.%(ext)s',
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}],
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    with st.spinner("🕵️‍♂️ Récupération des données..."):
        text_content = ""
        if "instagram.com" in url:
            text_content = get_instagram_text(url)
        try:
            if os.path.exists("temp_audio.mp3"): os.remove("temp_audio.mp3")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if "instagram.com" not in url:
                    text_content = info.get('description', '')
                return text_content, "temp_audio.mp3"
        except:
            return text_content, None

# --- 5. FONCTION IA ---
def process_recipe_gemini(description, audio_path=None):
    # On prépare ce qu'on envoie à Gemini
    content_to_send = [
        """Tu es un assistant culinaire expert. Fusionne les infos (Audio + Texte) en JSON strict :
        {"emoji": "🎨", "titre": "Nom", "portions_defaut": 2, "temps_prep": "20 min", 
         "ingredients": [{"item": "nom", "quantite": 100, "unite": "g"}], 
         "etapes": ["Etape 1"]}""",
        f"TEXTE RÉCUPÉRÉ: {description}"
    ]
    
    # On ajoute l'audio SEULEMENT s'il existe
    if audio_path and os.path.exists(audio_path):
        with st.spinner("📤 Analyse de l'audio..."):
            audio_file = genai.upload_file(path=audio_path, mime_type="audio/mp3")
            while audio_file.state.name == "PROCESSING":
                time.sleep(1)
                audio_file = genai.get_file(audio_file.name)
            content_to_send.append(audio_file)

    with st.spinner("🧠 Gemini cuisine la donnée..."):
        response = model.generate_content(content_to_send, generation_config={"response_mime_type": "application/json"})
        # Nettoyage
        if audio_path:
            try: genai.delete_file(audio_file.name); os.remove(audio_path)
            except: pass
        return json.loads(response.text)

# --- 6. INTERFACE ---
url = st.text_input("Colle le lien (TikTok, Insta, YT) :")

if st.button("Extraire la recette"):
    if url:
        desc, audio = get_video_data(url)
        if desc or audio:
            recipe = process_recipe_gemini(desc, audio)
            if recipe:
                st.divider()
                st.header(f"{recipe.get('emoji','🍳')} {recipe.get('titre')}")
                
                col1, col2 = st.columns(2)
                with col1: st.info(f"⏱️ {recipe.get('temps_prep')}")
                with col2:
                    base = recipe.get('portions_defaut', 2)
                    portions = st.segmented_control("Portions", [1, 2, 4, 6, 8], default=base) or base
                
                ratio = portions / base
                st.subheader("Ingrédients")
                for ing in recipe.get('ingredients', []):
                    q = ing.get('quantite')
                    if q:
                        v = q * ratio
                        st.write(f"- **{int(v) if v.is_integer() else round(v,1)} {ing.get('unite','')}** {ing.get('item')}")
                    else: st.write(f"- {ing.get('item')}")
                
                st.subheader("Instructions")
                for i, step in enumerate(recipe.get('etapes', []), 1):

                    st.write(f"**{i}.** {step}")
