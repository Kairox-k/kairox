#!/usr/bin/env python3
"""
Gestor de archivos de Kairox
Crea carpetas y documentos por voz, guardándolos donde el usuario indique.
Todo queda dentro del directorio personal (seguridad).
"""

import os
import re
from pathlib import Path

HOME = Path.home()

# Alias de lugares comunes a rutas reales
PLACES = {
    "escritorio": [Path("Escritorio"), Path("Desktop")],
    "descargas": [Path("Descargas"), Path("Downloads")],
    "documentos": [Path("Documentos"), Path("Documents")],
    "musica": [Path("Música"), Path("Music")],
    "música": [Path("Música"), Path("Music")],
    "imagenes": [Path("Imágenes"), Path("Pictures")],
    "imágenes": [Path("Imágenes"), Path("Pictures")],
    "imagen": [Path("Imágenes"), Path("Pictures")],
    "videos": [Path("Vídeos"), Path("Videos")],
    "vídeos": [Path("Vídeos"), Path("Videos")],
    "video": [Path("Vídeos"), Path("Videos")],
    "home": [Path(".")],
    "inicio": [Path(".")],
    "casa": [Path(".")],
    "proyectos": [Path("Proyectos")],
    "proyecto": [Path("Proyectos")],
}

def _resolve_place(name):
    """Devuelve la primera ruta real existente de un lugar común"""
    name = name.strip().lower()
    norm = name.rstrip("s")
    candidates = PLACES.get(name) or PLACES.get(norm)
    if not candidates:
        return None
    for cand in candidates:
        if cand.exists():
            return cand
    return candidates[0]

def safe_dir(path, base=HOME):
    """Convierte una ruta en una ruta segura bajo el home"""
    if isinstance(path, Path):
        p = path
    elif path:
        p = Path(str(path).strip())
    else:
        p = Path(".")
    target = (base / p).resolve()
    # Asegura que no se salga del home
    if str(target).startswith(str(base.resolve())):
        return target
    return base

def find_target(command, base=HOME):
    """Dado un comando, detecta la ubicación deseada (escritorio, descargas, ...)"""
    m = re.search(r'\b(?:en|en el|en la|en mis|dentro de)\s+([a-záéíóúñ ]+?)(?:[.,]|$|\sy\s)', command.lower())
    for place in PLACES:
        if re.search(rf'\b(?:en|en el|en la|en mis|dentro de)\s+{place}\b', command.lower()):
            return _resolve_place(place)
    return base

def _extract_name(command):
    """Extrae el nombre (después de 'llamada/o' o 'que se llame')"""
    for pat in [r'llamad[oa]\s+([\w\- ]+)', r'que se llame\s+([\w\- ]+)',
                r'con el nombre de\s+([\w\- ]+)', r'con el nombre\s+([\w\- ]+)']:
        m = re.search(pat, command.lower())
        if m:
            name = re.split(r'\s+(?:en|en el|en la|que contenga|con)\b', m.group(1))[0].strip()
            if name:
                return name
    return None

def create_folder(command):
    """Crea una carpeta según el comando"""
    name = _extract_name(command)
    if not name:
        # Intentar con la última palabra significativa
        m = re.search(r'carpeta\s+(?:llamada\s+)?([\w\- ]+?)(?:\s+en\b|$)', command.lower())
        if m:
            name = m.group(1).strip()
    if not name:
        return None, "No sé cómo llamar a la carpeta. Dime algo como: crea una carpeta llamada proyectos"
    target_dir = safe_dir(_extract_location(command))
    path = target_dir / name
    if path.exists():
        return path, f"La carpeta {name} ya existe en {target_dir}"
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path, f"Carpeta {name} creada en {target_dir}"
    except Exception as e:
        return None, f"No pude crear la carpeta: {e}"

def create_document(command):
    """Crea un documento de texto según el comando"""
    name = _extract_name(command)
    if not name:
        m = re.search(r'(?:documento|archivo|texto|nota)\s+(?:llamad[oa]\s+)?([\w\- ]+?)(?:\s+en\b|\s+que\b|$)', command.lower())
        if m:
            name = m.group(1).strip()
    if not name:
        return None, "Dime el nombre del documento. Por ejemplo: crea un documento llamado apuntes"
    if not name.endswith('.txt') and not name.endswith('.md'):
        name += '.txt'
    target_dir = safe_dir(_extract_location(command))
    path = target_dir / name
    if path.exists():
        return path, f"El documento {name} ya existe en {target_dir}"
    try:
        content = _extract_content(command)
        path.write_text(content, encoding='utf-8')
        if content:
            return path, f"Documento {name} creado en {target_dir}"
        return path, f"Documento vacío {name} creado en {target_dir}"
    except Exception as e:
        return None, f"No pude crear el documento: {e}"

def _to_safe_rel(loc):
    """Limpia una ruta relativa (sin artículos ni caracteres raros)"""
    loc = re.sub(r'^[\./\s]+', '', loc)
    loc = re.sub(r'[<>:"|?*\\]', '', loc)
    return loc.strip()

def _extract_location(command):
    """Devuelve la ruta (Path) deseada tras 'en ...', o el home"""
    m = re.search(r'\b(?:en|en el|en la|en mis|en mi|dentro de)\s+([\w\- /]+?)\s*(?:llamad|que se llame|que contenga|con el nombre|contenido|$)', command.lower())
    if not m:
        return Path(".")
    loc = m.group(1).strip().rstrip('.')
    if not loc:
        return Path(".")
    # Quitar artículos iniciales
    loc = re.sub(r'^(el|la|los|las|mis|mi|un|una|unos|unas)\s+', '', loc)
    if not loc:
        return Path(".")
    first_word = re.split(r'[/\s]+', loc)[0]
    known = _resolve_place(first_word)
    if known:
        head, _, rest = loc.partition('/')
        rest = _to_safe_rel(rest)
        if rest:
            return known / rest
        return known
    return Path(".") / _to_safe_rel(loc)

def _extract_content(command):
    """Extrae el contenido si el usuario pide 'que contenga'"""
    m = re.search(r'(?:que contenga|con el siguiente contenido|con este contenido|y ponle)\s+["\']?([^"\']+?)["\']?\s*$', command.lower())
    if m:
        return m.group(1).strip()
    return ""

def handle_file_command(command):
    """Interpreta un comando de archivos. Devuelve (path o None, mensaje)"""
    c = command.lower()
    is_folder = bool(re.search(r'\b(?:carpeta|directorio|a la carpeta)\b', c))
    is_doc = bool(re.search(r'\b(?:documento|archivo|texto|nota|apuntes)\b', c)) or 'archivo' in c
    if is_folder and not is_doc:
        return create_folder(command)
    if is_doc:
        return create_document(command)
    return None, None