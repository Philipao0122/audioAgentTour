import streamlit as st
import base64
import json
import time
import hashlib
import os
import logging
import sys
import numpy as np
import torch
import scipy.io
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv
from huggingface_hub import InferenceClient, InferenceTimeoutError
from transformers import pipeline
import soundfile as sf

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('audio_tour_debug.log')
    ]
)
logger = logging.getLogger(__name__)

# Add a filter to log all uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

class AudioTourGenerator:
    """Handles the generation of audio tours using Hugging Face's API.
    
    This class manages text generation and text-to-speech conversion using
    Hugging Face's Inference API, with proper error handling and retry logic.
    """
    
    def __init__(self):
        """Initialize the AudioTourGenerator with API keys and configuration."""
        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("HF_API_TOKEN")
        
        if not self.api_key:
            raise ValueError(
                "HF_API_TOKEN not found in environment variables. "
                "Please set it in your .env file or environment variables."
            )
        
        # Initialize clients with timeout and retry settings
        self.text_client = InferenceClient(
            token=self.api_key,
            timeout=30.0  # 30 seconds timeout
        )
        
        # Available models for text generation (using free models)
        self.available_models = [
            "gpt2",
            "distilgpt2",
            "facebook/opt-350m"
        ]
        self.current_model = self.available_models[0]  # Start with gpt2
        
        # TTS configuration - Using a simpler TTS model that works with free API
        self.tts_model = "coqui/xtts-v2"  # Spanish TTS model
        self.tts_api_url = f"https://api-inference.huggingface.co/models/{self.tts_model}"
            
        # Set up directories
        self.base_dir = Path.cwd() / "audio_outputs"
        self.base_dir.mkdir(exist_ok=True, parents=True)
        
        # Cache for generated audio files
        self.audio_cache: Dict[str, Path] = {}
    
    def _save_model_output(self, prompt: str, response: str, model_name: str) -> str:
        """Save the model's input and output to a timestamped text file.
        
        Args:
            prompt: The input prompt sent to the model
            response: The model's response
            model_name: Name of the model that generated the response
            
        Returns:
            str: Path to the saved file
        """
        try:
            # Create outputs directory if it doesn't exist
            outputs_dir = Path("model_outputs")
            outputs_dir.mkdir(exist_ok=True)
            
            # Create a timestamped filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{outputs_dir}/model_output_{timestamp}.txt"
            
            # Prepare the content
            content = f"""=== Model Output ===
Timestamp: {time.ctime()}
Model: {model_name}

=== Input Prompt ===
{prompt}

=== Model Response ===
{response}
"""
            # Write to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
                
            logger.info(f"Model output saved to: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving model output: {e}")
            return ""

    def generate_text(self, prompt: str, max_length: int = 200, max_retries: int = 3) -> str:
        """Generate text using Hugging Face's text generation API.
        
        Args:
            prompt: The input prompt for text generation.
            max_length: Maximum number of tokens to generate.
            max_retries: Maximum number of retry attempts on failure.
            
        Returns:
            str: The generated text, or an error message if generation failed.
        """
        try:
            formatted_prompt = f"""Eres un guía turístico amigable y atractivo. Habla de manera natural y conversacional.
            Usa un tono cálido y acogedor, evita el lenguaje robótico o formal. Haz que el tour se sienta como una conversación
            casual con un amigo conocedor. Usa transiciones naturales entre temas y mantén un ritmo entusiasta pero relajado.

            {prompt}"""

            generation_params = {
                "max_new_tokens": max_length,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True,
            }
            
            logger.info(f"Sending request to model: {self.current_model}")
            logger.debug(f"Prompt: {formatted_prompt}")
            
            response = self.text_client.text_generation(
                prompt=formatted_prompt,
                model=self.current_model,
                **generation_params
            )
            
            # Clean the response
            response = response.strip() if isinstance(response, str) else str(response)
            
            # Save the input and output
            self._save_model_output(formatted_prompt, response, self.current_model)
            
            return response

        except Exception as e:
            error_msg = f"Error generating text: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if max_retries > 0:
                next_model_index = (self.available_models.index(self.current_model) + 1) % len(self.available_models)
                self.current_model = self.available_models[next_model_index]
                logger.info(f"Retrying with model {self.current_model} (attempts left: {max_retries-1})")
                return self.generate_text(prompt, max_length, max_retries-1)
                
            return f"Lo siento, no pude generar una respuesta en este momento. Error: {error_msg}"
    
    def tts(self, text: str, max_retries: int = 3) -> Optional[Path]:
        """Convertir texto a voz usando la API de Hugging Face."""
        try:
            # Crear directorio de salida si no existe
            self.base_dir.mkdir(exist_ok=True, parents=True)
            speech_file_path = self.base_dir / f"speech_tour_{int(time.time())}.wav"
            
            # Verificar si tenemos texto válido
            if not text or not text.strip():
                text = "Lo siento, no se pudo generar el contenido del tour. Por favor, intente nuevamente con una ubicación diferente."
                logger.warning("Empty text provided, using fallback message")
            
            logger.info("Initializing TTS...")
            
            # Usar la API de inferencia de Hugging Face
            try:
                # Crear un cliente de inferencia para TTS
                tts_client = InferenceClient(token=self.api_key)
                
                # Generar audio usando la API
                logger.info(f"Sending text to TTS API (length: {len(text)} chars)")
                audio_data = tts_client.text_to_speech(
                    text=text,
                    model="coqui/xtts-v2"  # Asegurarse de usar el modelo correcto
                )
                
                if not audio_data:
                    raise ValueError("No se recibieron datos de audio de la API")
                
                # Guardar el archivo de audio
                with open(speech_file_path, "wb") as f:
                    f.write(audio_data)
                    
                logger.info(f"Audio file saved to {speech_file_path} (size: {os.path.getsize(speech_file_path)} bytes)")
                return speech_file_path
                
            except Exception as e:
                logger.error(f"Error generating TTS with API: {str(e)}")
                logger.info("Falling back to simple beep sound")
                
                # Crear un sonido de bip simple como respaldo
                sample_rate = 44100
                duration = 1.0  # segundos
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                tone = np.sin(2 * np.pi * 440 * t) * 0.5  # 440 Hz tone
                
                # Asegurar que el directorio existe
                self.base_dir.mkdir(exist_ok=True, parents=True)
                speech_file_path = self.base_dir / f"error_beep_{int(time.time())}.wav"
                
                # Guardar como archivo WAV
                import soundfile as sf
                sf.write(str(speech_file_path), tone, sample_rate)
                logger.warning(f"Generated fallback beep sound at {speech_file_path}")
                return speech_file_path
                
        except Exception as e:
            logger.error(f"Critical error in TTS: {str(e)}", exc_info=True)
            return None

# Create an instance of the tour generator
try:
    audio_tour = AudioTourGenerator()
    logger.info("AudioTourGenerator initialized successfully")
except Exception as e:
    st.error(f"Error initializing the application: {str(e)}")
    st.error("Please check your API key and internet connection.")
    st.stop()

def get_css() -> str:
    """Return custom CSS styles for the Streamlit app."""
    return """
    <style>
        /* Main container */
        .main {
            max-width: 1000px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        /* Buttons */
        .stButton>button {
            width: 100%;
            border-radius: 20px;
            background: linear-gradient(90deg, #4B6CB7 0%, #182848 100%);
            color: white;
            font-weight: bold;
            padding: 0.75rem 1.5rem;
            border: none;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .stButton>button:hover {
            background: linear-gradient(90deg, #3a56a8 0%, #0f1f3d 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        
        .stButton>button:disabled {
            background: #cccccc;
            cursor: not-allowed;
        }
        
        /* Input fields */
        .stTextInput>div>div>input, 
        .stTextArea>div>div>textarea {
            border-radius: 10px;
            padding: 0.75rem;
            border: 1px solid #e0e0e0;
            font-size: 1rem;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }
        
        .stTextInput>div>div>input:focus, 
        .stTextArea>div>div>textarea:focus {
            border-color: #4B6CB7;
            box-shadow: 0 0 0 2px rgba(75, 108, 183, 0.2);
            outline: none;
        }
        
        /* Select boxes */
        .stSelectbox>div>div>div {
            border-radius: 10px;
            border: 1px solid #e0e0e0;
            padding: 0.5rem;
        }
        
        /* Alerts and info boxes */
        .stAlert {
            border-radius: 10px;
            margin: 1rem 0;
            padding: 1rem;
            border-left: 4px solid #4B6CB7;
        }
        
        /* Progress bar */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #4B6CB7 0%, #182848 100%);
        }
        
        /* Audio player */
        audio {
            width: 100%;
            margin: 1rem 0;
            border-radius: 10px;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .main {
                padding: 1rem;
            }
            
            .stButton>button {
                padding: 0.6rem 1rem;
                font-size: 0.9rem;
            }
        }
    </style>
    """

# Set page config for a better UI
st.set_page_config(
    page_title="🎧 AI Audio Tour Agent (Hugging Face)",
    page_icon="🎧",
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://huggingface.co/docs/api-inference/index',
        'Report a bug': 'https://github.com/yourusername/ai-audio-tour-agent/issues',
        'About': "# AI Audio Tour Agent\n\nCreate personalized audio tours using Hugging Face's AI models."
    }
)

# Inject custom CSS
st.markdown(get_css(), unsafe_allow_html=True)

# Sidebar for settings
with st.sidebar:
    st.title("⚙️ Settings")
    
    # API Key status
    if audio_tour.api_key:
        st.success("✅ Hugging Face API key is configured")
    else:
        st.error("❌ Hugging Face API key not found")
        st.info("Please create a .env file with your API key:")
        st.code("HUGGINGFACEHUB_API_TOKEN=your_api_key_here")
    
    # Model selection
    st.subheader("Text Generation")
    model_choice = st.selectbox(
        "Select text generation model",
        audio_tour.available_models,
        index=audio_tour.available_models.index(audio_tour.current_model) 
        if audio_tour.current_model in audio_tour.available_models else 0,
        help="Choose a model for generating tour content. Larger models may produce better results but take longer to generate."
    )
    
    # Voice selection (informational only, since we're using SpeechT5 with fixed embedding)
    st.subheader("Voice Settings")
    st.info("""
    Currently using Microsoft's SpeechT5 with a high-quality English voice.
    Voice customization will be available in a future update.
    """)
    
    # Update model settings
    if st.button("Apply Settings", key="apply_settings"):
        audio_tour.current_model = model_choice
        st.success("✅ Settings updated successfully!")
    
    # Current settings
    st.markdown("---")
    st.markdown("### Current Settings")
    st.markdown(f"**Text Model:** `{audio_tour.current_model}`")
    st.markdown("**Voice:** `Microsoft SpeechT5 (English)`")
    
    # About section
    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    This application uses Hugging Face's AI models to generate personalized audio tours.
    
    **Features:**
    - Multiple text generation models
    - Natural-sounding voice synthesis
    - Customizable tour parameters
    - Responsive design
    
    [Get an API Key](https://huggingface.co/settings/tokens) | 
    [Documentation](https://huggingface.co/docs/api-inference/index)
    """)

# Main content
st.title("🎧 AI Audio Tour Agent")
st.markdown("### Create personalized audio tours with AI")

# Initialize session state
if "tour_generated" not in st.session_state:
    st.session_state.tour_generated = False
    st.session_state.audio_file = None
    st.session_state.tour_content = ""

# Main form
with st.form("tour_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        location = st.text_input(
            "📍 Location", 
            placeholder="e.g., Paris, France",
            help="Enter the city or location for your tour"
        )
        
        duration = st.radio(
            "⏱️ Tour Duration",
            ["5 minutes", "15 minutes", "30 minutes", "60 minutes"],
            index=1,  # Default to 15 minutes
            help="Select the desired length of your tour. Shorter tours (5-15 min) are great for highlights, while longer tours provide more in-depth information."
        )
        logger.debug(f"Selected duration: {duration}")
    
    with col2:
        interests = st.multiselect(
            "🎯 Areas of Interest",
            ["History", "Architecture", "Culture", "Food & Cuisine", "Art", "Nature", "Shopping", "Local Secrets"],
            default=["History", "Architecture", "Culture"],
            help="Select topics you're interested in"
        )
        
        additional_info = st.text_area(
            "📝 Additional Information (Optional)", 
            placeholder="Any specific interests, themes, or requirements?",
            help="Add any special requests or details about your preferences"
        )
    
    # Generate button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        generate_btn = st.form_submit_button("🎙️ Generate Audio Tour", type="primary")
    with col2:
        if st.session_state.get('tour_content'):
            if st.form_submit_button("🔄 Regenerate"):
                # Clear previous results
                st.session_state.tour_generated = False
                st.session_state.audio_file = None
                st.rerun()

# Handle form submission
if generate_btn and location:
    if not interests:
        st.warning("Please select at least one area of interest.")
    else:
        with st.spinner("🚀 Crafting your personalized audio tour..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Step 1: Prepare the query
                status_text.info("Preparing your tour request...")
                progress_bar.progress(10)
                
                # Map duration to tokens
                duration_mapping = {
                    "5 minutes": "a brief 5-minute",
                    "15 minutes": "a concise 15-minute",
                    "30 minutes": "a 30-minute",
                    "60 minutes": "a comprehensive 60-minute"
                }
                
                duration_text = duration_mapping.get(duration, "a")
                query = f"Create {duration_text} audio tour of {location} focusing on {', '.join(interests)}. " \
                        f"Since this is a {duration.lower()}, please focus on the most important highlights and keep the content concise and engaging."
                if additional_info:
                    query += f" Additional information: {additional_info}"
                
                # Step 2: Generate tour content
                status_text.info("Generating tour content... (This may take a minute)")
                progress_bar.progress(30)
                
                tour_content = audio_tour.generate_text(query, max_length=500)
                st.session_state.tour_content = tour_content
                
                # Step 3: Generate audio
                status_text.info("Generating audio...")
                progress_bar.progress(70)
                
                audio_file = audio_tour.tts(tour_content)
                
                if audio_file:
                    st.session_state.audio_file = audio_file
                    st.session_state.tour_generated = True
                    progress_bar.progress(100)
                    status_text.success("Tour generated successfully!")
                else:
                    st.error("Failed to generate audio. Please try again.")
                
            except Exception as e:
                progress_bar.progress(0)
                status_text.error("An error occurred while generating your tour.")
                st.error(f"Error: {str(e)}")
                logger.error(f"Tour generation error: {str(e)}", exc_info=True)

# Display the generated tour if available
if st.session_state.get('tour_generated') and st.session_state.get('tour_content'):
    st.markdown("---")
    st.subheader("🎧 Your Audio Tour")
    
    # Display the generated content in an expandable section
    with st.expander("View Tour Transcript", expanded=True):
        st.write(st.session_state.tour_content)
    
    # Audio player
    if st.session_state.get('audio_file'):
        st.audio(str(st.session_state.audio_file), format='audio/wav')
        
        # Download button
        location_slug = "".join(c if c.isalnum() else "_" for c in location)
        with open(st.session_state.audio_file, "rb") as f:
            st.download_button(
                label="💾 Download Audio",
                data=f,
                file_name=f"{location_slug}_tour.wav",
                mime="audio/wav"
            )
    
    # Feedback section
    st.markdown("---")
    st.subheader("📝 Feedback")
    feedback = st.radio(
        "How was your tour?",
        ["😊 Great!", "😐 Okay", "😕 Could be better"],
        horizontal=True
    )
    
    if st.button("Submit Feedback"):
        st.success("Thank you for your feedback!")

# Display help/example if no tour has been generated yet
elif not st.session_state.get('tour_generated'):
    st.markdown("---")
    with st.expander("ℹ️ How to use this tool", expanded=True):
        st.markdown("""
        ### Create Your Perfect Audio Tour
        1. **Enter a location** - Any city, landmark, or place
        2. **Choose duration** - From quick highlights to in-depth tours
        3. **Select interests** - Customize what you want to hear about
        4. **Generate** - Let AI create your personalized tour
        
        ### Example Queries
        - "A 30-minute tour of Rome focusing on ancient history"
        - "A food tour of Tokyo in 60 minutes"
        - "A 15-minute art tour of Paris"
        
        [Learn more about how it works](#) | [View sample tours](#)
        """)
    
    # Add a sample tour button
    if st.button("🎧 Try a Sample Tour (Paris)", use_container_width=True):
        st.session_state.location = "Paris, France"
        st.session_state.interests = ["History", "Architecture", "Culture"]
        st.rerun()

# Add footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9em; margin-top: 2rem;">
    <p>Powered by Hugging Face 🤗 | Made with ❤️ | <a href="#" style="color: #4B6CB7;">Privacy Policy</a> | <a href="#" style="color: #4B6CB7;">Terms of Service</a></p>
</div>
""", unsafe_allow_html=True)
