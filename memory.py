#!/usr/bin/env python3
"""
Sistema de Memoria y Aprendizaje para Kairox
- Guarda historial de conversación (persistente)
- Aprende hechos del usuario (nombre, gustos, preferencias)
- Guarda pares pregunta->respuesta útiles y los recupera por similitud
- Implementa una mini red neuronal (hash-embedding + similitud coseno)
"""

import os
import json
import re
import hashlib
import math
import time
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "kairox_memory.json")

def _vectorize(text, dims=256):
    """Convierte texto en un vector de hash (embedding-lite sin dependencias)"""
    vec = [0.0] * dims
    tokens = re.findall(r'\w+', text.lower())
    for i, tok in enumerate(tokens):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dims
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign * (1.0 + (i % 3) * 0.5)
    # Normalizar
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec

def _cosine(a, b):
    """Similitud coseno entre dos vectores"""
    return sum(x * y for x, y in zip(a, b))

class MemorySystem:
    """Memoria persistente con aprendizaje de Kairox"""

    LEARN_RULES = [
        (r'me llamo ([a-záéíóúñ\s]+)', 'nombre'),
        (r'soy ([a-záéíóúñ\s]+)', 'nombre'),
        (r'mi nombre es ([a-záéíóúñ\s]+)', 'nombre'),
        (r'llámame ([a-záéíóúñ\s]+)', 'nombre'),
        (r'tengo (\d+) años', 'edad'),
        (r'vivo en ([a-záéíóúñ\s]+)', 'ciudad'),
        (r'soy de ([a-záéíóúñ\s]+)', 'ciudad'),
        (r'me gusta ([a-záéíóúñ\s]+)', 'gustos'),
        (r'me encanta ([a-záéíóúñ\s]+)', 'gustos'),
        (r'mi color favorito es ([a-záéíóúñ\s]+)', 'color_favorito'),
        (r'trabajo de ([a-záéíóúñ\s]+)', 'trabajo'),
        (r'soy estudiante de ([a-záéíóúñ\s]+)', 'estudio'),
    ]

    def __init__(self):
        self.data = {
            'facts': {},          # hechos aprendidos: {clave: valor}
            'qa': [],             # pares aprendidos: [{q, a, score}]
            'history': [],        # historial de conversación
            'learned_count': 0,
        }
        self.load()
        self._vector_cache = {}

    def load(self):
        """Carga memoria desde disco"""
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE) as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        self.data.setdefault(k, v)
            except Exception:
                pass

    def save(self):
        """Guarda memoria en disco"""
        try:
            with open(MEMORY_FILE, 'w') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- Conversación ----------
    def add_message(self, role, text):
        """Guarda un mensaje en el historial"""
        if not text:
            return
        self.data['history'].append({
            'role': role,
            'text': text,
            'time': time.time(),
        })
        # Mantener historial acotado (últimas 200)
        if len(self.data['history']) > 200:
            self.data['history'] = self.data['history'][-200:]
        self.save()

    def get_last_context(self, n=8):
        """Devuelve las últimas n interacciones para dar contexto a Gemini"""
        context = []
        for msg in self.data['history'][-n:]:
            role = "Usuario" if msg['role'] == 'user' else 'Kairox'
            context.append(f"{role}: {msg['text']}")
        return "\n".join(context)

    # ---------- Aprendizaje de hechos ----------
    def learn_from_text(self, text):
        """Extrae y aprende hechos del texto del usuario"""
        text_lower = text.lower()
        learned = []
        # Normalizar "me llamo X y ..." cortando en conectores
        for pattern, fact_key in self.LEARN_RULES:
            m = re.search(pattern, text_lower)
            if m:
                value = m.group(1).strip()
                # Cortar en conectores o partículas que terminan el hecho
                value = re.split(r'\s+(?:y|soy|vivo|estoy|quiero|me gusta|porque|tengo|pero)\b', value)[0].strip()
                value = re.split(r'[.,;:!?¿]', value)[0].strip()
                value = value.strip(' .')
                # Limpiar artículos residuales al final
                value = re.sub(r'\s+(el|la|mi|en|un|una)\s*$', '', value)
                if value and not value.isspace():
                    old = self.data['facts'].get(fact_key)
                    if old != value:
                        self.data['facts'][fact_key] = value
                        self.data['learned_count'] += 1
                        learned.append((fact_key, value))
        if learned:
            self.save()
        return learned

    def learn_answer(self, question, answer, good=True):
        """Aprende un par pregunta->respuesta (reforzamiento simple)"""
        q = question.lower().strip()
        exists = False
        for item in self.data['qa']:
            if q in item['q'].lower() or item['q'].lower() in q:
                item['a'] = answer
                item['score'] = min(10, item.get('score', 0) + (1 if good else -1))
                item['good'] = good
                exists = True
                break
        if not exists:
            self.data['qa'].append({
                'q': question,
                'a': answer,
                'score': 1 if good else -1,
                'good': good,
                'time': time.time(),
            })
            self.data['learned_count'] += 1
        self.save()

    # ---------- Recuperación por similitud (mini red neuronal) ----------
    def recall_answer(self, question, threshold=0.45):
        """Busca una respuesta aprendida similar a la pregunta"""
        q = question.lower().strip()
        qvec = self._vectorize(q)
        best = None
        best_score = 0.0
        for item in self.data['qa']:
            vec = self._vectorize(item['q'])
            score = _cosine(qvec, vec)
            if score > best_score:
                best_score = score
                best = item
        if best and best_score >= threshold and best.get('score', 0) > 0:
            return best['a'], best_score
        return None, 0.0

    def _vectorize(self, text):
        """Vectoriza con caché"""
        if text not in self._vector_cache:
            self._vector_cache[text] = _vectorize(text)
        return self._vector_cache[text]

    def learned_facts_string(self):
        """Formatea los hechos aprendidos"""
        if not self.data['facts']:
            return ""
        labels = {
            'nombre': 'Se llama', 'edad': 'Tiene', 'ciudad': 'Vive en',
            'gustos': 'Le gusta', 'color_favorito': 'Color favorito',
            'trabajo': 'Trabaja de', 'estudio': 'Estudia',
        }
        parts = []
        for k, v in self.data['facts'].items():
            label = labels.get(k, k.replace('_', ' '))
            parts.append(f"{label} {v}")
        return ", ".join(parts)

    def stats(self):
        """Estadísticas de aprendizaje"""
        facts = len(self.data['facts'])
        qa_count = len(self.data['qa'])
        total = self.data['learned_count']
        return f"🧠 {facts} hechos aprendidos · {qa_count} respuestas guardadas · {total} aprendizajes totales"

def create_memory():
    """Factory de memoria"""
    return MemorySystem()