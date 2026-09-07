#!/usr/bin/env python3
"""Prueba de transcripción de audio con Gemini"""

import sys
import os

def test_gemini_transcribe():
    from google import genai
    from google.genai import types
    
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY='):
                    os.environ['GEMINI_API_KEY'] = line.strip().split('=', 1)[1]
                    break
    
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        print('No API key')
        return
    
    client = genai.Client(api_key=key)
    
    # Simular un pequeño audio en silencio para probar la API
    import io, wave, struct
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b'\x00\x00' * 16000)  # 1 segundo de silencio
    
    wav_data = buf.getvalue()
    
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[
                'Transcribe el audio en español:',
                types.Part.from_bytes(data=wav_data, mime_type="audio/wav")
            ],
        )
        print('Resultado:', resp.text if resp and resp.text else '(vacío)')
        print('Transcripción con Gemini: OK')
    except Exception as e:
        print('Error transcripción:', e)

if __name__ == '__main__':
    test_gemini_transcribe()