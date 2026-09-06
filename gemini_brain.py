#!/usr/bin/env python3
"""
Cerebro de IA de Kairox — multi-proveedor
Soporta: Gemini (Google) + OpenAI (ChatGPT) + búsqueda web (DuckDuckGo)
"""

import os
import sys
import json
import time
import warnings
from pathlib import Path

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    warnings.filterwarnings('ignore')
    from ddgs import DDGS
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False

from config import load_config, save_config, get_api_key, get_model_name, get_provider

MIME_BY_EXT = {
    '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.webp': 'image/webp', '.gif': 'image/gif', '.bmp': 'image/bmp',
    '.txt': 'text/plain', '.md': 'text/markdown', '.csv': 'text/csv',
    '.json': 'application/json', '.xml': 'application/xml',
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg',
}

def guess_mime(path):
    ext = os.path.splitext(str(path))[1].lower()
    return MIME_BY_EXT.get(ext, 'application/octet-stream')


class GeminiBrain:
    """Cerebro multi-proveedor con búsqueda web"""

    def __init__(self, api_key=None):
        self.config = load_config()
        self.provider = self.config["provider"]
        self.model_name = self.config["model"]
        self.max_tokens = self.config.get("max_tokens", 1500)
        self.temperature = self.config.get("temperature", 0.75)
        self.connected = False
        self.client = None

        # Cargar clave
        if not api_key:
            api_key = get_api_key()
        self.api_key = api_key

        if self.api_key:
            self._connect()

    def _connect(self):
        if self.provider == "gemini":
            self._connect_gemini()
        elif self.provider == "openai":
            self._connect_openai()

    def _connect_gemini(self):
        if not GEMINI_AVAILABLE:
            print("⚠️ google-genai no instalado")
            return
        try:
            self.client = genai.Client(api_key=self.api_key)
            self.connected = True
            print(f"🔗 Conectado a Gemini ({self.model_name})")
        except Exception as e:
            print(f"⚠️ Error Gemini: {e}")

    def _connect_openai(self):
        if not OPENAI_AVAILABLE:
            print("⚠️ openai no instalado")
            return
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            self.connected = True
            print(f"🔗 Conectado a OpenAI ({self.model_name})")
        except Exception as e:
            print(f"⚠️ Error OpenAI: {e}")

    def is_available(self):
        return self.connected

    def search_web(self, query, max_results=5):
        if not WEB_SEARCH_AVAILABLE:
            return []
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))
        except Exception:
            return []

    def search_with_context(self, prompt, max_results=5):
        results = self.search_web(prompt, max_results)
        if not results:
            return ""
        context = "INFORMACIÓN RECIENTE DE INTERNET (búsqueda web):\n"
        for i, r in enumerate(results, 1):
            context += f"\n[{i}] {r.get('title','')}\n{r.get('body','')}\nFuente: {r.get('href','')}\n"
        return context

    def transcribe_audio(self, wav_data):
        if not self.connected:
            return None
        try:
            if self.provider == "gemini":
                resp = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        'Transcribe exactamente lo que dice el usuario en español:',
                        types.Part.from_bytes(data=wav_data, mime_type="audio/wav")
                    ],
                    config=types.GenerateContentConfig(max_output_tokens=300, temperature=0.0),
                )
                return resp.text.strip() if resp and resp.text else None
            elif self.provider == "openai":
                import tempfile, os as _os
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.write(wav_data)
                tmp.close()
                with open(tmp.name, 'rb') as f:
                    tr = self.client.audio.transcriptions.create(model="whisper-1", file=f, language="es")
                _os.unlink(tmp.name)
                return tr.text.strip() if tr and tr.text else None
        except Exception:
            return None

    def _build_web_context(self, prompt, use_web):
        if use_web:
            return self.search_with_context(prompt)
        return ""

    # ─── Gemini ───
    def _gemini_ask(self, contents, system_prompt, max_tokens, retries):
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    temperature=self.temperature,
                )
                response = self.client.models.generate_content(
                    model=self.model_name, contents=contents, config=config,
                )
                if response and response.text:
                    return response.text.strip()
                return "No pude generar una respuesta."
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                    time.sleep(attempt * 3)
                elif "503" in last_error or "UNAVAILABLE" in last_error:
                    time.sleep(attempt * 2)
                else:
                    if attempt == 1:
                        continue
                    break
        return self._friendly_error(last_error)

    # ─── OpenAI ───
    def _openai_ask(self, user_content, system_prompt, max_tokens, retries):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_name, messages=messages,
                    max_tokens=max_tokens, temperature=self.temperature,
                )
                if resp and resp.choices:
                    return resp.choices[0].message.content.strip()
                return "No pude generar una respuesta."
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "rate_limit" in last_error:
                    time.sleep(attempt * 3)
                else:
                    if attempt == 1:
                        continue
                    break
        return self._friendly_error(last_error)

    def _friendly_error(self, error):
        if not error:
            return "Error desconocido al contactar la IA."
        if "429" in error or "RESOURCE_EXHAUSTED" in error or "rate_limit" in error:
            return "La IA está sobrecargada o la cuota se agotó. Espera un momento."
        if "503" in error or "UNAVAILABLE" in error:
            return "La IA está con alta demanda ahora mismo."
        return f"Error al contactar con la IA: {error}"

    def ask(self, prompt, use_web=True, max_tokens=None, retries=3):
        if not self.connected:
            return None
        max_tokens = max_tokens or self.max_tokens
        system_prompt = """Eres Kairox, un asistente de voz español de alto nivel.
Responde SIEMPRE en español con respuestas completas, detalladas y bien estructuradas de 4 a 8 frases.
Piensa con cuidado y da respuestas profundas, útiles y prácticas.
Te llamas Kairox.
Convierte información de internet en una explicación clara y digerible por voz.
Cuando sea útil, estructura con pasos, causas, ejemplos o puntos clave.
Si hace falta, distingue datos verificados de especulaciones.
Si no hay información suficiente, dilo honestamente."""

        web_context = self._build_web_context(prompt, use_web)
        user_content = prompt
        if web_context:
            user_content = f"{web_context}\n\nPREGUNTA DEL USUARIO:\n{prompt}"

        if self.provider == "gemini":
            return self._gemini_ask(user_content, system_prompt, max_tokens, retries)
        elif self.provider == "openai":
            return self._openai_ask(user_content, system_prompt, max_tokens, retries)
        return None

    def ask_with_file(self, prompt, file_path, use_web=True, max_tokens=None, retries=3):
        if not self.connected or not file_path:
            return None
        max_tokens = max_tokens or self.max_tokens
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
        except Exception as e:
            return f"No pude leer el archivo: {e}"

        mime = guess_mime(file_path)
        is_image = mime.startswith('image/')
        system_prompt = """Eres Kairox, un asistente con Gemini que analiza archivos e imágenes.
Responde SIEMPRE en español con respuestas detalladas y completas (4 a 8 frases).
Describe con precisión lo que ves en la imagen o el contenido del documento.""" if is_image else \
"""Eres Kairox, un asistente que lee y analiza documentos.
Responde SIEMPRE en español con respuestas detalladas y completas (4 a 8 frases).
Resume el contenido, extrae datos clave, cifras, fechas, nombres y puntos importantes."""

        web_context = self._build_web_context(prompt, use_web)

        if self.provider == "gemini":
            file_part = types.Part.from_bytes(data=file_data, mime_type=mime)
            contents = [web_context, file_part, prompt] if web_context else [file_part, prompt]
            return self._gemini_ask(contents, system_prompt, max_tokens, retries)

        elif self.provider == "openai":
            import tempfile, base64, _io
            # OpenAI: text files inline, images via URL (base64)
            content_parts = []
            if web_context:
                content_parts.append({"type": "text", "text": web_context})
            if is_image:
                b64 = base64.b64encode(file_data).decode()
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })
                content_parts.append({"type": "text", "text": prompt})
            else:
                text_content = file_data.decode('utf-8', errors='replace')[:8000]
                content_parts.append({
                    "type": "text",
                    "text": f"CONTENIDO DEL ARCHIVO:\n{text_content}\n\nPREGUNTA: {prompt}"
                })
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_parts},
            ]
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_name, messages=messages,
                    max_tokens=max_tokens, temperature=self.temperature,
                )
                if resp and resp.choices:
                    return resp.choices[0].message.content.strip()
                return "No pude analizar el archivo."
            except Exception as e:
                return self._friendly_error(str(e))

        return None

    def generate_code(self, prompt, kind="code", max_tokens=None, retries=2):
        if not self.connected:
            return None
        max_tokens = max_tokens or 2400
        if kind == "pseudo":
            sys_p = """Eres Kairox. Genera PSEUDOCÓDIGO claro y bien estructurado en español.
Devuelve SOLO el pseudocódigo dentro de un bloque ``` seguido de 2 frases resumiendo la lógica.
Usa INICIO, ENTRADA, MIENTRAS, SI...ENTONCES, FIN, etc."""
        else:
            sys_p = """Eres Kairox. Genera código correcto y funcional.
Devuelve SOLO el código dentro de un bloque ```lenguaje ... ``` seguido de 2 frases explicando qué hace.
Incluye comentarios útiles en español y usa buenas prácticas."""

        if self.provider == "gemini":
            return self._gemini_ask(prompt, sys_p, max_tokens, retries)
        elif self.provider == "openai":
            return self._openai_ask(prompt, sys_p, max_tokens, retries)
        return None


def save_api_key(key, provider="gemini"):
    """Guarda la API key en .env"""
    env_path = Path(__file__).parent / ".env"
    env_var = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider, "GEMINI_API_KEY")
    key_found = False
    lines = []
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith(f"{env_var}="):
                    lines.append(f"{env_var}={key}\n")
                    key_found = True
                else:
                    lines.append(line)
    if not key_found:
        lines.append(f"{env_var}={key}\n")
    with open(env_path, 'w') as f:
        f.writelines(lines)
    print(f"✅ API key de {provider} guardada")


def get_gemini_brain():
    brain = GeminiBrain()
    if not brain.is_available():
        print("""
❌ IA no conectada. Opciones:
1. Gemini (gratis): python -c "from gemini_brain import save_api_key; save_api_key('tu_key')"
2. OpenAI: export OPENAI_API_KEY="sk-..."
O edita config.json para cambiar proveedor y modelo.
""")
    return brain