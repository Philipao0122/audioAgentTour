import streamlit as st
import logging
import os
from openai import OpenAI
from typing import List

# Obtener la API key de OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    st.error("❌ No se encontró la API key de OpenAI. Configúrala en las variables de entorno de Vercel.")
    st.stop()

logger = logging.getLogger(__name__)

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
    3. Historias oscuras o polémicas que generen incomodidad y reflexión.
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
        
    def generate_tour_text(self, location: str, interests: List[str], duration: int, mode: str = "normal", info_input: str = "") -> str:
        """Genera el texto del tour usando GPT-4."""
        # Obtener el prompt según el modo seleccionado
        prompt = get_prompt_by_mode(mode, location, interests, duration, info_input)
        
        try:
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
            return tour_text
            
        except Exception as e:
            raise
    
    def text_to_speech(self, text: str) -> bytes:
        """Convierte el texto a voz usando la API de OpenAI. Retorna los bytes del audio."""
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text,
                response_format="mp3",
                speed=1.0
            )
            
            return response.content
            
        except Exception as e:
            raise

def main():
    """Función principal de la aplicación."""
    st.title("🎧 Simple AI Audio Tour")
    st.write("Crea un tour de audio personalizado en segundos")
    
    # Inicializar variables de sesión para el tour
    if 'tour_text' not in st.session_state:
        st.session_state.tour_text = ""
    if 'audio_data' not in st.session_state:
        st.session_state.audio_data = None
    if 'is_generating' not in st.session_state:
        st.session_state.is_generating = False
        
    # Configuración por defecto
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
    except Exception as e:
        st.error(f"❌ Error al inicializar el cliente de OpenAI: {str(e)}")
        st.stop()
    
    # Sidebar para la configuración
    with st.sidebar:
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
            value=default_duration,
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
        
        if st.session_state.audio_data:
            st.audio(st.session_state.audio_data)
            
            st.download_button(
                label="💾 Descargar Audio",
                data=st.session_state.audio_data,
                file_name="tour_audio.mp3",
                mime="audio/mp3",
                use_container_width=True
            )
    
    # Lógica de generación del tour
    if st.session_state.get('is_generating', False):
        try:
            with st.spinner("🚀 Generando tu tour personalizado..."):
                # Generar el texto del tour
                tour_text = st.session_state.guide.generate_tour_text(
                    location=location,
                    interests=interests,
                    duration=duration,
                    mode=mode,
                    info_input=info_input
                )
                st.session_state.tour_text = tour_text
                st.success("✅ Tour generado")
                
                # Convertir a voz
                with st.spinner("🔊 Convirtiendo a voz..."):
                    audio_data = st.session_state.guide.text_to_speech(tour_text)
                    st.session_state.audio_data = audio_data
                    st.success("✅ Audio generado")
            
            # Finalizar el estado de generación
            st.session_state.is_generating = False
            st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error al generar el tour: {str(e)}")
            st.session_state.is_generating = False
            st.rerun()

if __name__ == "__main__":
    main()
