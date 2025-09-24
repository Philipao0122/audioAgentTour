import streamlit as st
import asyncio
import json
import logging
import sys
from pathlib import Path
from openai import OpenAI
from typing import Dict, List, Optional
from pydantic import BaseModel
import time

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

class SimpleTourGuide:
    """Guía de tour simplificada que genera y reproduce audio."""
    
    def __init__(self, api_key: str = None):
        if not api_key:
            raise ValueError("Se requiere una API key de OpenAI")
            
        self.client = OpenAI(api_key=api_key)
        self.audio_dir = Path("audio_outputs")
        self.audio_dir.mkdir(exist_ok=True)
        logger.info("Cliente de OpenAI inicializado correctamente")
        
    def generate_tour_text(self, location: str, interests: List[str], duration: int) -> str:
        """Genera el texto del tour usando GPT-4."""
        logger.info(f"Generando tour para {location} con intereses: {interests}")
        
        # Crear el prompt para el modelo
        prompt = f"""
        Eres un guía turístico experto creando un tour de audio para {location}.
        
        Duración objetivo: {duration} minutos
        Intereses del visitante: {', '.join(interests) if interests else 'No especificados'}
        
        Por favor, genera un guión de audio que incluya:
        1. Una introducción cálida
        2. Puntos de interés relevantes
        3. Historias y datos interesantes
        4. Una conclusión amigable
        
        El tono debe ser conversacional y amigable, como si estuvieras guiando personalmente al visitante.
        """
        
        try:
            logger.info("Enviando solicitud a la API de OpenAI...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un guía turístico experto y amigable."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            tour_text = response.choices[0].message.content
            logger.info("Tour generado exitosamente")
            logger.debug(f"Contenido generado: {tour_text[:200]}...")  # Mostrar solo el inicio
            
            return tour_text
            
        except Exception as e:
            logger.error(f"Error al generar el tour: {str(e)}")
            raise
    
    def text_to_speech(self, text: str, filename: str = "tour_audio.mp3") -> Path:
        """Convierte el texto a voz usando la API de OpenAI."""
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
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error en la generación de voz: {str(e)}")
            raise

def main():
    """Función principal de la aplicación."""
    st.title("🎧 Simple AI Audio Tour")
    st.write("Crea un tour de audio personalizado en segundos")
    
    # Inicializar variables de sesión
    if 'tour_text' not in st.session_state:
        st.session_state.tour_text = ""
    if 'audio_file' not in st.session_state:
        st.session_state.audio_file = None
    if 'is_generating' not in st.session_state:
        st.session_state.is_generating = False
    
    # Configuración de la API Key
    st.sidebar.header("🔑 Configuración de OpenAI")
    api_key = st.sidebar.text_input(
        "Ingresa tu API Key de OpenAI",
        type="password",
        help="Puedes obtener una API key en https://platform.openai.com/api-keys"
    )
    
    # Verificar si la API key está configurada
    if not api_key:
        st.warning("⚠️ Por favor ingresa tu API Key de OpenAI para continuar")
        st.stop()
    
    # Inicializar el guía con la API key
    try:
        if 'guide' not in st.session_state or st.session_state.get('current_api_key') != api_key:
            st.session_state.guide = SimpleTourGuide(api_key=api_key)
            st.session_state.current_api_key = api_key
            st.sidebar.success("✅ API Key configurada correctamente")
    except Exception as e:
        st.sidebar.error(f"❌ Error al inicializar el cliente de OpenAI: {str(e)}")
        st.stop()
    
    # Sidebar para la configuración
    with st.sidebar:
        st.header("⚙️ Configuración del Tour")
        
        # Inputs del usuario
        location = st.text_input("📍 Ubicación del tour", "Barcelona, España")
        
        interests = st.multiselect(
            "🎯 Intereses (opcional)",
            ["Arquitectura", "Historia", "Gastronomía", "Arte", "Naturaleza", "Compras"],
            ["Arquitectura", "Historia"]
        )
        
        # Ajustar el rango para permitir tiempos más cortos (2-60 minutos)
        duration = st.slider(
            "⏱️ Duración del tour (minutos)",
            min_value=2,  # Mínimo 2 minutos
            max_value=60,  # Máximo 60 minutos
            value=5,       # Valor por defecto: 5 minutos
            step=1,        # Incrementos de 1 minuto
            help="Selecciona la duración deseada para el tour (2-60 minutos)"
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
    
    # Lógica de generación del tour
    if st.session_state.get('is_generating', False):
        try:
            with st.spinner("🚀 Generando tu tour personalizado..."):
                # Paso 1: Generar el texto del tour
                start_time = time.time()
                tour_text = st.session_state.guide.generate_tour_text(location, interests, duration)
                st.session_state.tour_text = tour_text
                st.success(f"✅ Tour generado en {time.time() - start_time:.1f} segundos")
                
                # Paso 2: Convertir a voz
                with st.spinner("🔊 Convirtiendo a voz..."):
                    start_time = time.time()
                    audio_file = st.session_state.guide.text_to_speech(
                        tour_text,
                        f"tour_{location.lower().replace(' ', '_')}_{int(time.time())}.mp3"
                    )
                    st.session_state.audio_file = audio_file
                    st.success(f"✅ Audio generado en {time.time() - start_time:.1f} segundos")
            
            # Finalizar el estado de generación
            st.session_state.is_generating = False
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error al generar el tour: {str(e)}")
            logger.exception("Error en la generación del tour")
            st.session_state.is_generating = False
            st.rerun()

if __name__ == "__main__":
    main()
