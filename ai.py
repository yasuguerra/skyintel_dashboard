import openai
import logging
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def get_openai_response(prompt, context=""):
    """Función para obtener respuesta de OpenAI."""
    try:
        full_prompt = f"{context}\n\nPregunta/Tarea: {prompt}\n\nResponde en español:"
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres SkyIntel AI, un asistente experto en análisis de datos web, GA4 y redes sociales. Responde en español, claro, conciso y enfocado en insights accionables."},
                {"role": "user", "content": full_prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error llamando a OpenAI: {e}")
        return f"Hubo un error al contactar al asistente de IA: {e}. ¿Está bien configurada la API Key?"