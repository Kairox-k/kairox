#!/usr/bin/env python3
"""
Configuración del asistente Kairox
Edita este archivo para cambiar el modelo de IA, proveedor u opciones
"""

import os
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

# Modelos disponibles por proveedor (los mejores gratuitos primero)
AVAILABLE_MODELS = {
    "gemini": [
        "gemini-2.5-flash-preview-05-20",  # más potente, recomendado
        "gemini-2.5-flash-lite-preview-05-20",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
}

DEFAULT_CONFIG = {
    "provider": "gemini",
    "model": "gemini-2.5-flash-preview-05-20",
    "api_keys": {},
    "voice_provider": "edge-tts",
    "edge_voice": "es-MX-JorgeNeural",
    "max_tokens": 1500,
    "temperature": 0.75,
}

def load_config():
    """Carga la configuración desde config.json"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                saved = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(saved)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    """Guarda la configuración en config.json"""
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_api_key(provider=None):
    """Obtiene la API key para un proveedor dado"""
    cfg = load_config()
    prov = provider or cfg["provider"]
    # Buscar en config
    key = cfg.get("api_keys", {}).get(prov)
    if key:
        return key
    # Buscar en variables de entorno
    env_names = {
        "gemini": ["GEMINI_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
    }
    for env in env_names.get(prov, []):
        key = os.environ.get(env)
        if key:
            return key
    # Buscar en .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith(f"{env_names.get(prov, [''])[0]}="):
                    return line.strip().split("=", 1)[1]
    return None

def get_model_name():
    """Devuelve el modelo activo"""
    return load_config()["model"]

def get_provider():
    """Devuelve el proveedor activo"""
    return load_config()["provider"]

def list_models_for_provider(provider):
    """Lista los modelos para un proveedor"""
    return AVAILABLE_MODELS.get(provider, [])