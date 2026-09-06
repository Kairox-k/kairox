#!/usr/bin/env python3
"""
Interfaz Web para Asistente de Voz IA Local
Requiere: pip install SpeechRecognition pyttsx3 vosk pyaudio flask
"""

from flask import Flask, render_template, jsonify, request
import speech_recognition as sr
import pyttsx3
import json
import os
import threading
from datetime import datetime
from vosk import Model, KaldiRecognizer
from voice_engine import VoiceEngine

app = Flask(__name__)

class VoiceAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_engine = VoiceEngine()
        self.is_listening = False
        self.vosk_model = None
        self.rec = None
        self.load_vosk_model()
        
    def load_vosk_model(self):
        """Carga el modelo Vosk para reconocimiento offline"""
        model_path = "vosk-model-small-es-0.42"
        if not os.path.exists(model_path):
            os.system("wget -q https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip")
            os.system("unzip -q vosk-model-small-es-0.42.zip")
        
        try:
            self.vosk_model = Model(model_path)
            self.rec = KaldiRecognizer(self.vosk_model, 16000)
            print("Modelo de voz cargado correctamente")
        except Exception as e:
            print(f"Error cargando modelo: {e}")
            
    def speak(self, text):
        """Convierte texto a voz"""
        self.tts_engine.speak(text)
        
    def listen_once(self):
        """Escucha un comando"""
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
            if self.rec:
                audio_data = audio.get_raw_data()
                
                if self.rec.AcceptWaveform(audio_data):
                    result = json.loads(self.rec.Result())
                    return result.get("text", "")
                else:
                    result = json.loads(self.rec.PartialResult())
                    return result.get("partial", "")
            return ""
        except Exception as e:
            print(f"Error de escucha: {e}")
            return ""
            
    def process_command(self, command):
        """Procesa comandos especiales"""
        command_lower = command.lower()
        
        if any(word in command_lower for word in ["hora", "qué hora es"]):
            now = datetime.now()
            return f"Son las {now.strftime('%H:%M')}"
        elif any(word in command_lower for word in ["fecha", "qué día es"]):
            now = datetime.now()
            return f"Hoy es {now.strftime('%d/%m/%Y')}"
        elif any(word in command_lower for word in ["nombre", "cómo te llamas"]):
            return "Soy tu asistente de voz personal, creada en Python."
        elif any(word in command_lower for word in ["ayuda", "qué puedes hacer"]):
            return "Puedo ayudarte con: hora, fecha, y responder preguntas simples."
        elif any(word in command_lower for word in ["clima", "tiempo"]):
            return "No tengo acceso a datos del clima en modo offline."
        elif any(word in command_lower for word in ["música", "canción"]):
            return "No tengo acceso a música en modo offline."
        else:
            return f"Escuché: {command}"

assistant = VoiceAssistant()

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/listen', methods=['POST'])
def listen():
    """Endpoint para escuchar un comando"""
    text = assistant.listen_once()
    if text:
        response = assistant.process_command(text)
        threading.Thread(target=assistant.speak, args=(response,), daemon=True).start()
        return jsonify({
            'success': True,
            'user_input': text,
            'response': response
        })
    return jsonify({
        'success': False,
        'user_input': '',
        'response': 'No se detectó voz'
    })

@app.route('/speak', methods=['POST'])
def speak():
    """Endpoint para hablar texto"""
    data = request.get_json()
    text = data.get('text', '')
    if text:
        threading.Thread(target=assistant.speak, args=(text,), daemon=True).start()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/command', methods=['POST'])
def command():
    """Endpoint para ejecutar comandos rápidos"""
    data = request.get_json()
    command_text = data.get('command', '')
    response = assistant.process_command(command_text)
    threading.Thread(target=assistant.speak, args=(response,), daemon=True).start()
    return jsonify({
        'success': True,
        'command': command_text,
        'response': response
    })

if __name__ == '__main__':
    print("Iniciando servidor en http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)