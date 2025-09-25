import streamlit as st
import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from openai import OpenAI
from typing import Dict, List, Optional
from pydantic import BaseModel
import time
from dotenv import load_dotenv
from auth_manager import AuthManager
from supabase_manager import SupabaseManager

# Cargar variables de entorno
load_dotenv()

# Obtener la API key de OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    st.error("❌ No se encontró la API key de OpenAI. Por favor, crea un archivo .env con tu API key.")
    st.stop()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("audio_tour_debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AudioTour")

# Configuración de la página
st.set_page_config(
    page_title="Simple AI Audio Tour",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_prompt_by_mode(mode: str, location: str, interests: List[str], duration: int, info_input: str = "") -> str:
    """Devuelve el prompt adecuado según el modo seleccionado."""
    base_prompt = f"""
    Eres un guía turístico experto creando un tour de audio para {location}.
    
    Duración objetivo: {duration} minutos
    Intereses del visitante: {', '.join(interests) if interests else 'No especificados'}
    {f"\nInformación adicional sobre el visitante: {info_input}" if info_input else ''}
    """
    
    if mode == "savage":
        return f"""{base_prompt}

    Genera un guion de audio con:
    1. Una introducción cruda, grotesca y con un toque morboso.
    2. Puntos de interés narrados con descripciones intensas, sin suavizar lo desagradable.
    3. Historias oscuras,  o polémicas que generen incomodidad y reflexión.
    4. Una conclusión fuerte, con impacto duradero.

    El tono debe ser cercano pero crudo, directo, sin miedo a incomodar.
    """
    elif mode == "ultra_savage":
        return f"""{base_prompt}

    Genera un guion de audio extremo que:
    1. Abra con una introducción morbosa, grotesca y provocadora.
    2. Describa puntos de interés con crudeza absoluta, sin filtros ni suavizar nada.
    3. Incluya historias polémicas, crueles o tabú, diseñadas para provocar reacción.
    4. Termine con una conclusión inquietante, polémica o perturbadora.

    ⚠️ Después de cada bloque narrativo, añade un breve comentario indicando por qué este fragmento podría resultar delicado, incómodo o controvertido para algunos oyentes.

    El tono debe ser desafiante, polémico y transgresor, empujando los límites.
    """
    else:  # Modo normal por defecto
        return f"""{base_prompt}

    Genera un guion de audio con:
    1. Una introducción cálida y acogedora.
    2. Puntos de interés narrados de forma clara y atractiva.
    3. Historias interesantes, con un tono positivo y ameno.
    4. Una conclusión inspiradora y cercana.

    El tono debe ser amigable, conversacional y accesible para cualquier visitante.
    """

class SimpleTourGuide:
    """Guía de tour simplificada que genera y reproduce audio."""
    
    def __init__(self, api_key: str = None):
        if not api_key:
            raise ValueError("Se requiere una API key de OpenAI")
            
        self.client = OpenAI(api_key=api_key)
        self.audio_dir = Path("audio_outputs")
        self.audio_dir.mkdir(exist_ok=True)
        logger.info("Cliente de OpenAI inicializado correctamente")
        
    def generate_tour_text(self, location: str, interests: List[str], duration: int, mode: str = "normal", info_input: str = "") -> (str, int):
        """Genera el texto del tour usando GPT-4 y retorna (texto, tokens_usados)."""
        logger.info(f"Generando tour para {location} con intereses: {interests} en modo: {mode}")
        
        # Obtener el prompt según el modo seleccionado
        prompt = get_prompt_by_mode(mode, location, interests, duration, info_input)
        
        try:
            logger.info("Enviando solicitud a la API de OpenAI...")
            system_message = {
                "normal": "Eres un guía turístico experto y amigable.",
                "savage": "Eres un guía turístico que muestra el lado oscuro y crudo de los lugares, sin filtros.",
                "ultra_savage": "Eres un guía turístico extremadamente polémico que no tiene límites en su narrativa."
            }.get(mode, "Eres un guía turístico experto y amigable.")
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7 if mode == "normal" else 0.9,
                max_tokens=2000
            )
            
            tour_text = response.choices[0].message.content
            tokens_used = 0
            try:
                if hasattr(response, "usage") and response.usage and hasattr(response.usage, "total_tokens"):
                    tokens_used = int(response.usage.total_tokens)
            except Exception:
                tokens_used = 0
            logger.info("Tour generado exitosamente")
            logger.debug(f"Contenido generado: {tour_text[:200]}...")  # Mostrar solo el inicio
            
            return tour_text, tokens_used
            
        except Exception as e:
            logger.error(f"Error al generar el tour: {str(e)}")
            raise
    
    def text_to_speech(self, text: str, filename: str = "tour_audio.mp3") -> (Path, int):
        """Convierte el texto a voz usando la API de OpenAI. Retorna (ruta, chars_usados)."""
        logger.info("Iniciando conversión de texto a voz...")
        output_path = self.audio_dir / filename
        
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text,
                response_format="mp3",
                speed=1.0
            )
            
            # Guardar el archivo de audio
            response.stream_to_file(output_path)
            logger.info(f"Audio guardado en: {output_path}")
            
            return output_path, len(text)
            
        except Exception as e:
            logger.error(f"Error en la generación de voz: {str(e)}")
            raise
def main():
    """Función principal de la aplicación."""

    # --- Inicialización del Estado de Sesión ---
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None

    auth = AuthManager()

    # --- Flujo de Autenticación ---
    if not st.session_state.authenticated:
        auth.show_login_form()
        return

    # --- Aplicación Principal (si está autenticado) ---
    st.title("🎧 Simple AI Audio Tour")
    st.write("Crea un tour de audio personalizado en segundos")
    
    # Inicializar variables de sesión para el tour
    if 'tour_text' not in st.session_state:
        st.session_state.tour_text = ""
    if 'audio_file' not in st.session_state:
        st.session_state.audio_file = None
    if 'is_generating' not in st.session_state:
        st.session_state.is_generating = False
        
    # Configuración por defecto desde variables de entorno
    default_location = os.getenv('TOUR_DEFAULT_LOCATION', 'Barcelona, España')
    default_interests = os.getenv('TOUR_DEFAULT_INTERESTS', 'Arquitectura,Historia').split(',')
    default_duration = int(os.getenv('TOUR_DEFAULT_DURATION', '5'))
    # Lista completa de intereses disponibles
    available_interests = [
        "Arquitectura", 
        "Historia", 
        "Gastronomía", 
        "Arte", 
        "Naturaleza", 
        "Compras",
        "Night Life"
    ]
    
    # Inicializar el guía con la API key
    try:
        if 'guide' not in st.session_state:
            st.session_state.guide = SimpleTourGuide(api_key=OPENAI_API_KEY)
            st.sidebar.success("✅ Aplicación lista")
    except Exception as e:
        st.sidebar.error(f"❌ Error al inicializar el cliente de OpenAI: {str(e)}")
        st.stop()
    
    # Sidebar para la configuración
    with st.sidebar:
        st.header(f"👤 {st.session_state.get('user_email', 'Usuario')}")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            auth.logout()
        
        st.divider()

        # Panel de Administración (si es admin)
        if auth.supabase.is_admin(st.session_state.user_email):
            with st.expander("👑 Panel de Administración"):
                auth.show_admin_panel()
            st.divider()

        # Estado de uso y límites
        is_admin_user = auth.supabase.is_admin(st.session_state.user_email)
        usage = auth.supabase.get_usage_status(st.session_state.user_email)
        if usage:
            st.subheader("📊 Consumo del Mes")
            st.caption(f"Mes actual: {usage['month']}")
            if is_admin_user:
                st.success("👑 Admin: sin límite de consumo")
                st.write(f"Tokens usados: {usage['tokens_used']} / ∞")
                st.write(f"TTS usados: {usage['tts_chars_used']} / ∞")
            else:
                st.progress(min(1.0, usage['tokens_used'] / max(1, usage['token_limit'])), text=f"Tokens: {usage['tokens_used']} / {usage['token_limit']}")
                st.progress(min(1.0, usage['tts_chars_used'] / max(1, usage['tts_char_limit'])), text=f"TTS: {usage['tts_chars_used']} / {usage['tts_char_limit']}")
                st.caption(f"Restantes • Tokens: {usage['tokens_remaining']} • TTS: {usage['tts_chars_remaining']}")
            st.divider()
        else:
            st.info("No se pudo obtener el estado de uso actual.")

        st.header("⚙️ Configuración del Tour")
        
        # Inputs del usuario
        location = st.text_input("📍 Ubicación del tour", default_location)
        
        interests = st.multiselect(
            "🎯 Intereses (opcional)",
            available_interests,
            [i for i in default_interests if i in available_interests]  # Filtra solo los intereses válidos
        )
        
        # Selector de modo
        mode = st.selectbox(
            "🎭 Modo de narración",
            ["normal", "savage", "ultra_savage"],
            format_func=lambda x: {
                "normal": "🟢 Normal (Amigable)",
                "savage": "🔥 Savage (Grotesco)",
                "ultra_savage": "🔴 Ultra Savage (Sin filtros)"
            }[x],
            help="Selecciona el estilo de narración para el tour"
        )
        
        # Ajustar el rango para permitir tiempos más cortos (2-60 minutos)
        duration = st.slider(
            "⏱️ Duración del tour (minutos)",
            min_value=2,  # Mínimo 2 minutos
            max_value=60,  # Máximo 60 minutos
            value=default_duration,  # Valor por defecto desde .env o 5
            step=1,        # Incrementos de 1 minuto
            help="Selecciona la duración deseada para el tour (2-60 minutos)"
        )
        
        # Campo adicional para información del visitante
        info_input = st.text_area(
            "ℹ️ Información adicional sobre el visitante (opcional)",
            placeholder="Ej: Es la primera vez que visita la ciudad, tiene movilidad reducida, etc.",
            help="Información adicional que puede ayudar a personalizar el tour"
        )
        
        # Botón para generar el tour
        if not st.session_state.is_generating:
            if st.button("🎤 Generar Tour de Audio", use_container_width=True):
                st.session_state.is_generating = True
                st.rerun()
    
    # Área principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Contenido del Tour")
        
        # Mostrar el texto generado o placeholder
        tour_text = st.text_area(
            "Contenido generado",
            value=st.session_state.tour_text,
            height=400,
            placeholder="El contenido del tour aparecerá aquí..."
        )
    
    with col2:
        st.subheader("🎧 Reproducción")
        
        if st.session_state.audio_file and st.session_state.audio_file.exists():
            st.audio(str(st.session_state.audio_file))
            
            # Botón de descarga
            with open(st.session_state.audio_file, "rb") as f:
                audio_bytes = f.read()
                
            st.download_button(
                label="💾 Descargar Audio",
                data=audio_bytes,
                file_name=st.session_state.audio_file.name,
                mime="audio/mp3",
                use_container_width=True
            )
    
    # Lógica de generación del tour con control de cuotas
    if st.session_state.get('is_generating', False):
        try:
            with st.spinner("🚀 Generando tu tour personalizado..."):
                supa = auth.supabase
                user_email = st.session_state.user_email
                is_admin_user = supa.is_admin(user_email)

                # 1) Pre-check para ChatCompletion usando max_tokens como tope (omitido para admin)
                max_llm_tokens = 2000
                if not is_admin_user:
                    ok, status = supa.can_consume(user_email, tokens_needed=max_llm_tokens, tts_chars_needed=0)
                    if not ok:
                        st.error("❌ Has alcanzado tu límite mensual de tokens para generación de texto.")
                        if status:
                            st.info(f"Tokens usados: {status['tokens_used']} / {status['token_limit']}")
                        st.session_state.is_generating = False
                        st.rerun()

                # 2) Generar el texto del tour
                tour_text, tokens_used = st.session_state.guide.generate_tour_text(
                    location=location,
                    interests=interests,
                    duration=duration,
                    mode=mode,
                    info_input=info_input
                )
                st.session_state.tour_text = tour_text

                # 3) Registrar uso real de tokens
                if tokens_used and tokens_used > 0:
                    supa.add_usage(user_email, tokens_used=tokens_used, tts_chars_used=0)

                # 4) Pre-check para TTS por cantidad de caracteres (omitido para admin)
                needed_chars = len(tour_text)
                if not is_admin_user:
                    ok, status = supa.can_consume(user_email, tokens_needed=0, tts_chars_needed=needed_chars)
                    if not ok:
                        st.warning("⚠️ No tienes suficientes caracteres TTS restantes este mes para sintetizar el audio.")
                        if status:
                            st.info(f"TTS usados: {status['tts_chars_used']} / {status['tts_char_limit']}")
                        st.session_state.is_generating = False
                        st.rerun()

                # 5) Generar el audio
                audio_filename = f"tour_{int(time.time())}.mp3"
                audio_path, chars_used = st.session_state.guide.text_to_speech(
                    st.session_state.tour_text,
                    filename=audio_filename
                )
                st.session_state.audio_file = audio_path

                # 6) Registrar uso de TTS
                if chars_used and chars_used > 0:
                    supa.add_usage(user_email, tokens_used=0, tts_chars_used=chars_used)

                # 7) Reiniciar el estado de generación
                st.session_state.is_generating = False
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error al generar el tour: {str(e)}")
            logger.exception("Error en la generación del tour")
            st.session_state.is_generating = False
            st.rerun()

if __name__ == "__main__":
    main()