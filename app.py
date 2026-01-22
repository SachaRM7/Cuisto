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
# --- 3. DESIGN SYSTEM (CSS COMPLET & MODERNE) ---
st.markdown("""
    <style>
    /* Importation des polices */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&family=Playfair+Display:wght@700;900&display=swap');

    /* Configuration globale du fond et du texte */
    .stApp {
        background-color: #FFFFFF !important;
        color: #1A1A1A !important;
    }

    /* Forcer la couleur du texte pour TOUS les éléments */
    .stMarkdown, p, span, label, li, h1, h2, h3, div {
        color: #1A1A1A !important;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Titres élégants en Serif */
    h1, h2, h3 {
        font-family: 'Playfair Display', serif !important;
        font-weight: 900 !important;
        letter-spacing: -0.5px;
    }

    /* Barre d'input (URL) */
    .stTextInput input {
        border-radius: 12px !important;
        border: 2px solid #E0E0E0 !important;
        padding: 12px !important;
        background-color: #F8F9FA !important;
        color: #1A1A1A !important;
    }

    /* Bouton "Extraire" style Premium */
    .stButton button {
        width: 100%;
        background-color: #1A1A1A !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 15px !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        border: none !important;
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        background-color: #333333 !important;
    }

    /* Sélecteur de Portions (Segmented Control) */
    div[data-testid="stSegmentedControl"] {
        gap: 10px !important;
    }
    div[data-testid="stSegmentedControl"] button {
        background-color: #F0F2F6 !important;
        border: none !important;
        border-radius: 10px !important;
        color: #1A1A1A !important;
        font-weight: 600 !important;
    }
    div[data-testid="stSegmentedControl"] button[data-selected="true"] {
        background-color: #FF4B4B !important; /* Rouge corail pour la sélection */
        color: white !important;
    }

    /* Cartes d'info (Temps / Portions) */
    .stInfo {
        background-color: #F8F9FA !important;
        border: 1px solid #EEEEEE !important;
        border-radius: 16px !important;
        padding: 20px !important;
    }

    /* Liste d'ingrédients stylisée */
    .ing-card {
        background: white;
        border-left: 4px solid #FF4B4B;
        padding: 10px 15px;
        margin-bottom: 8px;
        border-radius: 4px 12px 12px 4px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.03);
    }
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
                    unit = ing.get('unite', '')
                    item = ing.get('item', '')
                    
                    # Correction ici : on vérifie que q est bien un nombre avant de multiplier
                    if isinstance(q, (int, float)):
                        v = q * ratio
                        display_val = int(v) if v.is_integer() else round(v, 1)
                        st.write(f"- **{display_val} {unit}** {item}")
                    else:
                        # Si pas de quantité, on affiche juste l'unité et l'item (ex: "Sel")
                        st.write(f"- {unit} {item}")
