#!/usr/bin/env python3
"""
Motor de voz humanizado para Kairox
Cadena de calidad: edge-tts (voces neuronales) -> gTTS (Google) -> espeak-ng (fallback offline)
Cola de reproducción serializada para evitar voces superpuestas
"""

import subprocess
import os
import sys
import tempfile
import threading
import queue
import asyncio

# Voces neuronales humanas en español (latinoamericano, masculina)
EDGE_VOICE = "es-MX-JorgeNeural"
GTTS_LANG = "es"
GTTS_TLD = "com.mx"
GTTS_SLOW = False

class VoiceEngine:
    """Motor de texto a voz humanizado con cola serializada (sin superposiciones)"""

    def __init__(self, voice="es-419"):
        self.voice = voice
        self.rate = 150
        self.pitch = 50
        self.volume = 95
        self.gap = 4
        self._espeak_path = self._find_espeak()
        self._ffplay_path = self._find_ffplay()
        self._use_human_voice = True
        
        # Cola de reproducción serializada
        self._queue = queue.Queue()
        self._current_process = None
        self._lock = threading.Lock()
        self._speaking = False
        self._clear_requested = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        
    def _find_espeak(self):
        """Busca la ruta de espeak-ng"""
        for cmd in ["espeak-ng", "espeak"]:
            try:
                result = subprocess.run(["which", cmd], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
        return None
        
    def _find_ffplay(self):
        """Busca reproductor de audio (ffplay o paplay)"""
        for cmd in ["ffplay", "paplay"]:
            try:
                result = subprocess.run(["which", cmd], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                pass
        return None
        
    def _worker_loop(self):
        """Hilo único que reproduce el habla en orden (sin superposiciones)"""
        while True:
            text = self._queue.get()
            self._clear_requested.clear()
            self._speaking = True
            try:
                if self._use_human_voice:
                    if not self._try_edge_tts(text):
                        if not self._try_gtts(text):
                            self._run_espeak(text)
                else:
                    self._run_espeak(text)
            finally:
                # Si no hubo cancelación, marcar como no hablando
                if not self._clear_requested.is_set():
                    self._speaking = False
                self._queue.task_done()
    
    # ---------- Voz humana: edge-tts ----------
    def _try_edge_tts(self, text, timeout=30):
        """Genera MP3 con voz neuronal de Microsoft y lo reproduce"""
        if not self._ffplay_path:
            return False
        try:
            import edge_tts
            tmp_path = os.path.join(tempfile.gettempdir(), f"kairox_edge_{os.getpid()}.mp3")
            communicate = edge_tts.Communicate(text, EDGE_VOICE)
            asyncio.run(communicate.save(tmp_path))
            return self._play_audio(tmp_path)
        except Exception:
            return False
    
    # ---------- Voz humana: gTTS ----------
    def _try_gtts(self, text, timeout=30):
        """Genera MP3 con la voz de Google y lo reproduce"""
        if not self._ffplay_path:
            return False
        try:
            from gtts import gTTS
            tmp_path = os.path.join(tempfile.gettempdir(), f"kairox_gtts_{os.getpid()}.mp3")
            tts = gTTS(text=text, lang=GTTS_LANG, tld=GTTS_TLD, slow=GTTS_SLOW)
            tts.save(tmp_path)
            return self._play_audio(tmp_path)
        except Exception:
            return False
    
    def _play_audio(self, path):
        """Reproduce un archivo de audio con ffplay (bloqueante, solo worker)"""
        args = [self._ffplay_path, "-nodisp", "-autoexit", "-loglevel", "error", path]
        self._current_process = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                                 stderr=subprocess.DEVNULL)
        self._current_process.wait()
        self._current_process = None
        try:
            os.remove(path)
        except Exception:
            pass
        return True
    
    # ---------- Voz offline: espeak-ng ----------
    def _run_espeak(self, text):
        """Ejecuta espeak-ng (bloqueante, solo desde el worker)"""
        if not self._espeak_path:
            print("Error: espeak-ng no encontrado")
            return
            
        args = [
            self._espeak_path,
            "-v", self.voice,
            "-s", str(self.rate),
            "-p", str(self.pitch),
            "-a", str(self.volume),
            "-k", "8",
            "-g", str(self.gap),
            text
        ]
        
        self._current_process = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                                 stderr=subprocess.DEVNULL)
        self._current_process.wait()
        self._current_process = None
    
    # ---------- API pública ----------
    def speak(self, text, async_mode=False):
        """Encola texto para hablar (no se superpone con habla anterior)"""
        if not text or not text.strip():
            return
        formatted = self.naturalize_text(text)
        if async_mode:
            self._queue.put(formatted)
        else:
            self._queue.put(formatted)
            self._queue.join()
            
    def speak_async(self, text):
        """Habla en segundo plano respetando la cola"""
        self.speak(text, async_mode=True)
        
    def stop(self):
        """Detiene el habla actual y limpia la cola pendiente"""
        self._clear_requested.set()
        with self._lock:
            if self._current_process:
                try:
                    self._current_process.terminate()
                except Exception:
                    pass
        # Vaciar cola pendiente
        try:
            while True:
                self._queue.get_nowait()
                self._queue.task_done()
        except queue.Empty:
            pass
        self._speaking = False
        
    def is_speaking(self):
        """Indica si hay habla en curso"""
        return self._speaking and self._current_process is not None
        
    def naturalize_text(self, text):
        """Prepara el texto para pronunciar mejor y fluido en español"""
        text = text.replace('¿', '')
        text = text.replace('¡', '')
        text = ' '.join(text.split())
        return text

def create_voice_engine():
    """Factory para crear el motor de voz"""
    try:
        return VoiceEngine()
    except Exception as e:
        print(f"Error creando motor de voz: {e}")
        return VoiceEngine()