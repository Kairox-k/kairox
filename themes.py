#!/usr/bin/env python3
"""
Sistema de paletas de colores para Kairox
Cada tema define colores para todos los elementos de la GUI
"""

THEMES = {
    "Kairox Rojo": {
        "name": "Kairox Rojo",
        "emoji": "🔴",
        "bg_root": "#000000",
        "bg_frame": "#0d0d0d",
        "bg_chat": "#111111",
        "accent": "#ff2d2d",
        "accent_green": "#00e676",
        "accent_red": "#ff1744",
        "accent_purple": "#7c4dff",
        "text_white": "#f5f5f5",
        "text_gray": "#8a8a8a",
        "highlight": "#1a1a1a",
        "btn_inactive": "#1a1a1a",
        "btn_hover": "#330000",
    },
    "Azul Cyber": {
        "name": "Azul Cyber",
        "emoji": "🔵",
        "bg_root": "#0a0e27",
        "bg_frame": "#0d1333",
        "bg_chat": "#111a3a",
        "accent": "#00b4d8",
        "accent_green": "#00ff88",
        "accent_red": "#ff4d6a",
        "accent_purple": "#7b68ee",
        "text_white": "#e8f0ff",
        "text_gray": "#6b7fa3",
        "highlight": "#162050",
        "btn_inactive": "#0d1a40",
        "btn_hover": "#002a3d",
    },
    "Verde Matrix": {
        "name": "Verde Matrix",
        "emoji": "🟢",
        "bg_root": "#000000",
        "bg_frame": "#050505",
        "bg_chat": "#0a0a0a",
        "accent": "#00ff41",
        "accent_green": "#39ff14",
        "accent_red": "#ff0033",
        "accent_purple": "#00ff88",
        "text_white": "#d0ffb0",
        "text_gray": "#2a6b2a",
        "highlight": "#0d1a0d",
        "btn_inactive": "#0a1a0a",
        "btn_hover": "#003300",
    },
    "Púrpura Neon": {
        "name": "Púrpura Neon",
        "emoji": "🟣",
        "bg_root": "#0f0f1a",
        "bg_frame": "#131322",
        "bg_chat": "#18182e",
        "accent": "#b041ff",
        "accent_green": "#76ff03",
        "accent_red": "#ff4081",
        "accent_purple": "#d500f9",
        "text_white": "#f0e6ff",
        "text_gray": "#7a6a99",
        "highlight": "#201a3a",
        "btn_inactive": "#1a1530",
        "btn_hover": "#2a1a40",
    },
    "Blanco Limpio": {
        "name": "Blanco Limpio",
        "emoji": "⚪",
        "bg_root": "#e8e8e8",
        "bg_frame": "#f0f0f0",
        "bg_chat": "#ffffff",
        "accent": "#1a73e8",
        "accent_green": "#0d904f",
        "accent_red": "#d93025",
        "accent_purple": "#9334e6",
        "text_white": "#1a1a1a",
        "text_gray": "#666666",
        "highlight": "#d8d8d8",
        "btn_inactive": "#e0e0e0",
        "btn_hover": "#c8dcf5",
    },
    "Naranja Fuego": {
        "name": "Naranja Fuego",
        "emoji": "🟠",
        "bg_root": "#0d0000",
        "bg_frame": "#1a0800",
        "bg_chat": "#220e00",
        "accent": "#ff6d00",
        "accent_green": "#76ff03",
        "accent_red": "#ff1744",
        "accent_purple": "#ff9100",
        "text_white": "#fff3e0",
        "text_gray": "#8a5a3a",
        "highlight": "#2a1200",
        "btn_inactive": "#1a0e00",
        "btn_hover": "#3a1800",
    },
}

DEFAULT_THEME = "Kairox Rojo"

def get_theme(name=None):
    """Devuelve un tema por nombre. Si no existe, devuelve el por defecto"""
    if name and name in THEMES:
        return THEMES[name]
    return THEMES[DEFAULT_THEME]

def list_themes():
    """Devuelve la lista de nombres de temas disponibles"""
    return list(THEMES.keys())

def next_theme(current_name):
    """Devuelve el siguiente tema en la lista"""
    names = list_themes()
    if current_name not in names:
        return names[0]
    idx = names.index(current_name)
    return names[(idx + 1) % len(names)]