#!/usr/bin/env python3
"""
Interfaz Gráfica para Asistente de Voz IA Local - Diseño Moderno Transparente
"""

import speech_recognition as sr
import json
import sys
import os
import threading
import time
from datetime import datetime
import numpy as np
from vosk import Model, KaldiRecognizer
import tkinter as tk
from tkinter import scrolledtext, filedialog
from voice_engine import VoiceEngine
from gemini_brain import GeminiBrain
from memory import MemorySystem
from spotify_control import handle_music_command
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

class MicButton(tk.Canvas):
    """Botón de micrófono circular animado"""
    
    def __init__(self, parent, command, size=90):
        self.size = size
        super().__init__(parent, width=size, height=size, bg=BG_ROOT,
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
        # Anillos de pulso
        for i in range(3):
            ring_r = r + i * glow
            if ring_r < self.size:
                alpha_color = f'#{int(0x4e - i*0x18):02x}{int(0xcc + i*0x04):02x}{int(0xa3 - i*0x18):02x}'
                self.create_oval(cx-ring_r, cy-ring_r, cx+ring_r, cy+ring_r,
                               outline=alpha_color, width=1)
        # Círculo central brillante (color del tema, no fijo)
        self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=HIGHLIGHT, outline=ACCENT_GREEN, width=3)
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
        self.root = tk.Tk()
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
        
        # Variables
        self.is_listening = False
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 150
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.0
        mic_index = _CONFIG.get("mic_index", 4)
        try:
            self.microphone = sr.Microphone(device_index=mic_index)
        except Exception:
            self.microphone = sr.Microphone()
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
        
    def load_vosk_model(self):
        """Carga el modelo Vosk para reconocimiento offline"""
        model_path = "vosk-model-small-es-0.42"
        if not os.path.exists(model_path):
            self.add_message("Sistema", "Descargando modelo de voz...")
            os.system("wget -q https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip")
            os.system("unzip -q vosk-model-small-es-0.42.zip")
        
        try:
            self.vosk_model = Model(model_path)
            self.rec = KaldiRecognizer(self.vosk_model, 16000)
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
        
        sidebar_label = tk.Label(
            sidebar,
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
            ("📎", "Adjuntar", "Adjunta un archivo"),
            ("🧐", "Analiza", "Analiza el archivo adjunto"),
            ("👋", "Adiós", "Adiós"),
        ]
        
        for emoji, label, cmd in commands:
            if cmd is None and label == "Código":
                action = lambda: self.ask_code("code")
            elif cmd is None and label == "Pseudo":
                action = lambda: self.ask_code("pseudo")
            else:
                action = lambda c=cmd: self.execute_command(c)
            btn = RoundedButton(
                sidebar,
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
        
        subtitle_label = tk.Label(
            title_frame,
            text="Kairox con Gemini · Acceso a toda la web",
            font=("Segoe UI", 10),
            bg=BG_ROOT,
            fg=TEXT_GRAY
        )
        subtitle_label.pack(pady=(2, 0))
        self._label_root_list.append(subtitle_label)
        
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
        gemini_status = "🟢 Kairox · Gemini conectado" if self.brain_available else "🔴 Kairox · Gemini sin conectar"
        gemini_color = ACCENT_GREEN if self.brain_available else ACCENT_RED
        self.status_canvas.create_text(
            335, 20, text="|",
            fill=TEXT_GRAY, font=("Segoe UI", 11)
        )
        self.gemini_indicator = self.status_canvas.create_text(
            560, 20, text=gemini_status, anchor='e',
            fill=gemini_color, font=("Segoe UI", 9, "bold")
        )
        
        # LED de escucha
        self.led = self.status_canvas.create_oval(12, 12, 28, 28, fill=BTN_INACTIVE, outline=TEXT_GRAY)
        self.status_text = self.status_canvas.create_text(
            42, 20, text="Estado: Listo", anchor='w',
            fill=TEXT_WHITE, font=("Segoe UI", 11)
        )
        
        # Barra de volumen
        self.volume_display = self.status_canvas.create_text(
            560, 20, text="🔊 ▪▪▪", anchor='e',
            fill=ACCENT_GREEN, font=("Segoe UI", 10)
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
        chat_frame = tk.Frame(main_frame, bg=BG_FRAME, bd=1, highlightbackground=HIGHLIGHT,
                             highlightthickness=1)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        self._frame_frame_list.append(chat_frame)
        self.chat_frame = chat_frame
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
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
        self.chat_display.pack(fill=tk.BOTH, expand=True)

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
        
    def cycle_theme(self):
        """Cambia al siguiente tema de la paleta (sin anuncio de voz propio)"""
        global CURRENT_THEME
        prev = CURRENT_THEME['name']
        new_name = next_theme(prev)
        CURRENT_THEME = load_theme(new_name)
        _save_theme_name(new_name)
        self._recolor_ui()
        self.add_message("Sistema", f"🎨 Tema aplicado: {new_name}")
        
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
        if hasattr(self, 'quick_frame'):
            self.quick_frame.configure(highlightbackground=HIGHLIGHT)
        # Etiquetas
        for w in self._label_root_list:
            w.configure(bg=BG_ROOT)
        for w in self._label_frame_list:
            w.configure(bg=BG_FRAME)
        if hasattr(self, 'title_label'):
            self.title_label.configure(fg=ACCENT)
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
                    self.attach_button, self.detach_button, self.send_button]:
            btn.text_color = text_on_accent
            btn.configure(bg=BG_ROOT)
            btn.draw()
        
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
        
    def speak(self, text):
        """Convierte texto a voz"""
        self.add_message("Kairox", text)
        self.tts_engine.speak(text, async_mode=True)
        
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
        self.is_listening = True
        self.listen_button.set_text("🎤 Escuchando...")
        self.listen_button.bg_color = ACCENT_RED
        self.listen_button.text_color = '#ffffff'
        self.listen_button.draw()
        self.mic_button.set_active(True)
        self.mic_status_label.configure(text="🎤 Escuchando... Habla y luego pulsa Detener", fg=ACCENT_GREEN)
        self.live_transcript_label.configure(text="", fg=ACCENT_GREEN)
        self.set_status_lamp(True)
        self.set_status_text("Estado: Escuchando...", ACCENT_GREEN)
        self.add_message("Sistema", "Escuchando... habla, cuando termines pulsa ⏹ Detener")
        threading.Thread(target=self.listen_loop, daemon=True).start()
        
    def stop_listening(self):
        """Detiene la escucha y procesa todo lo que dijo"""
        self.is_listening = False
        self.tts_engine.stop()
        self.listen_button.set_text("🎤 Escuchar")
        self.listen_button.bg_color = ACCENT_GREEN
        self.listen_button.text_color = BG_ROOT
        self.listen_button.draw()
        self.mic_button.set_active(False)
        self.mic_status_label.configure(text="Haz clic en el micrófono para hablar", fg=TEXT_GRAY)
        self.live_transcript_label.configure(text="", fg=ACCENT_GREEN)
        self.set_status_lamp(False)
        self.set_status_text("Estado: Listo", TEXT_WHITE)
        
        if self.pending_text:
            # Unir todo lo que dijo en una sola frase
            full_text = ' '.join(self.pending_text).strip()
            self.pending_text = []
            if full_text:
                self.add_message("Tú", full_text)
                self.process_command(full_text)
        else:
            self.add_message("Sistema", "No se detectó ninguna palabra.")
        
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
                    max_bytes = 16000 * 2 * 40
                    if len(buffer_chunks) > max_bytes:
                        del buffer_chunks[:len(buffer_chunks) - max_bytes]
                    
                    # Feedback en vivo con Vosk (instantáneo y local)
                    if self.rec:
                        try:
                            if self.rec.AcceptWaveform(bytes(chunk)):
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
        try:
            audio_full = sr.AudioData(bytes(buffer_chunks), 16000, 2)
            boosted = np.clip(np.frombuffer(buffer_chunks, dtype=np.int16).astype(np.float32) * 1.3,
                              -32767, 32767).astype(np.int16)
            audio_full = sr.AudioData(boosted.tobytes(), 16000, 2)
        except Exception:
            audio_full = None
        
        text = ""
        if audio_full:
            # Google primero (precisión; ante ruido puro devuelve error)
            try:
                text = self.recognizer.recognize_google(audio_full, language='es-ES')
            except sr.UnknownValueError:
                text = ""
            except sr.RequestError:
                text = ""
            # Gemini como refuerzo
            if not text:
                try:
                    wav_data = audio_full.get_wav_data(convert_rate=16000, convert_width=2)
                    if wav_data and self.brain and self.brain_available:
                        text = self.brain.transcribe_audio(wav_data) or ""
                except Exception:
                    text = ""
        
        # Fallback: lo que captó Vosk en directo
        if not text and last_phrase:
            text = last_phrase
        
        if text and text.strip() and audio_full:
            text = text.strip()
            self.pending_text = [text]
            self.root.after(0, lambda: self.set_status_text(
                f"🗣 Captado: {text[:40]}...", ACCENT_GREEN))
    
    def _update_live(self, text, is_final):
        """Actualiza el indicador de transcripción EN VIVO"""
        def _apply():
            displayed = text if is_final else f"… {text}…"
            self.live_transcript_label.configure(
                text=f"🎙️ {displayed}",
                fg=ACCENT_GREEN if is_final else ACCENT)
        self.root.after(0, _apply)
                
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
        elif any(word in command_lower for word in ["música", "cancion", "canción", "volumen", "spotify", "musica", "repite", "repetición", "playlist", "lista de reproducción"]):
            # Control de Spotify con la voz
            music_response, _action = handle_music_command(command)
            if music_response:
                response = music_response
            else:
                response = "Puedes decirme: pon música, pausa, siguiente canción, sube o baja el volumen."
        else:
            # Intentar recordar respuesta aprendida primero
            recalled, score = self.memory.recall_answer(command)
            if recalled and score > 0.75:
                response = f"[Lo recuerdo] {recalled}"
            elif self.brain_available:
                # Añadir contexto de memoria a Gemini
                self.root.after(0, lambda: self.speak("Un momento, estoy consultando..."))
                threading.Thread(target=self._gemini_reply, args=(command,), daemon=True).start()
                return
            else:
                response = f"Escuché: {command}. Conecta Gemini para respuestas inteligentes."
            
        self.root.after(0, lambda: self.speak(response))
        
    def _gemini_reply(self, text):
        """Obtiene respuesta de Gemini con contexto de memoria"""
        try:
            self.root.after(0, lambda: self.set_status_text("🧠 Consultando Gemini...", ACCENT))
            
            # Incluir contexto de memoria y hechos en la petición
            context = self.memory.get_last_context(n=8)
            facts = self.memory.learned_facts_string()
            
            prompt_with_context = text
            if context:
                prompt_with_context = f"CONVERSACIÓN PREVIA:\n{context}\n\n"
            if facts:
                prompt_with_context += f"DATOS DEL USUARIO: {facts}\n\n"
            prompt_with_context += f"PREGUNTA ACTUAL: {text}"
            
            if self.attached_path:
                response = self.brain.ask_with_file(prompt_with_context, self.attached_path)
            else:
                response = self.brain.ask(prompt_with_context, use_web=True, max_tokens=1200)
            if response:
                self.memory.add_message('assistant', response)
                self.memory.learn_answer(text, response)
                self.root.after(0, lambda: self.speak(response))
            else:
                self.root.after(0, lambda: self.speak(
                    "Perdona, no puedo contactar con Gemini ahora mismo. Intenta de nuevo."))
            self.root.after(0, lambda: self.set_status_text("Estado: Listo", TEXT_WHITE))
        except Exception as e:
            self.root.after(0, lambda: self.speak(
                "Lo siento, tuve problemas con Gemini. ¿Probamos de nuevo?"))
            self.root.after(0, lambda: self.set_status_text("Estado: Listo", TEXT_WHITE))
            
    def _generate_code(self, text, kind="code"):
        """Genera código o pseudocódigo con Gemini y lo muestra en el chat"""
        label = "Código" if kind == "code" else "Pseudocódigo"
        try:
            self.root.after(0, lambda: self.set_status_text(f"💻 Escribiendo {label}...", ACCENT))
            response = self.brain.generate_code(text, kind=kind)
            if response:
                self.memory.add_message('assistant', response)
                self.memory.learn_answer(text, label + " de " + (text.split("para", 1)[-1].strip() if "para" in text else text))
                self.root.after(0, lambda: self._show_code(response, label))
                self.root.after(0, lambda: self.speak(
                    f"He generado el {label.lower()}. Revisa el chat. Si quieres, guárdalo en un archivo."))
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