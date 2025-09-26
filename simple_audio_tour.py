import streamlit as st
import logging
import os
from openai import OpenAI
from typing import List, Optional
from dotenv import load_dotenv
from auth_manager import AuthManager

# Cargar variables de entorno desde .env
load_dotenv(override=True)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Obtener la API key de OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    st.error("❌ No se encontró la API key de OpenAI. Por favor, configura la variable de entorno 'OPENAI_API_KEY'.")
    st.stop()

# Configurar el cliente de OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

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
    """Guía de tour simplificada que genera y reproduce audio con gestión de tokens."""
    
    def __init__(self, api_key: str = None, user_email: str = None):
        """Inicializa la guía de tour con la API key de OpenAI y el email del usuario.
        
        Args:
            api_key: Clave de API de OpenAI
            user_email: Email del usuario para seguimiento de tokens (opcional)
        """
        if not api_key:
            raise ValueError("Se requiere una API key de OpenAI")
            
        # Usar el cliente global de OpenAI
        self.client = openai_client
        self.user_email = user_email
        self.supabase = SupabaseManager() if user_email else None
        
    def _check_token_limit(self, estimated_tokens: int = 0) -> dict:
        """Verifica si el usuario puede realizar la operación."""
        if not self.user_email or not self.supabase:
            return {"can_proceed": True}  # Sin límite si no hay usuario o supabase
            
        return self.supabase.check_token_usage(self.user_email, estimated_tokens)
        
    def generate_tour_text(self, location: str, interests: List[str], duration: int, mode: str = "normal", info_input: str = "") -> str:
        """Genera el texto del tour usando GPT-4 con control de tokens.
        
        Args:
            location: Ubicación del tour
            interests: Lista de intereses del usuario
            duration: Duración del tour en horas
            mode: Modo de generación (normal, experto, etc.)
            info_input: Información adicional para personalizar el tour
            
        Returns:
            str: Texto generado del tour
            
        Raises:
            ValueError: Si se excede el límite de tokens
        """
        estimated_tokens = len(location) + len(str(interests)) + 100  # Estimación simple
        token_check = self._check_token_limit(estimated_tokens)
        
        if not token_check.get("can_proceed", True):
            raise ValueError(token_check.get("reason", "Límite de tokens excedido"))
            
        prompt = get_prompt_by_mode(mode, location, interests, duration, info_input)
        
        system_message = {
            "normal": "Eres un guía turístico experto y amigable.",
            "savage": "Eres un guía turístico que muestra el lado oscuro y crudo de los lugares, sin filtros.",
            "ultra_savage": "Eres un guía turístico extremadamente polémico que no tiene límites en su narrativa."
        }.get(mode, "Eres un guía turístico experto y amigable.")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7 if mode == "normal" else 0.9,
                max_tokens=2000
            )
            
            # Actualizar el contador de tokens después de la generación
            if self.user_email and self.supabase:
                # Usar el conteo real de tokens de la respuesta si está disponible
                used_tokens = response.usage.total_tokens if hasattr(response, 'usage') else len(response.choices[0].message.content)
                self.supabase.update_token_usage(self.user_email, used_tokens)
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error al generar el tour: {str(e)}")
            if self.user_email and self.supabase:
                # Actualizar el contador de tokens en caso de error
                self.supabase.update_token_usage(self.user_email, estimated_tokens)
            raise
            
    def generate_and_play_audio(self, text: str, voice: str = "alloy") -> None:
        """
        Genera audio a partir de texto usando OpenAI TTS y lo reproduce en la interfaz.
        
        Args:
            text: Texto a convertir a voz
            voice: Voz a utilizar (alloy, echo, fable, onyx, nova, o shimmer)
        """
        if not text.strip():
            st.warning("No hay texto para convertir a audio.")
            return
            
        with st.spinner("Generando audio..."):
            try:
                # Generar el audio usando la API de OpenAI TTS
                response = self.client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text
                )
                
                # Guardar el audio en un archivo temporal
                audio_file = "temp_audio.mp3"
                response.stream_to_file(audio_file)
                
                # Reproducir el audio en la interfaz
                st.audio(audio_file, format='audio/mp3')
                
                # Opción para descargar el audio
                with open(audio_file, "rb") as f:
                    audio_bytes = f.read()
                st.download_button(
                    label="Descargar audio",
                    data=audio_bytes,
                    file_name=f"tour_audio_{voice}.mp3",
                    mime="audio/mp3"
                )
                
                # Limpiar el archivo temporal
                try:
                    os.remove(audio_file)
                except Exception as e:
                    logger.warning(f"No se pudo eliminar el archivo temporal: {e}")
                
            except Exception as e:
                st.error(f"Error al generar el audio: {str(e)}")
                logger.error(f"Error en generate_and_play_audio: {str(e)}")
                raise

def check_authentication() -> bool:
    """Verifica si el usuario está autenticado."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated

def show_token_management(auth_manager):
    """Muestra el panel de gestión de tokens."""
    st.title("💰 Gestión de Tokens")
    
    # Mostrar uso actual
    st.subheader("Uso de Tokens por Usuario")
    try:
        token_usages = auth_manager.supabase.get_all_token_usage()
        
        if token_usages:
            for usage in token_usages:
                with st.expander(f"📧 {usage['user_email']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Tokens Usados", f"{usage['tokens_used']:,}")
                        st.metric("Límite de Tokens", f"{usage['tokens_limit']:,}")
                        progress = min(100, (usage['tokens_used'] / usage['tokens_limit']) * 100) if usage['tokens_limit'] > 0 else 0
                        st.progress(int(progress))
                    
                    with col2:
                        new_limit = st.number_input(
                            "Nuevo límite",
                            min_value=1000,
                            value=usage['tokens_limit'],
                            key=f"limit_{usage['user_email']}",
                            step=1000
                        )
                        
                        col_update, col_reset = st.columns(2)
                        with col_update:
                            if st.button("💾 Actualizar", key=f"update_{usage['user_email']}", use_container_width=True):
                                if auth_manager.supabase.update_token_limit(usage['user_email'], new_limit):
                                    st.success("✅ Límite actualizado")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al actualizar el límite")
                        
                        with col_reset:
                            if st.button("🔄 Reiniciar", key=f"reset_{usage['user_email']}", use_container_width=True):
                                if auth_manager.supabase.reset_token_usage(usage['user_email']):
                                    st.success("✅ Contador reiniciado")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al reiniciar el contador")
        else:
            st.info("No hay datos de uso de tokens disponibles.")
            
    except Exception as e:
        st.error(f"Error al cargar los datos de uso: {str(e)}")
        logger.error(f"Error en show_token_management: {str(e)}")

def main():
    """Función principal de la aplicación."""
    # Inicializar el gestor de autenticación
    auth_manager = AuthManager()
    
    # Verificar autenticación
    if not check_authentication():
        email = auth_manager.show_login_form()
        if not st.session_state.get('authenticated'):
            return  # No continuar si el usuario no está autenticado
    
    # Mostrar la aplicación principal si el usuario está autenticado
    st.title("🎧 Simple AI Audio Tour")
    
    # Verificar si el usuario es administrador
    is_admin = auth_manager.supabase.is_admin(st.session_state.user_email) if hasattr(st.session_state, 'user_email') else False
    
    # Mostrar menú de administración si es admin
    if is_admin:
        admin_tab1, admin_tab2 = st.sidebar.tabs(["👥 Usuarios", "💰 Tokens"])
        
        with admin_tab1:
            if st.button("⚙️ Panel de Administración"):
                st.session_state.show_admin = not st.session_state.get('show_admin', False)
        
        with admin_tab2:
            if st.button("💰 Gestión de Tokens"):
                st.session_state.show_token_management = not st.session_state.get('show_token_management', False)
    
    # Mostrar el panel de administración correspondiente
    if st.session_state.get('show_admin', False):
        auth_manager.show_admin_panel()
        return
        
    if st.session_state.get('show_token_management', False):
        show_token_management(auth_manager)
        return
    
    # Mostrar el saludo al usuario
    user_email = getattr(st.session_state, 'user_email', 'Invitado')
    st.write(f"Bienvenido, {user_email}!")
    
    # Mostrar información de uso de tokens
    if hasattr(st.session_state, 'user_email'):
        try:
            token_info = auth_manager.supabase.check_token_usage(st.session_state.user_email)
            if token_info.get('can_proceed', True):
                progress = min(100, (token_info['tokens_used'] / token_info['tokens_limit']) * 100) if token_info['tokens_limit'] > 0 else 0
                st.sidebar.metric("Tokens Usados", f"{token_info['tokens_used']:,}/{token_info['tokens_limit']:,}")
                st.sidebar.progress(int(progress))
            else:
                st.sidebar.warning(token_info.get('reason', 'Límite de tokens alcanzado'))
        except Exception as e:
            logger.error(f"Error al cargar información de tokens: {e}")
            st.sidebar.error("Error al cargar información de tokens")
    
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
    
    # Mostrar el texto generado si existe
    if st.session_state.get('tour_text'):
        st.markdown("### 📝 Contenido del Tour")
        st.markdown(st.session_state.tour_text)
        
        # Sección de generación de audio
        st.markdown("---")
        st.markdown("### 🎧 Generar Audio")
        
        # Selector de voz
        voice = st.selectbox(
            "🗣️ Selecciona una voz",
            ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            format_func=lambda x: x.capitalize(),
            help="Selecciona la voz que prefieras para la narración"
        )
        
        # Botón para generar audio
        if st.button("🔊 Generar Audio", use_container_width=True):
            # Generar y reproducir el audio
            st.session_state.guide.generate_and_play_audio(st.session_state.tour_text, voice=voice)
    
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
                
                # Mostrar el texto generado
                st.markdown("### 📝 Contenido del Tour")
                st.markdown(tour_text)
                
                # Sección de generación de audio
                st.markdown("---")
                st.markdown("### 🎧 Generar Audio")
                
                # Selector de voz
                voice = st.selectbox(
                    "🗣️ Selecciona una voz",
                    ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                    format_func=lambda x: x.capitalize(),
                    help="Selecciona la voz que prefieras para la narración"
                )
                
                # Botón para generar audio
                if st.button("🔊 Generar Audio", use_container_width=True):
                    # Generar y reproducir el audio
                    st.session_state.guide.generate_and_play_audio(tour_text, voice=voice)
                
                st.session_state.is_generating = False
                st.success("✅ Audio generado")
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error al generar el tour: {str(e)}")
            st.session_state.is_generating = False
            st.rerun()

if __name__ == "__main__":
    main()
