#!/usr/bin/env python3
"""
Interfaz Gráfica para Asistente de Voz IA Local - Diseño Moderno Transparente
"""

import speech_recognition as sr
import json
import sys
import os
import threading
import subprocess
import audioop
import time
from datetime import datetime
import numpy as np
from vosk import Model, KaldiRecognizer
import tkinter as tk
from tkinter import scrolledtext, filedialog, ttk
from voice_engine import VoiceEngine
from gemini_brain import GeminiBrain
from memory import MemorySystem
from spotify_control import handle_music_command, is_music_command
from file_manager import handle_file_command
from themes import THEMES, DEFAULT_THEME, get_theme, list_themes, next_theme
from config import load_config

_CONFIG = load_config()

THEME_CONFIG = os.path.join(os.path.dirname(__file__), "theme_config.json")

def _load_saved_theme_name():
    """Lee el tema guardado en disco"""
    try:
        with open(THEME_CONFIG) as f:
            return json.load(f).get("theme", DEFAULT_THEME)
    except Exception:
        return DEFAULT_THEME

def _is_light_theme():
    """Detecta si el tema activo es claro (p.ej. Blanco Limpio)"""
    try:
        r, g, b = (int(BG_ROOT.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        return (r + g + b) / 3 > 128
    except Exception:
        return False

def _hex_to_rgb(color):
    """Convierte '#rrggbb' a tupla (r, g, b)"""
    color = color.lstrip('#')
    if len(color) != 6:
        return (255, 255, 255)
    return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))

def _blend(base_color, accent_rgb, weight):
    """Mezcla un color base con el acento según el peso (0..1)"""
    base_rgb = _hex_to_rgb(base_color)
    r = int(base_rgb[0] * (1 - weight) + accent_rgb[0] * weight)
    g = int(base_rgb[1] * (1 - weight) + accent_rgb[1] * weight)
    b = int(base_rgb[2] * (1 - weight) + accent_rgb[2] * weight)
    return f'#{r:02x}{g:02x}{b:02x}'

def _save_theme_name(name):
    """Guarda el tema activo en disco"""
    try:
        with open(THEME_CONFIG, "w") as f:
            json.dump({"theme": name}, f)
    except Exception:
        pass

def load_theme(name):
    """Aplica un tema a las constantes globales de color"""
    t = get_theme(name)
    globals().update({
        'BG_ROOT': t['bg_root'],
        'BG_FRAME': t['bg_frame'],
        'BG_CHAT': t['bg_chat'],
        'ACCENT': t['accent'],
        'ACCENT_GREEN': t['accent_green'],
        'ACCENT_RED': t['accent_red'],
        'ACCENT_PURPLE': t['accent_purple'],
        'TEXT_WHITE': t['text_white'],
        'TEXT_GRAY': t['text_gray'],
        'HIGHLIGHT': t['highlight'],
        'BTN_INACTIVE': t['btn_inactive'],
        'BTN_HOVER': t['btn_hover'],
    })
    return t

# Cargar tema inicial
CURRENT_THEME = load_theme(_load_saved_theme_name())

class RoundedButton(tk.Canvas):
    """Botón moderno con esquinas redondeadas"""
    
    def __init__(self, parent, text, command, font_size=11, bg_color=None,
                 text_color=None, width=140, height=42, radius=21):
        if bg_color is None:
            bg_color = ACCENT_GREEN
        if text_color is None:
            text_color = BG_ROOT
        super().__init__(parent, width=width, height=height, bg=BG_ROOT,
                        highlightthickness=0, bd=0)
        self.command = command
        self.bg_color = bg_color
        self.text_color = text_color
        self.width = width
        self.height = height
        self.radius = radius
        self.font_size = font_size
        self.text = text
        self._hover = False
        
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)
        
        self.draw()
        
    def draw(self):
        """Dibuja el botón"""
        self.delete('all')
        color = self.bg_color if not self._hover else self._lighten(self.bg_color)
        self.create_rounded_rect(1, 1, self.width-1, self.height-1, self.radius, fill=color, outline='')
        self.create_text(self.width//2, self.height//2, text=self.text,
                        fill=self.text_color, font=("Segoe UI", self.font_size, "bold"))
        
    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        """Crea un rectángulo con esquinas redondeadas"""
        points = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
        
    def _lighten(self, color):
        """Aclara un color"""
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = min(255, int(r + 35))
            g = min(255, int(g + 35))
            b = min(255, int(b + 35))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return color
            
    def _on_enter(self, event):
        self._hover = True
        self.draw()
        self.configure(cursor='hand2')
        
    def _on_leave(self, event):
        self._hover = False
        self.draw()
        
    def _on_click(self, event):
        if self.command:
            self.command()
            
    def set_text(self, text):
        """Cambia el texto del botón"""
        self.text = text
        self.draw()


class MaximizeButton(tk.Canvas):
    """Botón redondeado con icono de expandir/restaurar ventana dibujado a mano
    (no depende de glifos de la fuente, así siempre se ve)"""

    def __init__(self, parent, command, size=48, bg_color=None, icon_color=None):
        if bg_color is None:
            bg_color = ACCENT_GREEN
        if icon_color is None:
            icon_color = '#ffffff'
        super().__init__(parent, width=size, height=size, bg=BG_ROOT,
                        highlightthickness=0, bd=0)
        self.size = size
        self.bg_color = bg_color
        self.icon_color = icon_color
        self.command = command
        self._hover = False
        self.radius = size // 2

        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<Button-1>', self._on_click)

        self.draw()

    def draw(self):
        """Dibuja el botón redondeado con el icono de expandir"""
        self.delete('all')
        s = self.size
        color = self.bg_color if not self._hover else self._lighten(self.bg_color)
        self.create_rounded_rect(1, 1, s - 1, s - 1, self.radius,
                                 fill=color, outline='')
        self._draw_expand_icon()

    def _draw_expand_icon(self):
        """Icono de 4 flechas apuntando a las esquinas (ventana a pantalla grande)"""
        s = self.size
        c = self.icon_color
        unit = s * 0.14
        base = s * 0.28
        # Cuadrado central
        x1, y1 = base, base
        x2, y2 = s - base, s - base
        self.create_rectangle(x1, y1, x2, y2, outline=c, width=2)
        # Flechas desde el centro hacia las 4 esquinas
        cx, cy = s / 2, s / 2
        corners = [
            (x1 - unit, y1 - unit),  # arriba-izquierda
            (x2 + unit, y1 - unit),  # arriba-derecha
            (x1 - unit, y2 + unit),  # abajo-izquierda
            (x2 + unit, y2 + unit),  # abajo-derecha
        ]
        for tx, ty in corners:
            self.create_line(cx, cy, tx, ty, fill=c, width=2)

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        """Crea un rectángulo con esquinas redondeadas"""
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _lighten(self, color):
        """Aclara un color para el efecto hover"""
        try:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = min(255, int(r + 35))
            g = min(255, int(g + 35))
            b = min(255, int(b + 35))
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return color

    def _on_enter(self, _e=None):
        self._hover = True
        self.configure(cursor='hand2')
        self.draw()

    def _on_leave(self, _e=None):
        self._hover = False
        self.configure(cursor='')
        self.draw()

    def _on_click(self, _e=None):
        if self.command:
            self.command()

class MicButton(tk.Canvas):
    """Botón de micrófono circular animado"""
    
    def __init__(self, parent, command, size=90, bg=None):
        self.size = size
        if bg is None:
            bg = BG_ROOT
        self._mic_bg = bg
        super().__init__(parent, width=size, height=size, bg=bg,
                        highlightthickness=0, bd=0)
        self.command = command
        self.is_active = False
        self.pulse_level = 0
        self.angle = 0
        
        self.bind('<Button-1>', lambda e: self.command())
        self.draw_idle()
        
    def draw_idle(self):
        """Dibuja micrófono en estado inactivo"""
        self.delete('all')
        cx = cy = self.size // 2
        r = self.size // 2 - 4
        # Círculo exterior (color del tema, no fijo)
        self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=HIGHLIGHT, outline=ACCENT, width=2)
        # Micrófono
        self._draw_mic(cx, cy)
        
    def draw_active(self, pulse):
        """Dibuja micrófono con animación de pulso"""
        self.delete('all')
        cx = cy = self.size // 2
        r = self.size // 2 - 4
        glow = 6 + pulse * 4
        # Anillos de pulso (derivados del color de acento del tema, no fijos)
        base_r, base_g, base_b = _hex_to_rgb(ACCENT)
        for i in range(3):
            ring_r = r + i * glow
            if ring_r < self.size:
                fade = 0.35 - i * 0.10
                ring_color = _blend('#000000' if not _is_light_theme() else '#ffffff',
                                    (base_r, base_g, base_b), fade)
                self.create_oval(cx-ring_r, cy-ring_r, cx+ring_r, cy+ring_r,
                               outline=ring_color, width=1)
        # Círculo central brillante (color del tema, no fijo)
        self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=HIGHLIGHT, outline=ACCENT, width=3)
        self._draw_mic(cx, cy)
        
    def _draw_mic(self, cx, cy):
        """Dibuja el icono del micrófono"""
        # Pastilla
        self.create_rectangle(cx-10, cy-20, cx+10, cy, fill=ACCENT if not self.is_active else TEXT_WHITE,
                             outline='')
        # Arco
        self.create_arc(cx-14, cy-8, cx+14, cy+12, start=0, extent=180,
                       style=tk.ARC, outline=ACCENT if not self.is_active else TEXT_WHITE, width=3)
        # Pie
        self.create_line(cx, cy+14, cx, cy+20, fill=ACCENT if not self.is_active else TEXT_WHITE, width=3)
        self.create_line(cx-8, cy+24, cx+8, cy+24, fill=ACCENT if not self.is_active else TEXT_WHITE, width=3)
        
    def animate(self):
        """Anima el pulso cuando está activo"""
        if self.is_active:
            self.pulse_level = (self.pulse_level + 1) % 10
            self.draw_active(self.pulse_level)
            self.after(120, self.animate)
        else:
            self.draw_idle()
            
    def set_active(self, active):
        """Establece estado activo/inactivo"""
        self.is_active = active
        if active:
            self.animate()
        else:
            self.draw_idle()
            
    def set_pulse(self, level):
        """Nivel de pulso (0-1) para efecto onda de sonido"""
        self.pulse_level = level
        if self.is_active:
            self.draw_active(level)

class VoiceAssistantGUI:
    def __init__(self):
        self.root = tk.Tk(className="Kairox")
        self.root.title("Kairox - Asistente de Voz IA")
        self.root.geometry("780x640")
        self.root.configure(bg=BG_ROOT)
        
        # Transparencia de la ventana
        try:
            self.root.attributes('-alpha', 0.93)  # 93% de opacidad
        except Exception:
            pass
            
        # Hacer la ventana sin bordes estándar para look moderno
        self.root.overrideredirect(False)

        # Icono de la ventana / barra de tareas
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon_kairox.png")
            if os.path.exists(icon_path):
                self._window_icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self._window_icon)
        except Exception:
            pass
        self.root.after(300, self._set_x_wm_icon)
        # Variables
        self.is_listening = False
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 150
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.0
        self._whisper_model = None
        mic_index = _CONFIG.get("mic_index", 7)
        try:
            self.microphone = sr.Microphone(device_index=mic_index, sample_rate=16000)
        except Exception:
            self.microphone = sr.Microphone(device_index=mic_index)
        self.sample_rate = self.microphone.SAMPLE_RATE
        self.tts_engine = VoiceEngine()
        self.volume_scale = 0.4
        self.brain = GeminiBrain()
        self.brain_available = self.brain.is_available()
        self.memory = MemorySystem()
        self.pending_text = []
        self.attached_path = None

        # Crear interfaz
        self.create_widgets()

        # Cargar modelo Vosk
        self.vosk_model = None
        self.rec = None
        self.load_vosk_model()

    def _set_x_wm_icon(self):
        """Fija _NET_WM_ICON en X11 (Tk 9 ignora wm iconphoto en este entorno)"""
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon_kairox.png")
            if not os.path.exists(icon_path):
                return
            from PIL import Image
            import ctypes
            img = Image.open(icon_path).convert("RGBA")
            w, h = img.size
            pixels = [w, h]
            for r, g, b, a in img.getdata():
                pixels.append((a << 24) | (r << 16) | (g << 8) | b)
            xlib = ctypes.CDLL("libX11.so.6")
            xlib.XOpenDisplay.restype = ctypes.c_void_p
            xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            xlib.XInternAtom.restype = ctypes.c_ulong
            xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            xlib.XChangeProperty.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
                ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
            xlib.XFlush.argtypes = [ctypes.c_void_p]
            xlib.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                                        ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_int)]
            disp = xlib.XOpenDisplay(None)
            if not disp:
                return
            win_id = int(self.root.winfo_id())
            root_win = ctypes.c_ulong()
            parent_win = ctypes.c_ulong()
            children = ctypes.POINTER(ctypes.c_ulong)()
            n_children = ctypes.c_int()
            xlib.XQueryTree(disp, win_id, ctypes.byref(root_win), ctypes.byref(parent_win),
                            ctypes.byref(children), ctypes.byref(n_children))
            atom_icon = xlib.XInternAtom(disp, b"_NET_WM_ICON", 0)
            XA_CARDINAL = 6
            PropModeReplace = 0
            arr = (ctypes.c_ulong * len(pixels))(*[ctypes.c_ulong(p) for p in pixels])
            for wid in (parent_win.value, win_id):
                if wid:
                    xlib.XChangeProperty(disp, wid, atom_icon, XA_CARDINAL, 32,
                                         PropModeReplace, arr, len(arr))
            xlib.XFlush(disp)

        except Exception:
            pass

    def load_vosk_model(self):
        """Carga el modelo Vosk para reconocimiento offline"""
        model_path = "vosk-model-small-es-0.42"
        if not os.path.exists(model_path):
            self.add_message("Sistema", "Descargando modelo de voz...")
            os.system("wget -q https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip")
            os.system("unzip -q vosk-model-small-es-0.42.zip")
        
        try:
            self.vosk_model = Model(model_path)
            self.rec = KaldiRecognizer(self.vosk_model, self.sample_rate)
            self.add_message("Sistema", "Modelo de voz cargado correctamente")
        except Exception as e:
            self.add_message("Error", f"Error cargando modelo: {e}")
            
    def create_widgets(self):
        """Crea los widgets de la interfaz"""
        # Colecciones para el cambio de tema
        self._frame_root_list = []
        self._frame_frame_list = []
        self._label_root_list = []
        self._label_frame_list = []
        self._quick_buttons = []
        
        # Contenedor exterior (raíz)
        outer = tk.Frame(self.root, bg=BG_ROOT)
        outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        self._frame_root_list.append(outer)
        
        # ===== Barra lateral de comandos =====
        sidebar = tk.Frame(outer, bg=BG_FRAME, bd=1, highlightbackground=HIGHLIGHT,
                           highlightthickness=1, width=170)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        sidebar.pack_propagate(False)
        self._frame_frame_list.append(sidebar)
        self.quick_frame = sidebar

        sidebar_canvas = tk.Canvas(sidebar, bg=BG_FRAME, highlightthickness=0, bd=0,
                                   width=150)
        sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sidebar_scroll = tk.Scrollbar(sidebar, orient=tk.VERTICAL,
                                      command=sidebar_canvas.yview,
                                      bg=HIGHLIGHT, troughcolor=BG_FRAME,
                                      activebackground=ACCENT,
                                      highlightbackground=BG_FRAME,
                                      highlightcolor=BG_FRAME, width=10,
                                      borderwidth=0)
        sidebar_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)
        self._frame_frame_list.append(sidebar_canvas)

        sidebar_content = tk.Frame(sidebar_canvas, bg=BG_FRAME)
        sidebar_canvas.create_window((0, 0), window=sidebar_content, anchor='nw',
                                     tags=("sidebar_win",))
        self._frame_frame_list.append(sidebar_content)
        self._sidebar_scrollbar = sidebar_scroll
        self.sidebar_canvas = sidebar_canvas
        self.sidebar_content = sidebar_content

        # El scrollregion se fija al alto REAL del contenido (nunca con
        # bbox("all"), que crece hacia arriba al hacer scroll y genera el
        # desplazamiento "sin nada").
        def _update_scrollregion(_e=None):
            sidebar_canvas.configure(scrollregion=(0, 0,
                                                   sidebar_content.winfo_reqwidth(),
                                                   sidebar_content.winfo_reqheight()))
        sidebar_content.bind("<Configure>", _update_scrollregion)

        def _fit_content(e=None):
            sidebar_canvas.itemconfigure("sidebar_win", width=e.width)
            _update_scrollregion()
        sidebar_canvas.bind("<Configure>", _fit_content)

        def _on_sidebar_mousewheel(event):
            if event.num in (4, 5):
                delta = -1 if event.num == 4 else 1
            else:
                delta = -1 if event.delta > 0 else 1
            sidebar_canvas.yview_scroll(delta, "units")

        def _bind_wheel(_e=None):
            sidebar_canvas.bind_all("<MouseWheel>", _on_sidebar_mousewheel)
            sidebar_canvas.bind_all("<Button-4>", _on_sidebar_mousewheel)
            sidebar_canvas.bind_all("<Button-5>", _on_sidebar_mousewheel)

        def _unbind_wheel(_e=None):
            sidebar_canvas.unbind_all("<MouseWheel>")
            sidebar_canvas.unbind_all("<Button-4>")
            sidebar_canvas.unbind_all("<Button-5>")

        sidebar_canvas.bind("<Enter>", _bind_wheel)
        sidebar_canvas.bind("<Leave>", _unbind_wheel)
        sidebar_content.bind("<Enter>", _bind_wheel)
        sidebar_content.bind("<Leave>", _unbind_wheel)

        sidebar_label = tk.Label(
            sidebar_content,
            text="⚡ Comandos",
            font=("Segoe UI", 11, "bold"),
            bg=BG_FRAME,
            fg=ACCENT
        )
        sidebar_label.pack(padx=8, pady=(12, 8), anchor='w')
        self._label_frame_list.append(sidebar_label)
        self.quick_label = sidebar_label
        
        commands = [
            ("▶️", "Play", "Pon música"),
            ("⏸", "Pausa", "Pausa la música"),
            ("⏭", "Siguiente", "Siguiente canción"),
            ("🔁", "Repetir lista", "Repite la playlist"),
            ("🎵", "Volumen", "Sube el volumen"),
            ("🕐", "Hora", "¿Qué hora es?"),
            ("📅", "Fecha", "¿Qué fecha es?"),
            ("🧠", "Sabes de mí", "¿Qué sabes de mí?"),
            ("💾", "Memoria", "Memoria"),
            ("💻", "Código", None),  # comando especial, se maneja abajo
            ("📐", "Pseudo", None),  # comando especial, se maneja abajo
            ("🔍", "Buscar", None),  # comando especial, se maneja abajo
            ("📎", "Adjuntar", "Adjunta un archivo"),
            ("🧐", "Analiza", "Analiza el archivo adjunto"),
            ("👋", "Adiós", "Adiós"),
        ]
        
        for emoji, label, cmd in commands:
            if cmd is None and label == "Código":
                action = lambda: self.ask_code("code")
            elif cmd is None and label == "Pseudo":
                action = lambda: self.ask_code("pseudo")
            elif cmd is None and label == "Buscar":
                action = self.ask_search
            else:
                action = lambda c=cmd: self.execute_command(c)
            btn = RoundedButton(
                sidebar_content,
                f"{emoji} {label}",
                action,
                font_size=8,
                bg_color=BTN_INACTIVE,
                text_color=TEXT_WHITE,
                width=150,
                height=30,
                radius=15
            )
            btn.pack(side=tk.TOP, padx=8, pady=3)
            self._quick_buttons.append(btn)
        
        # ===== Frame principal (derecha) =====
        main_frame = tk.Frame(outer, bg=BG_ROOT)
        main_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self._frame_root_list.append(main_frame)
        
        # ===== Título =====
        title_frame = tk.Frame(main_frame, bg=BG_ROOT)
        title_frame.pack(fill=tk.X, pady=(0, 12))
        self._frame_root_list.append(title_frame)
        
        # Icono de apariencia (paleta de colores) en la esquina
        self.theme_button = RoundedButton(
            title_frame, "🎨", self.cycle_theme,
            bg_color=ACCENT, text_color='#ffffff', width=44, height=36, radius=18
        )
        self.theme_button.pack(side=tk.RIGHT)
        self.theme_button.bind('<Enter>', lambda e: self.set_status_text(
            f"Apariencia: {CURRENT_THEME['name']} (clic para cambiar)", ACCENT), add='+')

        # Botón para minimizar a widget flotante (micrófono + chat en el escritorio)
        self.minimize_button = RoundedButton(
            title_frame, "—", self.minimize_to_widget,
            bg_color=ACCENT, text_color='#ffffff', width=40, height=36, radius=18
        )
        self.minimize_button.pack(side=tk.RIGHT)
        self.minimize_button.bind('<Enter>', lambda e: self.set_status_text(
            "Minimizar a widget flotante en el escritorio", ACCENT), add='+')
        
        # Selector de IA (Gemini / opencode / Automático)
        self.ai_mode = tk.StringVar(value="Automático")
        ai_label = tk.Label(title_frame, text="IA:", font=("Segoe UI", 10, "bold"),
                            bg=BG_ROOT, fg=TEXT_GRAY)
        ai_label.pack(side=tk.RIGHT, padx=(0, 6), pady=(10, 6))
        self._label_root_list.append(ai_label)
        self._style_combobox()
        self.ai_selector = ttk.Combobox(
            title_frame, textvariable=self.ai_mode, state="readonly",
            values=["Automático", "Gemini", "opencode"], width=12,
            font=("Segoe UI", 10), style="Kairox.TCombobox"
        )
        self.ai_selector.pack(side=tk.RIGHT, pady=(8, 4))
        self.ai_selector.bind("<<ComboboxSelected>>", self._on_ai_change)

        # Selector de modelo de pensamiento
        from config import AVAILABLE_MODELS, save_config as _save_cfg
        self.model_selector_var = tk.StringVar(value=_CONFIG.get("model", "gemini-2.5-flash-preview-05-20"))
        model_label = tk.Label(title_frame, text="Modelo:", font=("Segoe UI", 10, "bold"),
                               bg=BG_ROOT, fg=TEXT_GRAY)
        model_label.pack(side=tk.RIGHT, padx=(0, 6), pady=(10, 6))
        self._label_root_list.append(model_label)
        prov = _CONFIG.get("provider", "gemini")
        self.model_selector = ttk.Combobox(
            title_frame, textvariable=self.model_selector_var, state="readonly",
            values=AVAILABLE_MODELS.get(prov, []), width=28,
            font=("Segoe UI", 9), style="Kairox.TCombobox"
        )
        self.model_selector.pack(side=tk.RIGHT, pady=(8, 4))
        self.model_selector.bind("<<ComboboxSelected>>", self._on_model_change)
        
        title_label = tk.Label(
            title_frame,
            text="⚡ KAIROX · Asistente de Voz IA",
            font=("Segoe UI", 22, "bold"),
            bg=BG_ROOT,
            fg=ACCENT
        )
        title_label.pack()
        self._label_root_list.append(title_label)
        self.title_label = title_label

        self.beta_badge = tk.Label(
            title_frame,
            text="BETA",
            font=("Segoe UI", 9, "bold"),
            bg=ACCENT,
            fg=self._beta_badge_fg()
        )
        self.beta_badge.pack(pady=(0, 2))
        
        subtitle_label = tk.Label(
            title_frame,
            text="Kairox con Gemini · Acceso a toda la web",
            font=("Segoe UI", 10),
            bg=BG_ROOT,
            fg=TEXT_GRAY
        )
        subtitle_label.pack(pady=(2, 0))
        self._label_root_list.append(subtitle_label)
        self.subtitle_label = subtitle_label
        
        # ===== Barra de estado =====
        status_frame = tk.Frame(main_frame, bg=BG_FRAME, highlightbackground=ACCENT,
                               highlightthickness=0, bd=0)
        status_frame.pack(fill=tk.X, pady=(0, 15))
        self._frame_frame_list.append(status_frame)
        
        # Barra de estatus con gradiente
        self.status_canvas = tk.Canvas(status_frame, height=38, bg=BG_FRAME, highlightthickness=0, bd=0)
        self.status_canvas.pack(fill=tk.X)
        self._frame_frame_list.append(self.status_canvas)
        
        # Indicador de Gemini
        gemini_status = "● Gemini conectado" if self.brain_available else "● Gemini sin conectar"
        gemini_color = ACCENT_GREEN if self.brain_available else ACCENT_RED
        self.status_canvas.create_text(
            335, 20, text="|",
            fill=TEXT_GRAY, font=("Segoe UI", 11)
        )
        
        # LED de escucha
        self.led = self.status_canvas.create_oval(12, 12, 28, 28, fill=BTN_INACTIVE, outline=TEXT_GRAY)
        self.status_text = self.status_canvas.create_text(
            42, 20, text="Estado: Listo", anchor='w',
            fill=TEXT_WHITE, font=("Segoe UI", 11)
        )
        
        # Barra de volumen
        self.volume_display = self.status_canvas.create_text(
            560, 20, text="Vol ▮▮▮", anchor='e',
            fill=ACCENT_GREEN, font=("Segoe UI", 10)
        )
        self.status_canvas.update_idletasks()
        vol_left = self.status_canvas.bbox(self.volume_display)[0]
        self.gemini_indicator = self.status_canvas.create_text(
            vol_left - 24, 20, text=gemini_status, anchor='e',
            fill=gemini_color, font=("Segoe UI", 9, "bold")
        )
        self.status_canvas.tag_bind(self.led, '<Button-1>', lambda e: None)
        
        # ===== Botón de micrófono =====
        mic_frame = tk.Frame(main_frame, bg=BG_ROOT)
        mic_frame.pack(pady=(0, 15))
        self._frame_root_list.append(mic_frame)
        
        self.mic_button = MicButton(mic_frame, self.toggle_listening, size=100)
        self.mic_button.pack()
        
        self.mic_status_label = tk.Label(
            mic_frame,
            text="Haz clic en el micrófono para hablar",
            font=("Segoe UI", 10),
            bg=BG_ROOT,
            fg=TEXT_GRAY
        )
        self.mic_status_label.pack(pady=(8, 0))
        self._label_root_list.append(self.mic_status_label)
        
        # Indicador de transcripción EN VIVO (lo que Kairox va escuchando)
        self.live_transcript_label = tk.Label(
            mic_frame,
            text="",
            font=("Consolas", 10),
            bg=BG_ROOT,
            fg=ACCENT_GREEN,
            wraplength=520,
            justify=tk.LEFT,
            anchor='w'
        )
        self.live_transcript_label.pack(fill=tk.X, padx=6, pady=(4, 0))
        self._label_root_list.append(self.live_transcript_label)
        
        # ===== Área de chat =====
        chat_frame = tk.Frame(main_frame, bg=BG_FRAME, bd=0, highlightthickness=0)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        self._frame_frame_list.append(chat_frame)
        self.chat_frame = chat_frame

        # Marco con borde del color del tema
        chat_border = tk.Frame(chat_frame, bg=HIGHLIGHT, bd=0, highlightthickness=0)
        chat_border.pack(fill=tk.BOTH, expand=True)
        self.chat_border = chat_border

        self.chat_display = scrolledtext.ScrolledText(
            chat_border,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Segoe UI", 10),
            bg=BG_CHAT,
            fg=TEXT_WHITE,
            insertbackground=ACCENT,
            selectbackground=ACCENT_PURPLE,
            relief=tk.FLAT,
            padx=12,
            pady=10
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Barra de scroll acorde al tema
        self.chat_scrollbar = self.chat_display.vbar
        self.chat_scrollbar.configure(
            bg=HIGHLIGHT, troughcolor=BG_CHAT, activebackground=ACCENT,
            highlightbackground=HIGHLIGHT, highlightthickness=0,
            bd=0, relief=tk.FLAT, borderwidth=0, elementborderwidth=0, width=12
        )

        # ===== Barra de escritura (chat por texto sin hablar) =====
        input_frame = tk.Frame(chat_frame, bg=BG_FRAME)
        input_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._frame_frame_list.append(input_frame)
        self.input_frame = input_frame

        self.text_input = tk.Entry(
            input_frame,
            font=("Segoe UI", 11),
            bg=HIGHLIGHT,
            fg=TEXT_GRAY,
            insertbackground=ACCENT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=HIGHLIGHT,
            highlightcolor=ACCENT
        )
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=7)
        self.text_input.insert(0, "Escribe tu petición aquí...")
        self.text_input.bind('<Return>', lambda e: self.send_text_message())
        self.text_input.bind('<FocusIn>', self._clear_input_placeholder)
        self.text_input.bind('<FocusOut>', self._restore_input_placeholder)

        send_button = RoundedButton(
            input_frame, "Enviar", self.send_text_message,
            bg_color=ACCENT, text_color='#ffffff', width=90, height=36, radius=18
        )
        send_button.pack(side=tk.LEFT, padx=(8, 0))
        self.send_button = send_button
        
        # Configurar estilos de mensajes
        self.chat_display.tag_configure('user', foreground=ACCENT_GREEN, font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_configure('assistant', foreground=ACCENT, font=("Segoe UI", 10))
        self.chat_display.tag_configure('system', foreground=TEXT_GRAY, font=("Segoe UI", 9, "italic"))
        self.chat_display.tag_configure('error', foreground=ACCENT_RED, font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_configure('code', foreground=ACCENT_GREEN, font=("Consolas", 9))
        self.chat_display.tag_configure('code_label', foreground=TEXT_GRAY, font=("Segoe UI", 9, "italic"))
        self.chat_display.tag_configure('sender', foreground=ACCENT, font=("Segoe UI", 9, "bold"))
        
        # ===== Botones de control =====
        controls_frame = tk.Frame(main_frame, bg=BG_ROOT)
        controls_frame.pack(fill=tk.X, pady=(0, 15))
        self._frame_root_list.append(controls_frame)
        self.controls_frame = controls_frame
        
        self.listen_button = RoundedButton(
            controls_frame, "🎤 Escuchar", self.toggle_listening,
            bg_color=ACCENT_GREEN, text_color=BG_ROOT, width=150
        )
        self.listen_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = RoundedButton(
            controls_frame, "⏹ Detener", self.stop_listening,
            bg_color=ACCENT_RED, text_color='#ffffff', width=120
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        clear_button = RoundedButton(
            controls_frame, "🗑 Limpiar", self.clear_chat,
            bg_color=ACCENT_PURPLE, text_color='#ffffff', width=100
        )
        clear_button.pack(side=tk.LEFT, padx=(0, 10))
        self.clear_button = clear_button
        
        attach_button = RoundedButton(
            controls_frame, "📎 Adjuntar", self.attach_file,
            bg_color=ACCENT_PURPLE, text_color='#ffffff', width=95
        )
        attach_button.pack(side=tk.LEFT, padx=(0, 8))
        self.attach_button = attach_button
        
        self.detach_button = RoundedButton(
            controls_frame, "✖ Quitar", self.detach_file,
            bg_color=ACCENT_RED, text_color='#ffffff', width=60, height=42, radius=21
        )
        self.detach_button.pack(side=tk.LEFT)
        
        # Línea informativa del archivo adjunto
        self.attached_label = tk.Label(
            main_frame,
            text="📎 Sin archivo adjunto",
            font=("Segoe UI", 9),
            bg=BG_ROOT,
            fg=TEXT_GRAY
        )
        self.attached_label.pack(fill=tk.X, pady=(0, 8))
        self._label_root_list.append(self.attached_label)
        
        # Pie de página
        footer = tk.Label(
            main_frame,
            text=f"Kairox · Red neuronal de aprendizaje",
            font=("Segoe UI", 8),
            bg=BG_ROOT,
            fg=TEXT_GRAY
        )
        footer.pack(pady=(10, 0))
        self._label_root_list.append(footer)
        self.footer_label = footer
        
        # Estadísticas de memoria
        self.memory_stats_label = tk.Label(
            main_frame,
            text=self.memory.stats(),
            font=("Segoe UI", 8),
            bg=BG_ROOT,
            fg=ACCENT_GREEN
        )
        self.memory_stats_label.pack(pady=(2, 0))
        self._label_root_list.append(self.memory_stats_label)
        
    def _update_live_mini(self, text, is_final):
        """Actualiza la transcripción en vivo dentro del widget flotante"""
        if not hasattr(self, 'mini_live_label'):
            return
        def _apply():
            try:
                displayed = text if is_final else f"… {text}…"
                self.mini_live_label.configure(
                    text=f"🎙️ {displayed}",
                    fg=ACCENT_GREEN if is_final else ACCENT)
            except Exception:
                pass
        self.root.after(0, _apply)

    def minimize_to_widget(self):
        """Recoge la ventana principal y muestra un widget flotante con
        micrófono y barra de chat al costado derecho del escritorio.
        El asistente sigue funcionando (escucha, responde, habla)."""
        if getattr(self, 'is_minimized', False):
            return
        self.is_minimized = True
        # Guardar posición para restaurar igual
        self._main_geometry = self.root.geometry()
        self.root.withdraw()

        mini = tk.Toplevel(self.root)
        mini.title("Kairox Mini")
        mini.configure(bg=BG_FRAME)
        # En Wayland, las ventanas overrideredirect no reciben foco de teclado.
        # Usamos una ventana gestionada sin decoración (-type) para poder escribir.
        try:
            mini.attributes('-type', 'utility')
            mini.overrideredirect(False)
        except Exception:
            mini.overrideredirect(True)
        mini.attributes('-topmost', True)
        try:
            mini.attributes('-alpha', 0.96)
        except Exception:
            pass
        self.mini_win = mini
        self._mini_drag = {"x": 0, "y": 0}

        def _start_drag(e):
            self._mini_drag = {"x": e.x_root - mini.winfo_x(), "y": e.y_root - mini.winfo_y()}
        def _do_drag(e):
            try:
                mini.geometry(f"+{e.x_root - self._mini_drag['x']}+{e.y_root - self._mini_drag['y']}")
            except Exception:
                pass
        mini.bind('<ButtonPress-1>', _start_drag)
        mini.bind('<B1-Motion>', _do_drag)

        def _focus_mini_input(_e=None):
            try:
                self.mini_text_input.focus_set()
            except Exception:
                pass
        mini.bind('<Button-1>', _focus_mini_input, add='+')

        w, h = 264, 360
        sw, sh = mini.winfo_screenwidth(), mini.winfo_screenheight()
        x = sw - w - 16
        y = sh - h - 90
        mini.geometry(f"{w}x{h}+{x}+{y}")

        # Fondo
        bg = tk.Frame(mini, bg=BG_FRAME, highlightbackground=HIGHLIGHT, highlightthickness=1)
        bg.pack(fill=tk.BOTH, expand=True)
        self.mini_bg = bg

        # Cabecera del widget con botón de restaurar ventana a pantalla grande
        header = tk.Frame(bg, bg=BG_FRAME)
        header.pack(fill=tk.X, pady=(6, 0))
        title_mini = tk.Label(
            header, text="⚡ Kairox", font=("Segoe UI", 11, "bold"),
            bg=BG_FRAME, fg=ACCENT)
        title_mini.pack(side=tk.LEFT, padx=12)
        restore = MaximizeButton(
            header, self.restore_from_widget,
            size=46, bg_color=ACCENT, icon_color='#ffffff'
        )
        restore.pack(side=tk.RIGHT, padx=8)
        restore.bind('<Enter>', lambda e: self.set_status_text(
            "Restaurar ventana grande", ACCENT), add='+')
        self.mini_restore_button = restore

        # Micrófono pequeño
        mic_holder = tk.Frame(bg, bg=BG_FRAME)
        mic_holder.pack(pady=(10, 4))
        mini_mic = MicButton(mic_holder, self.toggle_listening, size=64, bg=BG_FRAME)
        mini_mic.pack()
        self.mini_mic_button = mini_mic

        # Indicador de estado del widget
        self.mini_status = tk.Label(
            bg, text="● Escuchando" if self.is_listening else "Haz clic en el micrófono",
            font=("Segoe UI", 9), bg=BG_FRAME, fg=ACCENT_GREEN if self.is_listening else TEXT_GRAY)
        self.mini_status.pack(pady=(0, 4))

        # Transcripción en vivo
        self.mini_live_label = tk.Label(
            bg, text="", font=("Consolas", 8), bg=BG_FRAME, fg=ACCENT_GREEN, wraplength=240)
        self.mini_live_label.pack(fill=tk.X, padx=6)

        # Área de chat del widget mini
        mini_chat = tk.Text(
            bg, height=5, wrap=tk.WORD, relief=tk.FLAT, state=tk.DISABLED,
            font=("Segoe UI", 9), bg=BG_ROOT, fg=TEXT_WHITE,
            highlightthickness=1, highlightbackground=HIGHLIGHT)
        mini_chat.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))
        mini_chat.tag_configure('mini_user', foreground=ACCENT_GREEN)
        mini_chat.tag_configure('mini_assistant', foreground=ACCENT)
        mini_chat.tag_configure('mini_system', foreground=TEXT_GRAY)
        mini_chat.tag_configure('mini_error', foreground=ACCENT_RED)
        self.mini_chat_display = mini_chat

        # Barra de chat mini
        input_row = tk.Frame(bg, bg=BG_FRAME)
        input_row.pack(fill=tk.X, padx=8, pady=8)
        self.mini_text_input = tk.Entry(
            input_row, font=("Segoe UI", 10), bg=HIGHLIGHT, fg=TEXT_WHITE,
            insertbackground=ACCENT, relief=tk.FLAT, highlightthickness=1,
            highlightbackground=HIGHLIGHT, highlightcolor=ACCENT)
        self.mini_text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, ipady=5)
        self.mini_text_input.insert(0, "Escribe aquí...")
        self.mini_text_input.bind('<Return>', lambda e: self._mini_send())
        self.mini_text_input.bind('<FocusIn>', self._clear_mini_placeholder)
        self.mini_text_input.bind('<FocusOut>', self._restore_mini_placeholder)

        mini_send = RoundedButton(
            input_row, "➤", self._mini_send,
            bg_color=ACCENT, text_color='#ffffff', width=44, height=34, radius=17
        )
        mini_send.pack(side=tk.LEFT, padx=(6, 0))
        self.mini_send_button = mini_send

        self.add_message("Sistema", "Minimizado a widget flotante ⤢ | Sigo escuchando y respondiendo")

        try:
            mini.lift()
            mini.focus_force()
            self.mini_text_input.focus_set()
        except Exception:
            pass

    def restore_from_widget(self):
        """Recupera la ventana grande desde el widget flotante"""
        self.is_minimized = False
        try:
            if hasattr(self, 'mini_win') and self.mini_win.winfo_exists():
                self.mini_win.destroy()
        except Exception:
            pass
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.set_status_text("Estado: Listo", TEXT_WHITE)

    def _mini_send(self):
        """Envía el texto escrito en la barra del widget mini"""
        raw = self.mini_text_input.get()
        # Si hubiera quedado parte del placeholder mezclado, lo recortamos
        text = raw.replace("Escribe aquí...", "").strip()
        if not text:
            self._restore_mini_placeholder()
            return
        self.mini_text_input.delete(0, tk.END)
        if self.is_listening:
            self.stop_listening()
        self.add_message("Tú", text)
        self.process_command(text)

    def _clear_mini_placeholder(self, _e=None):
        """Borra el placeholder de la barra mini al hacer foco"""
        try:
            if self.mini_text_input.get() == "Escribe aquí...":
                self.mini_text_input.delete(0, tk.END)
                self.mini_text_input.configure(fg=TEXT_WHITE)
        except Exception:
            pass

    def _restore_mini_placeholder(self, _e=None):
        """Restaura el placeholder de la barra mini si está vacía"""
        try:
            if not self.mini_text_input.get().strip():
                self.mini_text_input.insert(0, "Escribe aquí...")
                self.mini_text_input.configure(fg=TEXT_GRAY)
        except Exception:
            pass

    def _beta_badge_fg(self):
        """Texto del sello BETA con contraste legible sobre el acento del tema"""
        try:
            r, g, b = (int(ACCENT.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            return "#14141c" if lum > 150 else "#ffffff"
        except Exception:
            return "#ffffff"

    def cycle_theme(self):
        """Cambia al siguiente tema de la paleta (sin anuncio de voz propio)"""
        global CURRENT_THEME
        prev = CURRENT_THEME['name']
        new_name = next_theme(prev)
        CURRENT_THEME = load_theme(new_name)
        _save_theme_name(new_name)
        self._recolor_ui()
        self.add_message("Sistema", f"🎨 Tema aplicado: {new_name}")

    def _style_combobox(self):
        """Aplica la tipografía y colores del tema al desplegable de IA"""
        self._ttk_style = ttk.Style()
        self._ttk_style.theme_use('clam')
        self._ttk_style.configure(
            "Kairox.TCombobox",
            fieldbackground=HIGHLIGHT, background=HIGHLIGHT, foreground=TEXT_WHITE,
            arrowcolor=ACCENT, bordercolor=HIGHLIGHT, lightcolor=HIGHLIGHT,
            darkcolor=HIGHLIGHT, selectbackground=HIGHLIGHT, selectforeground=ACCENT,
            font=("Segoe UI", 10, "bold"), padding=4
        )
        self._ttk_style.map(
            "Kairox.TCombobox",
            fieldbackground=[("readonly", HIGHLIGHT)],
            foreground=[("readonly", TEXT_WHITE)],
            selectbackground=[("readonly", HIGHLIGHT)],
            selectforeground=[("readonly", ACCENT)],
        )
        self.root.option_add("*TCombobox*Listbox*font", "{Helvetica} 10")
        self.root.option_add("*TCombobox*Listbox*background", HIGHLIGHT)
        self.root.option_add("*TCombobox*Listbox*foreground", TEXT_WHITE)
        self.root.option_add("*TCombobox*Listbox*selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")
        self.root.option_add("*TCombobox*Listbox*borderwidth", 1)

    def _on_ai_change(self, _e=None):
        """Actualiza el subtítulo y avisa del modo de IA elegido"""
        mode = self.ai_mode.get()
        names = {"Automático": "Kairox · Gemini primero, respaldo con opencode",
                 "Gemini": "Kairox con Gemini · Acceso a toda la web",
                 "opencode": "Kairox con opencode · Respuestas locales"}
        self.subtitle_label.configure(text=names.get(mode, names["Automático"]))
        self.add_message("Sistema", f"🤖 Modo de IA: {mode}")

        # Actualizar lista de modelos según el proveedor seleccionado
        from config import AVAILABLE_MODELS
        prov_map = {"Gemini": "gemini", "opencode": "openai", "Automático": _CONFIG.get("provider", "gemini")}
        prov = prov_map.get(mode, "gemini")
        models = AVAILABLE_MODELS.get(prov, [])
        self.model_selector.configure(values=models)
        if models and self.model_selector_var.get() not in models:
            self.model_selector_var.set(models[0])
            self._on_model_change()

    def _on_model_change(self, _e=None):
        """Guarda el modelo seleccionado en config.json y reconecta el cerebro"""
        from config import save_config as _save_cfg
        new_model = self.model_selector_var.get()
        _CONFIG["model"] = new_model
        _save_cfg(_CONFIG)
        # Reconectar el cerebro con el nuevo modelo
        try:
            self.brain.model_name = new_model
        except Exception:
            pass
        self.add_message("Sistema", f"🧠 Modelo de pensamiento: {new_model}")
        
    def _recolor_ui(self):
        """Reaplica todos los colores con el tema activo"""
        self.root.configure(bg=BG_ROOT)
        # Frames de fondo raíz
        for w in self._frame_root_list:
            w.configure(bg=BG_ROOT)
            if isinstance(w, tk.Canvas):
                w.configure(bg=BG_ROOT, highlightbackground=BG_ROOT)
        # Frames de acento
        for w in self._frame_frame_list:
            w.configure(bg=BG_FRAME)
        if hasattr(self, 'chat_frame'):
            self.chat_frame.configure(highlightbackground=HIGHLIGHT)
        if hasattr(self, 'chat_border'):
            self.chat_border.configure(bg=HIGHLIGHT)
        if hasattr(self, 'quick_frame'):
            self.quick_frame.configure(highlightbackground=HIGHLIGHT)
        if hasattr(self, 'sidebar_canvas'):
            self.sidebar_canvas.configure(bg=BG_FRAME, highlightbackground=BG_FRAME)
        if hasattr(self, 'sidebar_content'):
            self.sidebar_content.configure(bg=BG_FRAME)
        if hasattr(self, '_sidebar_scrollbar'):
            self._sidebar_scrollbar.configure(
                bg=HIGHLIGHT, troughcolor=BG_FRAME, activebackground=ACCENT,
                highlightbackground=BG_FRAME)
        # Etiquetas
        for w in self._label_root_list:
            w.configure(bg=BG_ROOT)
        for w in self._label_frame_list:
            w.configure(bg=BG_FRAME)
        if hasattr(self, 'title_label'):
            self.title_label.configure(fg=ACCENT)
        if hasattr(self, 'beta_badge'):
            self.beta_badge.configure(bg=ACCENT, fg=self._beta_badge_fg())
        if hasattr(self, 'quick_label'):
            self.quick_label.configure(fg=ACCENT)
        # Chat
        if hasattr(self, 'chat_display'):
            self.chat_display.configure(bg=BG_CHAT, fg=TEXT_WHITE, insertbackground=ACCENT,
                                        selectbackground=ACCENT_PURPLE)
            self.chat_display.tag_configure('user', foreground=ACCENT_GREEN)
            self.chat_display.tag_configure('assistant', foreground=ACCENT)
            self.chat_display.tag_configure('system', foreground=TEXT_GRAY)
            self.chat_display.tag_configure('error', foreground=ACCENT_RED)
            self.chat_display.tag_configure('code', foreground=ACCENT_GREEN)
            self.chat_display.tag_configure('code_label', foreground=TEXT_GRAY)
            self.chat_display.tag_configure('sender', foreground=ACCENT)
        if hasattr(self, 'chat_scrollbar'):
            self.chat_scrollbar.configure(
                bg=HIGHLIGHT, troughcolor=BG_CHAT, activebackground=ACCENT,
                highlightbackground=HIGHLIGHT)
        # Barra de escritura
        if hasattr(self, 'text_input'):
            self.text_input.configure(bg=HIGHLIGHT, fg=TEXT_GRAY, insertbackground=ACCENT,
                                      highlightbackground=HIGHLIGHT, highlightcolor=ACCENT)
        # Barra de estado (canvas)
        if hasattr(self, 'status_canvas'):
            self.status_canvas.configure(bg=BG_FRAME)
            self.status_canvas.itemconfigure(self.status_text, fill=TEXT_WHITE)
            self.status_canvas.itemconfigure(self.volume_display, fill=ACCENT_GREEN)
            self.status_canvas.itemconfigure(self.gemini_indicator,
                fill=ACCENT_GREEN if self.brain_available else ACCENT_RED)
            self.status_canvas.itemconfigure(self.led, fill=BTN_INACTIVE)
        # Botones rápidos
        for btn in self._quick_buttons:
            btn.bg_color = BTN_INACTIVE
            btn.text_color = TEXT_WHITE
            btn.configure(bg=BG_ROOT)
            btn.draw()
        # Botones de control manuales (rojo/perúrpura fijos dependen del tema)
        if hasattr(self, 'listen_button'):
            self.listen_button.bg_color = ACCENT_GREEN
            self.listen_button.text_color = BG_ROOT
            self.listen_button.configure(bg=BG_ROOT)
            self.listen_button.draw()
        if hasattr(self, 'stop_button'):
            self.stop_button.bg_color = ACCENT_RED
            self.stop_button.configure(bg=BG_ROOT)
            self.stop_button.draw()
        if hasattr(self, 'clear_button'):
            self.clear_button.bg_color = ACCENT_PURPLE
            self.clear_button.configure(bg=BG_ROOT)
            self.clear_button.draw()
        if hasattr(self, 'attach_button'):
            self.attach_button.bg_color = ACCENT_PURPLE
            self.attach_button.configure(bg=BG_ROOT)
            self.attach_button.draw()
        if hasattr(self, 'detach_button'):
            self.detach_button.bg_color = ACCENT_RED
            self.detach_button.configure(bg=BG_ROOT)
            self.detach_button.draw()
        if hasattr(self, 'send_button'):
            self.send_button.bg_color = ACCENT
            self.send_button.configure(bg=BG_ROOT)
            self.send_button.draw()
        if hasattr(self, 'theme_button'):
            self.theme_button.bg_color = ACCENT
            self.theme_button.configure(bg=BG_ROOT)
            self.theme_button.draw()
        # Desplegable de IA (colores del tema)
        if hasattr(self, 'ai_selector'):
            self._style_combobox()
        # Botón micrófono: el fondo del canvas también sigue al tema
        if hasattr(self, 'mic_button'):
            self.mic_button.configure(bg=BG_ROOT)
            if self.mic_button.is_active:
                self.mic_button.draw_active(0)
            else:
                self.mic_button.draw_idle()
        # Subtítulo del micrófono y transcripción en vivo
        if hasattr(self, 'mic_status_label'):
            self.mic_status_label.configure(fg=TEXT_GRAY)
        if hasattr(self, 'live_transcript_label'):
            self.live_transcript_label.configure(fg=ACCENT_GREEN)
        # Texto de los botones de color: blanco sobre acentos oscuros,
        # fondo sobre acentos claros (temas tipo "Blanco Limpio")
        text_on_accent = BG_ROOT if _is_light_theme() else '#ffffff'
        for btn in [self.theme_button, self.stop_button, self.clear_button,
                    self.attach_button, self.detach_button, self.send_button,
                    self.minimize_button]:
            btn.text_color = text_on_accent
            btn.configure(bg=BG_ROOT)
            btn.draw()
        # Recolorear el widget flotante mini si está activo
        if hasattr(self, 'mini_win') and self.mini_win.winfo_exists():
            try:
                self.mini_win.configure(bg=BG_FRAME)
                self.mini_bg.configure(bg=BG_FRAME, highlightbackground=HIGHLIGHT)
                if hasattr(self, 'mini_mic_button'):
                    self.mini_mic_button.configure(bg=BG_FRAME)
                    if self.mini_mic_button.is_active:
                        self.mini_mic_button.draw_active(0)
                    else:
                        self.mini_mic_button.draw_idle()
                if hasattr(self, 'mini_status'):
                    self.mini_status.configure(
                        bg=BG_FRAME,
                        fg=ACCENT_GREEN if self.is_listening else TEXT_GRAY)
                if hasattr(self, 'mini_live_label'):
                    self.mini_live_label.configure(bg=BG_FRAME, fg=ACCENT_GREEN)
                for w in [self.mini_send_button, self.mini_restore_button]:
                    try:
                        w.configure(bg=BG_FRAME)
                        if isinstance(w, MaximizeButton):
                            w.bg_color = ACCENT
                            w.icon_color = '#ffffff' if not _is_light_theme() else BG_ROOT
                        w.draw()
                    except Exception:
                        w.draw()
                self.mini_text_input.configure(
                    bg=HIGHLIGHT, fg=TEXT_WHITE, insertbackground=ACCENT,
                    highlightbackground=HIGHLIGHT, highlightcolor=ACCENT)
                if hasattr(self, 'mini_chat_display'):
                    self.mini_chat_display.configure(
                        bg=BG_ROOT, fg=TEXT_WHITE, highlightbackground=HIGHLIGHT)
                    self.mini_chat_display.tag_configure(
                        'mini_user', foreground=ACCENT_GREEN)
                    self.mini_chat_display.tag_configure(
                        'mini_assistant', foreground=ACCENT)
                    self.mini_chat_display.tag_configure(
                        'mini_system', foreground=TEXT_GRAY)
                    self.mini_chat_display.tag_configure(
                        'mini_error', foreground=ACCENT_RED)
            except Exception:
                pass
        
    def set_status_lamp(self, listening):
        """Configura color del LED de estado"""
        if hasattr(self, 'status_canvas'):
            color = ACCENT_GREEN if listening else BTN_INACTIVE
            self.status_canvas.itemconfigure(self.led, fill=color)
            
    def set_status_text(self, text, color=None):
        """Configura texto de estado"""
        if hasattr(self, 'status_canvas'):
            self.status_canvas.itemconfigure(self.status_text, text=text)
            if color:
                self.status_canvas.itemconfigure(self.status_text, fill=color)
                
    def add_message(self, sender, message):
        """Añade un mensaje al área de chat"""
        self.chat_display.configure(state=tk.NORMAL)
        
        if sender == "Tú":
            tag = 'user'
            prefix = "🎤 "
        elif sender == "Asistente":
            tag = 'assistant'
            prefix = "⚡ "            
        elif sender == "Kairox":
            tag = 'assistant'
            prefix = "⚡ "
        elif sender == "Error":
            tag = 'error'
            prefix = "⚠️ "
        else:
            tag = 'system'
            prefix = ""
            
        timestamp = datetime.now().strftime("%H:%M")
        self.chat_display.insert(tk.END, f"\n{prefix}{sender} [{timestamp}]\n{message}\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.configure(state=tk.DISABLED)

        if getattr(self, 'is_minimized', False) and hasattr(self, 'mini_chat_display'):
            self._append_mini_chat(sender, message)

    def _append_mini_chat(self, sender, message):
        """Añade el mensaje también al chat del widget flotante"""
        try:
            disp = self.mini_chat_display
            disp.configure(state=tk.NORMAL)
            if sender == "Tú":
                disp.insert(tk.END, f"🎤 {message}\n", 'mini_user')
            elif sender in ("Asistente", "Kairox"):
                disp.insert(tk.END, f"⚡ {message}\n", 'mini_assistant')
            elif sender == "Error":
                disp.insert(tk.END, f"⚠️ {message}\n", 'mini_error')
            else:
                disp.insert(tk.END, f"{message}\n", 'mini_system')
            disp.see(tk.END)
            disp.configure(state=tk.DISABLED)
        except Exception:
            pass
        
    def clear_chat(self):
        """Limpia el área de chat"""
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        self.add_message("Sistema", "Chat limpiado")
        
    def attach_file(self):
        """Abre un diálogo para adjuntar un archivo o imagen"""
        path = filedialog.askopenfilename(
            title="Selecciona un archivo o imagen para Kairox",
            filetypes=[
                ("Imágenes", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"),
                ("Documentos", "*.txt *.md *.csv *.json *.pdf *.docx"),
                ("Audio", "*.wav *.mp3 *.ogg"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if path:
            self.attached_path = path
            name = os.path.basename(path)
            self.attached_label.configure(text=f"📎 Adjunto: {name}", fg=ACCENT_GREEN)
            self.add_message("Sistema", f"📎 Archivo adjuntado: {name}")
            
    def detach_file(self):
        """Quita el archivo adjunto"""
        self.attached_path = None
        self.attached_label.configure(text="📎 Sin archivo adjunto", fg=TEXT_GRAY)
        self.add_message("Sistema", "Archivo adjunto eliminado")
        
    def speak(self, text, read_text=None):
        """Convierte texto a voz (si se indica read_text, se lee ese resumen corto)"""
        self.add_message("Kairox", text)
        self.tts_engine.speak(read_text if read_text is not None else text, async_mode=True)
        
    def toggle_listening(self):
        """Alterna el estado de escucha"""
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()
            
    def start_listening(self):
        """Inicia la escucha"""
        self.tts_engine.stop()
        self.pending_text = []
        self._vad_rejected = False
        self.is_listening = True
        self.listen_button.set_text("🎤 Escuchando...")
        self.listen_button.bg_color = ACCENT_RED
        self.listen_button.text_color = '#ffffff'
        self.listen_button.draw()
        self.mic_button.set_active(True)
        self.mic_status_label.configure(text="🎤 Escuchando... Habla y luego pulsa Detener", fg=ACCENT_GREEN)
        self.live_transcript_label.configure(text="", fg=ACCENT_GREEN)
        if hasattr(self, 'mini_mic_button'):
            try:
                self.mini_mic_button.set_active(True)
                self.mini_status.configure(text="● Escuchando...", fg=ACCENT_GREEN)
                self.mini_live_label.configure(text="")
            except Exception:
                pass
        self.set_status_lamp(True)
        self.set_status_text("Estado: Escuchando...", ACCENT_GREEN)
        self.add_message("Sistema", "Escuchando... habla, cuando termines pulsa ⏹ Detener")
        self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listen_thread.start()
        
    def stop_listening(self):
        """Detiene la escucha y procesa todo lo que dijo"""
        self.is_listening = False
        self.listen_thread = None
        self.tts_engine.stop()
        self.listen_button.set_text("🎤 Escuchar")
        self.listen_button.bg_color = ACCENT_GREEN
        self.listen_button.text_color = BG_ROOT
        self.listen_button.draw()
        self.mic_button.set_active(False)
        self.mic_status_label.configure(text="Haz clic en el micrófono para hablar", fg=TEXT_GRAY)
        self.live_transcript_label.configure(text="", fg=ACCENT_GREEN)
        if hasattr(self, 'mini_mic_button'):
            try:
                self.mini_mic_button.set_active(False)
                self.mini_status.configure(text="Haz clic en el micrófono", fg=TEXT_GRAY)
                self.mini_live_label.configure(text="")
            except Exception:
                pass
        self.set_status_lamp(False)
        self.set_status_text("Estado: Procesando...", "#ffb454")
        
        self._finish_listen_pending()
    
    def _finish_listen_pending(self):
        """Espera a que el hilo de escucha termine el VAD + transcripción
        (que tarda en llamar a Google) y luego procesa lo que se captó.
        Sin esto, stop_listening() lee pending_text antes de que exista."""
        thread = getattr(self, 'listen_thread', None)
        if thread is None or not thread.is_alive():
            # El hilo ya terminó: procesar directamente
            self._process_pending_text()
            return
        # El hilo aún procesa: reintentar cuando termine
        self.root.after(80, self._finish_listen_pending)
    
    def _process_pending_text(self):
        if self.pending_text:
            # Unir todo lo que dijo en una sola frase
            full_text = ' '.join(self.pending_text).strip()
            self.pending_text = []
            if full_text:
                self.add_message("Tú", full_text)
                self.process_command(full_text)
                self.set_status_text("Estado: Listo", TEXT_WHITE)
                return
        if not getattr(self, '_vad_rejected', False):
            self.add_message("Sistema", "No se detectó ninguna palabra.")
        self._vad_rejected = False
        self.set_status_text("Estado: Listo", TEXT_WHITE)
        
    def _whisper_transcribe(self, audio_full):
        """Transcribe con Whisper local (faster-whisper) — mucho más preciso en
        español que Google. Se carga bajo demanda la primera vez."""
        try:
            if self._whisper_model is None:
                imported = __import__("faster_whisper")
                WhisperModel = imported.WhisperModel
                self._whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
            wav_data = audio_full.get_wav_data(convert_rate=16000, convert_width=2)
            import io, wave
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(wav_data)
            buf.seek(0)
            segments, _ = self._whisper_model.transcribe(
                buf, language="es", beam_size=5, vad_filter=True)
            text = "".join(s.text for s in segments).strip()
            return text or None
        except Exception:
            return None

    def _spectral_denoise(self, samples):
        """Reduce el ruido de fondo espectral (FFT): estima el piso de ruido
        con las tramas de menor energía y atenua esas frecuencias."""
        try:
            n = len(samples)
            if n < 1024:
                return None
            win = np.hanning(2048)
            step = 512
            spec = {}
            nframes = 0
            i = 0
            while i + 2048 <= n:
                seg = samples[i:i + 2048] * win
                mag = np.abs(np.fft.rfft(seg))
                for k, v in enumerate(mag):
                    spec.setdefault(k, []).append(v)
                nframes += 1
                i += step
            if nframes < 4:
                return None
            noise = np.zeros(len(spec))
            for k in spec:
                arr = np.sort(np.array(spec[k]))
                noise[k] = arr[max(0, int(len(arr) * 0.1)) - 1]
            out = np.zeros(n)
            wsum = np.zeros(n)
            i = 0
            while i + 2048 <= n:
                seg = samples[i:i + 2048]
                X = np.fft.rfft(seg * win)
                mag = np.abs(X)
                gain = np.where(mag > noise * 1.6, 1.0, 0.35)
                Y = X * gain
                out[i:i + 2048] += np.fft.irfft(Y, 2048) * win
                wsum[i:i + 2048] += win
                i += step
            mask = wsum > 1e-6
            out[mask] /= wsum[mask]
            return out
        except Exception:
            return None

    def listen_loop(self):
        """Escucha en STREAMING CONTINUO: muestra en tiempo real lo que va
        entendiendo (Vosk) y guarda el audio; al soltar Detener se transcribe
        con precisión (Google) y se procesa."""
        buffer_chunks = bytearray()
        last_phrase = ""
        chunk = None
        try:
            with self.microphone as source:
                # Calibrar al ruido ambiente
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                self.recognizer.dynamic_energy_threshold = False
                self.recognizer.energy_threshold = max(
                    300, int(self.recognizer.energy_threshold * 1.0))
                if self.rec:
                    try:
                        self.rec.Reset()
                    except Exception:
                        pass
                while self.is_listening:
                    try:
                        chunk = source.stream.read(source.CHUNK)
                    except (EOFError, IOError):
                        break
                    buffer_chunks += chunk
                    # Recortar el buffer a ~40s útiles
                    max_bytes = self.sample_rate * 2 * 40
                    if len(buffer_chunks) > max_bytes:
                        del buffer_chunks[:len(buffer_chunks) - max_bytes]
                    
                    # VAD por chunk: Vosk SOLO ve audio que supere el umbral de
                    # energía calibrado (voz real), así no alucina palabras con
                    # el ruido de fondo ni con la propia voz del asistente.
                    chunk_rms = audioop.rms(chunk, 2)
                    speech_chunk = chunk_rms > max(
                        float(self.recognizer.energy_threshold), 300.0)
                    
                    # Feedback en vivo con Vosk (instantáneo y local)
                    if self.rec:
                        try:
                            if speech_chunk:
                                result = self.rec.AcceptWaveform(bytes(chunk))
                            else:
                                result = self.rec.AcceptWaveform(
                                    b'\x00\x00' * (len(chunk) // 2))
                            if result:
                                res = json.loads(self.rec.Result())
                                phrase = res.get("text", "").strip()
                                if phrase and phrase != last_phrase:
                                    last_phrase = phrase
                                    self._update_live(phrase, is_final=True)
                            else:
                                pres = json.loads(self.rec.PartialResult())
                                partial = pres.get("partial", "").strip()
                                if partial:
                                    self._update_live(partial, is_final=False)
                        except Exception:
                            pass
        except sr.WaitTimeoutError:
            pass
        except Exception as e:
            self.root.after(0, lambda: self.add_message("Error", str(e)))
        
        # Al detener: transcripción precisa de TODO el audio acumulado
        if not buffer_chunks:
            return

        samples = np.frombuffer(bytes(buffer_chunks), dtype=np.int16).astype(np.float32)
        # Quitar el offset DC que suele enmascarar la voz
        samples = samples - samples.mean()

        # VAD basado en el umbral de energía ya calibrado por
        # speech_recognition (adjust_for_ambient_noise lo fija a ~1.5x el ruido
        # ambiente). Replicamos su fórmula probada: un frame es "voz" si su RMS
        # supera el umbral. Esto rechaza ruido de fondo / eco / música y en
        # cambio NUNCA rechaza voz real (que siempre está muy por encima).
        rms = float(np.sqrt(np.mean(samples ** 2)))
        frame = int(self.sample_rate * 30 / 1000)  # 30 ms
        n_frames = len(samples) // frame
        vad_passed = False
        speech_seg = None
        if n_frames >= 5:
            frames = samples[:n_frames * frame].reshape(n_frames, frame)
            frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))
            calib = max(float(self.recognizer.energy_threshold), 300.0)
            floor_est = max(float(np.percentile(frame_rms, 25)) * 2.0, 150.0)
            # Umbral de voz: el menor entre el nivel calibrado en silencio y el
            # ruido estimado en la propia grabación (ser mas permisivo evita
            # rechazar voz real que solo supera el umbral por poco).
            base = min(calib, floor_est)
            n_active = int((frame_rms > base).sum())
            vad_passed = bool(frame_rms.max() > base and n_active >= 2)
            # Recortar al segmento de voz real: recoger tramas claramente por
            # encima del ruido (max(base*1.4, floor_est)) y expandir un poco,
            # para mandarle a Google solo la frase sin silencios iniciales/finales.
            if vad_passed:
                seg_thr = max(base * 1.4, floor_est)
                act = frame_rms > seg_thr
                idx = np.where(act)[0]
                words = []
                if len(idx):
                    w0 = idx[0]
                    for i in range(1, len(idx)):
                        if idx[i] > idx[i-1] + 12:  # hueco >360ms
                            words.append((w0, idx[i-1]))
                            w0 = idx[i]
                    words.append((w0, idx[-1]))
                    a = max(0, words[0][0] - 12)
                    b = min(n_frames, words[-1][1] + 12)
                    seg = samples[a * frame:(b + 1) * frame]
                    if len(seg) > 0:
                        pk = max(float(abs(seg).max()), 1.0)
                        seg = seg * (0.7 * 32767 / pk)
                        speech_seg = seg
                    elif rms > 300:
                        pk = max(rms, 1.0)
                        speech_seg = samples * (0.7 * 32767 / (pk * 3))
        else:
            vad_passed = bool(rms > 300)

        audio_full = None
        if vad_passed:
            try:
                src = speech_seg if (speech_seg is not None and len(speech_seg) > 0) else samples
                # Reducción espectral de ruido: estimar el piso de ruido con las
                # tramas menos energéticas del buffer y atenuar esas frecuencias
                # (FAQ ruido/aire/música de fondo que ensucia la transcripción).
                try:
                    clean = self._spectral_denoise(src)
                    if clean is not None:
                        src = clean
                except Exception:
                    pass
                boosted = np.clip(src, -32767, 32767).astype(np.int16)
                audio_full = sr.AudioData(boosted.tobytes(), self.sample_rate, 2)
            except Exception:
                audio_full = None
        
        text = ""
        if audio_full:
            # Google es el motor principal: frase limpia y precisa.
            try:
                text = self.recognizer.recognize_google(audio_full, language='es-ES')
            except sr.UnknownValueError:
                text = ""
            except sr.RequestError:
                text = ""
            # Whisper local como respaldo: solo si Google no oyó nada, porque
            # consultarlo siempre añade latencia y en audio con ruido puede
            # empeorar palabras que Google sí reconoce (ej. "bad bunny").
            if not text:
                try:
                    text = self._whisper_transcribe(audio_full) or ""
                except Exception:
                    text = ""
            # Gemini como refuerzo final (solo si todos fallaron)
            if not text:
                try:
                    wav_data = audio_full.get_wav_data(convert_rate=16000, convert_width=2)
                    if wav_data and self.brain and self.brain_available:
                        text = self.brain.transcribe_audio(wav_data) or ""
                except Exception:
                    text = ""
        
        # Fallback: lo que captó Vosk en directo (solo si el VAD confirmó voz)
        if not text and last_phrase and vad_passed:
            text = last_phrase
        
        if text and text.strip() and audio_full:
            text = text.strip()
            self.pending_text = [text]
            self.root.after(0, lambda: self.set_status_text(
                f"🗣 Captado: {text[:40]}...", ACCENT_GREEN))
        elif not vad_passed:
            self._vad_rejected = True
            print(f"[VAD] rechazo: rms={rms:.0f} peak={frame_rms.max() if n_frames>=5 else rms:.0f} "
                  f"calib={calib:.0f} base={base:.0f} active={n_active}",
                  file=sys.stderr)
            if rms < 80:
                msg = "No escuché nada. Revisa el nivel del micrófono."
            else:
                msg = "No escuché ninguna palabra clara. Habla más fuerte o acércate al micrófono."
            self.root.after(0, lambda: self.add_message("Sistema", msg))
    
    def _update_live(self, text, is_final):
        """Actualiza el indicador de transcripción EN VIVO"""
        def _apply():
            displayed = text if is_final else f"… {text}…"
            self.live_transcript_label.configure(
                text=f"🎙️ {displayed}",
                fg=ACCENT_GREEN if is_final else ACCENT)
            if hasattr(self, 'mini_live_label'):
                try:
                    self.mini_live_label.configure(
                        text=f"🎙️ {displayed}",
                        fg=ACCENT_GREEN if is_final else ACCENT)
                except Exception:
                    pass
        self.root.after(0, _apply)
                
    def _open_browser(self, url):
        """Abre la URL en el navegador por defecto (Firefox/Chrome) sin bloquear"""
        try:
            if sys.platform.startswith('linux'):
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            else:
                import webbrowser
                webbrowser.open(url)
        except Exception as e:
            print(f"[browser] error abriendo {url}: {e}", file=sys.stderr)

    def process_command(self, command):
        """Procesa comandos, aprende hechos y usa memoria para respuestas"""
        # Guardar en memoria
        self.memory.add_message('user', command)
        
        # Aprender hechos del usuario
        facts_learned = self.memory.learn_from_text(command)
        if facts_learned:
            for k, v in facts_learned:
                self.root.after(0, lambda: self.add_message("Aprendizaje",
                    f"He aprendido algo de ti: {k} = {v}"))
        
        command_lower = command.lower()
        
        # Comandos locales rápidos (no requieren internet)
        if any(word in command_lower for word in ["hora", "qué hora es"]):
            now = datetime.now()
            response = f"Son las {now.strftime('%H:%M')}"
        elif any(word in command_lower for word in ["fecha", "qué día es"]):
            now = datetime.now()
            response = f"Hoy es {now.strftime('%d/%m/%Y')}"
        elif any(word in command_lower for word in ["qué sabes de mí", "qué sabes de mi", "cuéntame sobre mí"]):
            facts = self.memory.learned_facts_string()
            if facts:
                response = f"Esto es lo que he aprendido sobre ti: {facts}"
            else:
                response = "Todavía no he aprendido nada sobre ti. ¡Cuéntame algo de ti!"
        elif any(word in command_lower for word in ["memoria", "qué recuerdas", "aprendizaje"]):
            response = self.memory.stats()
        elif any(word in command_lower for word in ["pseudocódigo", "pseudocodigo", "pseudo código", "pseudo codigo", "pseudocodico"]):
            self.root.after(0, lambda: self.add_message("Sistema", "Generando pseudocódigo..."))
            threading.Thread(target=self._generate_code, args=(command, "pseudo"), daemon=True).start()
            return
        elif any(word in command_lower for word in ["genera código", "genera codigo", "escribe código", "escribe codigo", "haz un código", "haz el código", "código para", "codigo para", "escribeme", "hazme un código", "hazme codigo", "crea un programa", "hacer código", "hacer codigo", "programa en"]):
            self.root.after(0, lambda: self.add_message("Sistema", "Generando código..."))
            threading.Thread(target=self._generate_code, args=(command, "code"), daemon=True).start()
            return
        elif any(word in command_lower for word in ["adjuntar", "adjunta un archivo", "adjunto un archivo", "adjunto", "adjuntar archivo", "adjunta una imagen"]):
            self.attach_file()
            response = "Selecciona el archivo que quieres adjuntar en la ventana que aparece."
        elif any(word in command_lower for word in ["analiza", "analiza la imagen", "analiza el archivo", "analiza el documento", "describe la imagen", "describe el archivo", "qué dice este", "que dice este"]):
            if self.attached_path:
                name = os.path.basename(self.attached_path)
                self.root.after(0, lambda: self.speak(f"Analizando {name}. Un momento..."))
                threading.Thread(target=self._gemini_reply, args=(command,), daemon=True).start()
                return
            else:
                response = "No tengo ningún archivo adjunto. Pulsa el botón 📎 Adjuntar para elegir uno, y luego dime analiza otro."
        elif any(word in command_lower for word in ["crea una carpeta", "haz una carpeta", "nueva carpeta", "crear carpeta", "crea un directorio", "crea un documento", "haz un documento", "crea un archivo", "crear documento", "crear archivo", "crea un texto", "crea una nota", "crea un apunte", "documento llamado", "archivo llamado", "carpeta llamada"]):
            path, response = handle_file_command(command)
            if path:
                self.memory.add_message('assistant', response)
                response = f"{response}. Lo guardé en {path}"
        elif any(word in command_lower for word in ["cambia el tema", "cambia de tema", "cambiar tema", "paleta", "apariencia", "cambia la apariencia"]):
            nxt = next_theme(CURRENT_THEME['name'])
            response = f"Cambié al tema {nxt}"
            self.root.after(0, self.cycle_theme)
        elif any(word in command_lower for word in ["adiós", "hasta luego", "chao", "salir"]):
            response = "¡Hasta luego! Que tengas un buen día."
            self.root.after(0, lambda: self.speak(response))
            self.root.after(100, self.stop_listening)
            return
        elif any(word in command_lower for word in ["nombre", "cómo te llamas", "quién eres"]):
            response = "Soy Kairox, tu asistente con inteligencia Gemini que aprende de ti y tiene acceso a toda la web."
        elif any(word in command_lower for word in ["ayuda", "qué puedes hacer"]):
            response = """Soy Kairox, puedo ayudarte con:
• Responder preguntas usando Gemini + web
• Analizar imágenes y documentos adjuntos
• Crear carpetas y documentos donde quieras
• Aprender de ti y recordar lo que hablamos
• Música con Spotify y hora y fecha
Pregúntame lo que quieras en español."""
        elif any(word in command_lower for word in ["sin gemini", "modo offline"]):
            response = "Cambié a modo local básico."
            self.brain_available = False
        elif command_lower.startswith("busca en ") or command_lower.startswith("buscar en "):
            # Búsqueda web: "busca en google ..." / "busca en firefox ..." / "busca en youtube ..."
            query = command_lower[len("busca en "):].strip() if command_lower.startswith("busca en ") else command_lower[len("buscar en "):].strip()
            engine = None
            if query.startswith("google"):
                engine = "https://www.google.com/search?q="
                query = query[len("google"):].strip()
            elif query.startswith("google chrome") or query.startswith("chrome"):
                engine = "https://www.google.com/search?q="
                query = query[len("google chrome"):].strip() if query.startswith("google chrome") else query[len("chrome"):].strip()
            elif query.startswith("youtube"):
                engine = "https://www.youtube.com/results?search_query="
                query = query[len("youtube"):].strip()
            elif query.startswith("bing"):
                engine = "https://www.bing.com/search?q="
                query = query[len("bing"):].strip()
            elif query.startswith("duckduckgo"):
                engine = "https://duckduckgo.com/?q="
                query = query[len("duckduckgo"):].strip()
            elif query.startswith("wikipedia"):
                engine = "https://es.wikipedia.org/w/index.php?search="
                query = query[len("wikipedia"):].strip()
            elif query.startswith("firefox"):
                engine = "https://www.google.com/search?q="
                query = query[len("firefox"):].strip()
            if not engine:
                response = "Puedes decirme: busca en google <lo que quieras>, busca en youtube <video>, busca en bing, duckduckgo o wikipedia."
            else:
                query = query.strip(" ,.-_")
                if not query:
                    response = "¿Qué quieres que busque? Por ejemplo: busca en google recetas de cocina."
                else:
                    from urllib.parse import quote
                    url = engine + quote(query)
                    self.root.after(0, lambda: self._open_browser(url))
                    response = f"Busco {query} en tu navegador."
        elif is_music_command(command):
            # Control de Spotify con la voz
            music_response, _action = handle_music_command(command)
            if music_response:
                response = music_response
            else:
                response = "Puedes decirme: pon música, pausa, siguiente canción, sube o baja el volumen, o por ejemplo \"pon Bad Bunny en Spotify\" para buscar una canción."
        else:
            # Intentar recordar respuesta aprendida primero
            recalled, score = self.memory.recall_answer(command)
            if recalled and score > 0.75:
                response = f"[Lo recuerdo] {recalled}"
            elif self.brain_available or self.ai_mode.get() == "opencode":
                # Añadir contexto de memoria a la IA elegida (Gemini u opencode)
                self.root.after(0, lambda: self.speak("Un momento, estoy consultando..."))
                threading.Thread(target=self._gemini_reply, args=(command,), daemon=True).start()
                return
            else:
                response = f"Escuché: {command}. Conecta Gemini para respuestas inteligentes."
            
        self.root.after(0, lambda: self.speak(response))
        
    def _gemini_reply(self, text):
        """Obtiene respuesta de la IA (Gemini u opencode según el selector) con contexto de memoria"""
        mode = self.ai_mode.get()
        brain_name = "opencode" if mode == "opencode" else "Gemini"
        try:
            self.root.after(0, lambda: self.set_status_text(f"🧠 Consultando {brain_name}...", ACCENT))
            
            # Incluir contexto de memoria y hechos en la petición
            context = self.memory.get_last_context(n=8)
            facts = self.memory.learned_facts_string()
            
            prompt_with_context = text
            if context:
                prompt_with_context = f"CONVERSACIÓN PREVIA:\n{context}\n\n"
            if facts:
                prompt_with_context += f"DATOS DEL USUARIO: {facts}\n\n"
            prompt_with_context += f"PREGUNTA ACTUAL: {text}"
            
            if mode == "opencode":
                # opencode como único cerebro (también con archivo adjunto, si puede leerlo)
                response = self.brain.ask_opencode_from_pc(prompt_with_context)
            elif self.attached_path:
                response = self.brain.ask_with_file(prompt_with_context, self.attached_path)
            else:
                LONG_HINT = ["ensayo", "parrafo", "párrafo", "texto largo", "extensa",
                             "extenso", "detallada", "detallado", "muy largo", "muy larga",
                             "redaccion", "redacción", "articulo", "artículo", "carta",
                             "explica a fondo", "a fondo", "mucho texto", "resumen largo",
                             "narra", "historia", "cuento", "libro", "capitulo", "capítulo",
                             "con todo detalle", "en detalle"]
                long_req = any(h in text.lower() for h in LONG_HINT)
                response = self.brain.ask(
                    prompt_with_context, use_web=not long_req,
                    max_tokens=6000 if long_req else 3000, retries=5)
                # Si Gemini falla y el modo es Automático, preguntar a opencode
                if (mode == "Automático" and self.brain.is_error_response(response)):
                    self.root.after(0, lambda: self.set_status_text("🤖 Consultando opencode...", ACCENT))
                    fallback = self.brain.ask_opencode_from_pc(prompt_with_context)
                    if fallback:
                        response = fallback
            if response and self.brain.is_error_response(response):
                response = None
            if response:
                self.memory.add_message('assistant', response)
                self.memory.learn_answer(text, response)
                if len(response) > 900:
                    head = " ".join(response.split()[:70])
                    short = f"Aquí tienes el texto completo en el chat. Empezaba así: {head}..."
                    self.root.after(0, lambda: self.speak(response, read_text=short))
                else:
                    self.root.after(0, lambda: self.speak(response))
            else:
                self.root.after(0, lambda: self.speak(
                    f"Perdona, no puedo contactar con {brain_name} ahora mismo. Intenta de nuevo."))
            self.root.after(0, lambda: self.set_status_text("Estado: Listo", TEXT_WHITE))
        except Exception as e:
            self.root.after(0, lambda: self.speak(
                f"Lo siento, tuve problemas con {brain_name}. ¿Probamos de nuevo?"))
            self.root.after(0, lambda: self.set_status_text("Estado: Listo", TEXT_WHITE))
            
    def _generate_code(self, text, kind="code"):
        """Genera código o pseudocódigo con la IA elegida y lo muestra en el chat"""
        label = "Código" if kind == "code" else "Pseudocódigo"
        brain_name = "opencode" if self.ai_mode.get() == "opencode" else "Gemini"
        try:
            self.root.after(0, lambda: self.set_status_text(f"💻 Escribiendo {label} con {brain_name}...", ACCENT))
            if self.ai_mode.get() == "opencode":
                sys_p = (
                    "Eres Kairox. Genera código correcto y funcional.\n"
                    "Devuelve SOLO el código dentro de un bloque ```lenguaje ... ``` "
                    "seguido de 2 frases explicando qué hace.\n"
                    "Incluye comentarios útiles en español y usa buenas prácticas.\n"
                    "Petición del usuario:\n"
                )
                response = self.brain.ask_opencode_from_pc(sys_p + text)
            else:
                response = self.brain.generate_code(text, kind=kind)
            if response:
                self.memory.add_message('assistant', response)
                self.memory.learn_answer(text, label + " de " + (text.split("para", 1)[-1].strip() if "para" in text else text))
                self.root.after(0, lambda: self._show_code(response, label))
                self.root.after(0, lambda: self.speak(
                    f"He generado el {label.lower()} con {brain_name}. Revisa el chat. Si quieres, guárdalo en un archivo."))
            else:
                self.root.after(0, lambda: self.speak("No pude generar el código ahora mismo."))
            self.root.after(0, lambda: self.set_status_text("Estado: Listo", TEXT_WHITE))
        except Exception:
            self.root.after(0, lambda: self.speak("Tuve un problema generando el código. Inténtalo de nuevo."))
            
    def _show_code(self, text, label):
        """Muestra código en el chat con fuente monospace"""
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"\n💻 {label} [{datetime.now().strftime('%H:%M')}]\n", 'sender')
        self.chat_display.insert(tk.END, f"{text}\n", 'code')
        extra = ""
        if "```" in text:
            extra = "Consejo: copia el código entre los marcadores ``` si lo ves en el chat."
        self.chat_display.insert(tk.END, "\n", 'code_label')
        self.chat_display.see(tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        
    def execute_command(self, command):
        """Ejecuta un comando rápido"""
        self.add_message("Tú", command)
        self.process_command(command)
        
    def send_text_message(self):
        """Envía una petición escrita al chat (sin necesidad de hablar)"""
        text = self.text_input.get().strip()
        if not text or text == "Escribe tu petición aquí...":
            return
        self.add_message("Tú", text)
        self.process_command(text)
        self.text_input.delete(0, tk.END)
        
    def ask_code(self, kind):
        """Prepara el campo de texto para pedir código/pseudocódigo"""
        prefix = "Genera pseudocódigo para " if kind == "pseudo" else "Genera código para "
        if self.text_input.get() == "Escribe tu petición aquí...":
            self.text_input.delete(0, tk.END)
        self.text_input.insert(0, prefix)
        self.text_input.configure(fg=TEXT_WHITE)
        self.text_input.focus_set()

    def ask_search(self):
        """Pregunta al usuario dónde y qué quiere buscar, y muestra un ejemplo."""
        self.add_message("Sistema",
            "🔍 ¿Dónde quieres buscar? (google, youtube, bing, duckduckgo o wikipedia) "
            "y luego di qué quieres buscar. Ejemplo: <busca en google recetas de cocina>")
        if self.text_input.get() == "Escribe tu petición aquí...":
            self.text_input.delete(0, tk.END)
        self.text_input.insert(0, "busca en ")
        self.text_input.configure(fg=TEXT_WHITE)
        self.text_input.focus_set()

    def _clear_input_placeholder(self, _e):
        """Borra el placeholder al hacer foco"""
        if self.text_input.get() == "Escribe tu petición aquí...":
            self.text_input.delete(0, tk.END)
            self.text_input.configure(fg=TEXT_WHITE)

    def _restore_input_placeholder(self, _e):
        """Restaura el placeholder si está vacío"""
        if not self.text_input.get().strip():
            self.text_input.insert(0, "Escribe tu petición aquí...")
            self.text_input.configure(fg=TEXT_GRAY)
        
    def update_memory_stats(self):
        """Actualiza las estadísticas de memoria en la interfaz"""
        if hasattr(self, 'memory_stats_label'):
            self.memory_stats_label.configure(text=self.memory.stats())
        self.root.after(10000, self.update_memory_stats)
        
    def run(self):
        """Ejecuta la interfaz"""
        if self.brain_available:
            self.add_message("Sistema", "🟢 Kairox activado · Gemini conectado · Memoria + aprendizaje activados")
        else:
            self.add_message("Sistema", "🔴 Gemini sin conectar · Memoria activada en modo local")
        if self.memory.data['facts']:
            facts = self.memory.learned_facts_string()
            self.add_message("Sistema", f"🧠 Lo que recuerdo de ti: {facts}")
        # Presentación por voz al iniciar
        self.root.after(1000, lambda: self.speak("Kairox activado"))
        self.update_memory_stats()
        self.root.mainloop()

if __name__ == "__main__":
    app = VoiceAssistantGUI()
    app.run()