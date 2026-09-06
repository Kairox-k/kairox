#!/usr/bin/env python3
"""
Asistente de Voz IA Local en Python
Requiere: pip install SpeechRecognition pyttsx3 vosk pyaudio gpt4all
"""

import speech_recognition as sr
import pyttsx3
import json
import queue
import sys
import os
import threading
from datetime import datetime
from vosk import Model, KaldiRecognizer
from gpt4all import GPT4All

class VoiceAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)
        self.tts_engine.setProperty('volume', 0.9)
        self.is_listening = False
        self.audio_queue = queue.Queue()
        
        # Cargar modelo de voz (español)
        self.vosk_model = None
        self.load_vosk_model()
        
        # Cargar modelo de IA local
        self.ai_model = None
        self.load_ai_model()
        
    def load_vosk_model(self):
        """Carga el modelo Vosk para reconocimiento offline"""
        model_path = "vosk-model-small-es-0.42"
        if not os.path.exists(model_path):
            print("Descargando modelo de voz español...")
            os.system("wget https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip")
            os.system("unzip vosk-model-small-es-0.42.zip")
        self.vosk_model = Model(model_path)
        self.rec = KaldiRecognizer(self.vosk_model, 16000)
        
    def load_ai_model(self):
        """Carga el modelo GPT4All para respuestas locales"""
        try:
            self.ai_model = GPT4All("orca-mini-3b-gguf2-q4_0.gguf", verbose=False)
            print("Modelo de IA cargado correctamente")
        except Exception as e:
            print(f"Error cargando modelo IA: {e}")
            print("Instalando modelo...")
            os.system("python -c \"from gpt4all import GPT4All; GPT4All('orca-mini-3b-gguf2-q4_0.gguf')\"")
            self.ai_model = GPT4All("orca-mini-3b-gguf2-q4_0.gguf", verbose=False)
            
    def speak(self, text):
        """Convierte texto a voz"""
        print(f"Asistente: {text}")
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
        
    def listen_with_vosk(self):
        """Escucha usando Vosk (reconocimiento offline)"""
        with self.microphone as source:
            print("Ajustando ruido ambiental...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
        print("Escuchando...")
        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
        
        # Convertir audio a formato Vosk
        audio_data = audio.get_raw_data()
        
        if self.rec.AcceptWaveform(audio_data):
            result = json.loads(self.rec.Result())
            return result.get("text", "")
        else:
            result = json.loads(self.rec.PartialResult())
            return result.get("partial", "")
            
    def listen_with_google(self):
        """Escucha usando Google Speech Recognition (requiere internet)"""
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
            print("Escuchando...")
            audio = self.recognizer.listen(source, timeout=5)
            
        try:
            text = self.recognizer.recognize_google(audio, language="es-ES")
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            return ""
            
    def get_ai_response(self, user_input):
        """Obtiene respuesta del modelo de IA local"""
        try:
            prompt = f"""Eres un asistente de voz amigable y servicial. 
Responde de forma concisa y natural en español.

Usuario: {user_input}
Asistente:"""
            
            response = self.ai_model.generate(prompt, max_tokens=150)
            return response.strip()
        except Exception as e:
            return f"Disculpa, tuve un problema al procesar tu solicitud: {str(e)}"
            
    def process_command(self, command):
        """Procesa comandos especiales"""
        command = command.lower()
        
        if any(word in command for word in ["hora", "qué hora es"]):
            now = datetime.now()
            return f"Son las {now.strftime('%H:%M')}"
            
        elif any(word in command for word in ["fecha", "qué día es"]):
            now = datetime.now()
            return f"Hoy es {now.strftime('%d/%m/%Y')}"
            
        elif any(word in command for word in ["adiós", "hasta luego", "chao"]):
            return "¡Hasta luego! Que tengas un buen día."
            
        elif any(word in command for word in ["nombre", "cómo te llamas"]):
            return "Soy tu asistente de voz personal, creada en Python."
            
        elif any(word in command for word in ["ayuda", "qué puedes hacer"]):
            return """Puedo ayudarte con:
- Responder preguntas generales
- Decirte la hora y fecha
- Conversar contigo
- Responder sobre diversos temas
Simplemente háblame de forma natural."""
            
        else:
            return self.get_ai_response(command)
            
    def run(self):
        """Bucle principal del asistente"""
        self.speak("Hola, soy tu asistente de voz. ¿En qué puedo ayudarte?")
        
        while True:
            try:
                # Usar Vosk para reconocimiento offline
                text = self.listen_with_vosk()
                
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
                
    def run_google_mode(self):
        """Modo alternativo con Google Speech Recognition"""
        self.speak("Modo Google activado. ¿En qué puedo ayudarte?")
        
        while True:
            try:
                text = self.listen_with_google()
                
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
    os.system("pip install SpeechRecognition pyttsx3 vosk gpt4all pyaudio")
    
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Asistente de Voz IA Local")
    parser.add_argument("--install", action="store_true", help="Instalar dependencias")
    parser.add_argument("--google", action="store_true", help="Usar Google Speech Recognition")
    
    args = parser.parse_args()
    
    if args.install:
        install_requirements()
        print("Dependencias instaladas. Ejecute el script sin --install.")
        sys.exit(0)
        
    assistant = VoiceAssistant()
    
    if args.google:
        assistant.run_google_mode()
    else:
        assistant.run()