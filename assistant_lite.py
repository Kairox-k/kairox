#!/usr/bin/env python3
"""
Asistente de Voz IA Local en Python (Versión Liviana)
Requiere: pip install SpeechRecognition pyttsx3 vosk pyaudio
"""

import speech_recognition as sr
import pyttsx3
import json
import sys
import os
from datetime import datetime
from vosk import Model, KaldiRecognizer

class VoiceAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)
        self.tts_engine.setProperty('volume', 0.9)
        
        # Cargar modelo de voz (español)
        self.vosk_model = None
        self.load_vosk_model()
        
    def load_vosk_model(self):
        """Carga el modelo Vosk para reconocimiento offline"""
        model_path = "vosk-model-small-es-0.42"
        if not os.path.exists(model_path):
            print("Descargando modelo de voz español...")
            os.system("wget -q https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip")
            os.system("unzip -q vosk-model-small-es-0.42.zip")
        self.vosk_model = Model(model_path)
        self.rec = KaldiRecognizer(self.vosk_model, 16000)
        
    def speak(self, text):
        """Convierte texto a voz"""
        print(f"Asistente: {text}")
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
        
    def listen(self):
        """Escucha usando Vosk (reconocimiento offline)"""
        with self.microphone as source:
            print("Ajustando ruido ambiental...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
        print("Escuchando...")
        audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
        
        audio_data = audio.get_raw_data()
        
        if self.rec.AcceptWaveform(audio_data):
            result = json.loads(self.rec.Result())
            return result.get("text", "")
        else:
            result = json.loads(self.rec.PartialResult())
            return result.get("partial", "")
            
    def process_command(self, command):
        """Procesa comandos especiales"""
        command = command.lower()
        
        if any(word in command for word in ["hora", "qué hora es"]):
            now = datetime.now()
            return f"Son las {now.strftime('%H:%M')}"
            
        elif any(word in command for word in ["fecha", "qué día es"]):
            now = datetime.now()
            return f"Hoy es {now.strftime('%d/%m/%Y')}"
            
        elif any(word in command for word in ["adiós", "hasta luego", "chao", "salir"]):
            return "¡Hasta luego! Que tengas un buen día."
            
        elif any(word in command for word in ["nombre", "cómo te llamas"]):
            return "Soy tu asistente de voz personal, creada en Python."
            
        elif any(word in command for word in ["ayuda", "qué puedes hacer"]):
            return """Puedo ayudarte con:
- Decirte la hora y fecha
- Responder preguntas simples
- Conversar contigo
Simplemente háblame de forma natural."""
            
        elif any(word in command for word in ["clima", "tiempo", "temperatura"]):
            return "No tengo acceso a datos del clima en modo offline."
            
        elif any(word in command for word in ["música", "canción", "playlist"]):
            return "No tengo acceso a música en modo offline."
            
        else:
            return f"Escuché: {command}. Soy un asistente básico en modo offline."
            
    def run(self):
        """Bucle principal del asistente"""
        self.speak("Hola, soy tu asistente de voz. Di hora, fecha o ayuda para comenzar.")
        
        while True:
            try:
                text = self.listen()
                
                if text:
                    print(f"Tú: {text}")
                    
                    if any(word in text.lower() for word in ["adiós", "hasta luego", "chao", "salir"]):
                        response = self.process_command(text)
                        self.speak(response)
                        break
                        
                    response = self.process_command(text)
                    self.speak(response)
                    
            except KeyboardInterrupt:
                self.speak("Hasta luego")
                break
            except Exception as e:
                print(f"Error: {e}")
                continue

def install_requirements():
    """Instala las dependencias necesarias"""
    print("Instalando dependencias...")
    os.system("pip install SpeechRecognition pyttsx3 vosk pyaudio")
    
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Asistente de Voz Local (Versión Liviana)")
    parser.add_argument("--install", action="store_true", help="Instalar dependencias")
    
    args = parser.parse_args()
    
    if args.install:
        install_requirements()
        print("Dependencias instaladas. Ejecute el script sin --install.")
        sys.exit(0)
        
    assistant = VoiceAssistant()
    assistant.run()