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

# --- 3. DESIGN SYSTEM (CSS COMPLET & MODERNE) ---
# --- 3. DESIGN SYSTEM (CSS PREMIUM) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Fraunces:ital,opsz,wght@0,9..144,700;1,9..144,700&display=swap');

    :root {
        --primary-color: #FF4B4B;
        --bg-color: #FFFFFF;
        --text-main: #1A1C1E; /* Noir profond */
        --text-secondary: #4A4A4A;
        --card-border: #E9ECEF;
    }

    /* Fond de l'application */
    .stApp {
        background-color: var(--bg-color) !important;
    }

    /* --- FIX VISIBILITÉ CHARGEMENT (SPINNER) --- */
    /* On force le texte du spinner et l'icône à être visibles */
    div[data-testid="stStatusWidget"] div {
        color: var(--text-main) !important;
    }
    
    .stSpinner > div > div {
        color: var(--text-main) !important;
    }

    /* --- FIX TITRES ET TEXTE --- */
    /* On cible spécifiquement les titres pour éviter le blanc sur blanc */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Fraunces', serif !important;
        color: var(--text-main) !important;
        font-weight: 700 !important;
    }

    .stMarkdown p, .stCaption {
        font-family: 'Inter', sans-serif !important;
        color: var(--text-secondary) !important;
    }

    /* --- DESIGN DES INPUTS --- */
    div[data-baseweb="input"] {
        border-radius: 12px !important;
        border: 1px solid var(--card-border) !important;
        background-color: #F8F9FA !important;
    }
    
    input {
        color: var(--text-main) !important;
    }

    /* --- BOUTON --- */
    .stButton button {
        background-color: var(--text-main) !important;
        color: white !important;
        border-radius: 12px !important;
        width: 100%;
        height: 50px;
        border: none !important;
        font-weight: 600 !important;
    }
    
    .stButton button:hover {
        background-color: var(--primary-color) !important;
        color: white !important;
    }

    /* --- CARTES INGRÉDIENTS --- */
    .ingredient-row {
        background-color: #F8F9FA;
        padding: 12px 16px;
        border-radius: 10px;
        margin-bottom: 8px;
        border-left: 4px solid var(--primary-color);
        color: var(--text-main) !important;
        display: flex;
        justify-content: flex-start;
    }

    /* --- INFOS (TEMPS / PORTIONS) --- */
    .stInfo {
        background-color: #FFF5F5 !important;
        color: var(--text-main) !important;
        border: none !important;
        border-radius: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

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
                    unit = ing.get('unite', '')
                    item = ing.get('item', '')
                    
                    if isinstance(q, (int, float)):
                        v = q * ratio
                        display_val = int(v) if v.is_integer() else round(v, 1)
                        # On utilise une div avec la classe 'ingredient-row' définie dans le CSS
                        st.markdown(f"""
                            <div class="ingredient-row">
                                <span style="color:#FF4B4B; font-weight:bold; margin-right:10px;">{display_val} {unit}</span> 
                                <span style="color:#1A1C1E;">{item}</span>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div class="ingredient-row">
                                <span style="color:#1A1C1E;">{unit} {item}</span>
                            </div>
                        """, unsafe_allow_html=True)


