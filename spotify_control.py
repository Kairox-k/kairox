#!/usr/bin/env python3
"""
Control de Spotify para Kairox
Usa playerctl (MPRIS) para reproducir/pausar/navegar canciones
y abre el cliente de Spotify si no está corriendo.
"""

import subprocess
import shutil
import time
import json
import base64
import urllib.request
import urllib.parse
import os

SPOTIFY_PLAYER = "spotify"
PLAYERCTL = shutil.which("playerctl")
XDG_OPEN = shutil.which("xdg-open")
SPOTIFY_CMD = shutil.which("spotify")

def _run(cmd):
    try:
        subprocess.run(cmd, capture_output=True, timeout=5, check=False)
        return True
    except Exception:
        return False

def _playerctl(args):
    if not PLAYERCTL:
        return False
    return _run([PLAYERCTL, "--player", SPOTIFY_PLAYER] + args)

def _playerctl_output(args):
    if not PLAYERCTL:
        return ""
    try:
        r = subprocess.run([PLAYERCTL, "--player", SPOTIFY_PLAYER] + args,
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""

def is_running():
    """¿Está Spotify abierto?"""
    return bool(_playerctl_output(["status"]))

def open_spotify():
    """Abre Spotify si no está corriendo"""
    if not is_running() and SPOTIFY_CMD:
        _run([SPOTIFY_CMD])
        return True
    return False

def play():
    """Reproduce pausa/cancela pausa"""
    if not is_running():
        open_spotify()
    return _playerctl(["play"])

def pause():
    return _playerctl(["pause"])

def play_pause():
    if not is_running():
        open_spotify()
    return _playerctl(["play-pause"])

def next_track():
    if not is_running():
        open_spotify()
    return _playerctl(["next"])

def previous_track():
    if not is_running():
        open_spotify()
    return _playerctl(["previous"])

def stop():
    return _playerctl(["stop"])

def repeat_playlist():
    """Repite toda la playlist"""
    if not is_running():
        open_spotify()
    _playerctl(["loop", "Playlist"])
    time.sleep(0.7)
    return True

def repeat_track():
    """Repite la canción actual"""
    if not is_running():
        open_spotify()
    _playerctl(["loop", "Track"])
    time.sleep(0.7)
    return True

def repeat_off():
    """Desactiva la repetición"""
    _playerctl(["loop", "None"])
    time.sleep(0.7)
    return True

def get_loop_status():
    """Devuelve estado de repetición"""
    status = _playerctl_output(["loop"])
    if status.lower() == "playlist":
        return "Repetición de playlist ACTIVADA"
    elif status.lower() == "track":
        return "Repetición de canción ACTIVADA"
    return "Repetición desactivada"

def volume_up():
    return _playerctl(["volume", "+0.10"])

def volume_down():
    return _playerctl(["volume", "-0.10"])

def _spotify_env(var):
    """Lee una variable de entorno o de .env (mismo formato que config.py)"""
    val = os.environ.get(var)
    if val:
        return val
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path) as f:
            for line in f:
                if line.startswith(var + "="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return None

def get_spotify_credentials():
    """Devuelve (client_id, client_secret) de desarrollador de Spotify"""
    return _spotify_env("SPOTIFY_CLIENT_ID"), _spotify_env("SPOTIFY_CLIENT_SECRET")

def spotify_search_api(term, limit=1):
    """Busca en la API oficial de Spotify.
    Devuelve lista de tracks, o "NO_CREDS" si faltan credenciales, o [] si no hay resultados"""
    cid, csec = get_spotify_credentials()
    if not cid or not csec:
        return "NO_CREDS"
    try:
        body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        req = urllib.request.Request("https://accounts.spotify.com/api/token", data=body, method="POST")
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{cid}:{csec}".encode()).decode())
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=15) as r:
            token = json.loads(r.read())["access_token"]
        url = "https://api.spotify.com/v1/search?q=" + urllib.parse.quote(term) + f"&type=track&limit={limit}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        return data.get("tracks", {}).get("items", [])
    except Exception:
        return []

def search(term):
    """Abre la búsqueda de Spotify con el término dado"""
    if not is_running():
        open_spotify()
        # Dar tiempo a que el cliente termine de arrancar
        for _ in range(10):
            if is_running():
                break
            time.sleep(0.6)
    from urllib.parse import quote
    uri = "spotify:search:" + quote(term)
    return _playerctl(["open", uri])

def play_uri(uri):
    """Reproduce una URI de Spotify directamente (track, album, playlist, artist)"""
    if not is_running():
        open_spotify()
        for _ in range(10):
            if is_running():
                break
            time.sleep(0.6)
    return _playerctl(["open", uri])

def spotify_link_to_uri(text):
    """Convierte un enlace /open.spotify.com/ en una URI spotify:
    p. ej. https://open.spotify.com/track/abc -> spotify:track:abc"""
    if "open.spotify.com/" not in text:
        return None
    idx = text.index("open.spotify.com/") + len("open.spotify.com/")
    rest = text[idx:]
    kind = None
    for k in ("track", "album", "playlist", "artist", "show", "episode"):
        if rest.startswith(k + "/"):
            kind = k
            break
    if not kind:
        return None
    _id = rest[len(kind) + 1:].split("?")[0].split("/")[0]
    _id = (_id.split()[0] if _id.strip() else "").strip()
    if not _id:
        return None
    return f"spotify:{kind}:{_id}"

_SEARCH_PREFIXES = [
    "búscame", "buscame", "busca en spotify", "buscar en spotify",
    "búscala en spotify", "buscar en spotify",
    "va a buscar", "ve a buscar", "busca", "buscar",
    "pónme", "ponme", "póneme", "poneme", "pon a sonar", "pon a reproducir",
    "pon la canción", "pón la canción", "pon la música",
    "quiero escuchar", "quiero oír", "quiero oir",
    "reproduce", "reproducir", "suéname", "suena", "pón", "pon",
]

_SEARCH_SUFFIXES = [
    " en spotify", " en mi cuenta de spotify", " en la cuenta de spotify",
    " en mi cuenta", " en spotify por favor", " por favor",
]

def _extract_search_term(command):
    """Extrae el término de búsqueda quitando prefijos/sufijos comunes"""
    c = command.lower().strip(" .,;:!?")
    for prefix in _SEARCH_PREFIXES:
        if c.startswith(prefix):
            c = c[len(prefix):].strip(" .,;:!?")
            break
    for suffix in _SEARCH_SUFFIXES:
        if c.endswith(suffix):
            c = c[: -len(suffix)].strip(" .,;:!?")
            break
    # Quitar relleno inicial repetido (de/la/música/canción...)
    for _ in range(4):
        for filler in ("música", "musica", "canción", "cancion", "la ", "el ",
                       "un ", "una ", "de ", "que cante ", "que ponga "):
            if c.startswith(filler):
                c = c[len(filler):].strip(" .,;:!?")
                break
        else:
            break
    return c

def _is_search_command(command):
    """Detecta si la frase pide buscar/poner una canción concreta"""
    c = command.lower().strip()
    if any(w in c for w in ["musica", "música", "play", "reproducir música",
                            "reproduce música", "dale música", "inicia música"]):
        return False  # es un 'pon música' simple -> play
    if spotify_link_to_uri(command):
        return True
    for prefix in _SEARCH_PREFIXES:
        if c.startswith(prefix):
            term = c[len(prefix):].strip(" .,;:!?")
            if term:
                return True
    return False

def is_music_command(command):
    """Devuelve True si handle_music_command respondería a esta frase"""
    if not isinstance(command, str):
        return False
    c = command.lower()
    if any(w in c for w in ["música", "musica", "cancion", "canción", "volumen",
                            "spotify", "repite", "repetición", "playlist",
                            "lista de reproduccion", "lista de reproducción",
                            "siguiente", "anterior", "pausa", "reanuda",
                            "continúa", "continua", "adelante",
                            "dale música", "inicia música", "reproduce música",
                            "cierra spotify", "saca la música", "apaga la música"]):
        return True
    if _is_search_command(command):
        return True
    if spotify_link_to_uri(command):
        return True
    return False

def get_status():
    """Devuelve un texto amigable del estado de Spotify"""
    if not is_running():
        return "Spotify está cerrado"
    status = _playerctl_output(["status"])
    if status.lower() == "playing":
        return "reproduciendo música"
    elif status.lower() == "paused":
        return "en pausa"
    return "cerrado"

def handle_music_command(command):
    """Interpreta el comando de voz y ejecuta la acción de música"""
    c = command.lower()
    search_term = _extract_search_term(c)
    if search_term in ("", "musica", "música"):
        search_term = ""

    # Repetición primero (para que "play" dentro de "playlist" no te engañe)
    if any(w in c for w in ["repite la playlist", "repite la lista", "repetir playlist",
                            "repetir la playlist", "quiero repetir", "repite todo",
                            "que repitas la playlist", "que repitas", "repitas la playlist",
                            "repetición de lista", "modo repetición",
                            "repetición de playlist"]):
        if not is_running():
            open_spotify()
        repeat_playlist()
        return get_loop_status(), MicAction.REPEAT

    if any(w in c for w in ["repite esta canción", "repetir esta canción", "repite la canción",
                            "repetición de canción", "repítela"]):
        if not is_running():
            open_spotify()
        repeat_track()
        return get_loop_status(), MicAction.REPEAT

    if any(w in c for w in ["quita la repetición", "sin repetición", "desactiva repetición",
                            "desactivar repetición"]):
        repeat_off()
        return "Repetición desactivada", MicAction.REPEAT

    # --- Enlace directo de Spotify (open.spotify.com) ---
    uri = spotify_link_to_uri(command)
    if uri:
        play_uri(uri)
        return "Voy a reproducir ese enlace en Spotify", MicAction.PLAY

    # --- (la búsqueda de canciones se evalúa al final) ---

    if any(w in c for w in ["pon musica", "pon la música", "play", "reproduce música",
                            "reproducir", "dale música", "inicia música", "pón música"]) and \
       not any(w in c for w in ["repite", "repetir"]) and not search_term:
        if not is_running():
            open_spotify()
            return "Voy a poner música. Espera un momento", MicAction.PLAY
        play()
        return "Reproduciendo música", MicAction.PLAY

    if any(w in c for w in ["pausa", "para la música", "detén la música", "silencio", "detener musica"]):
        pause()
        return "Música en pausa", MicAction.PAUSE

    if any(w in c for w in ["continúa", "sigue con la música", "reanuda"]):
        open_spotify()
        play()
        return "Sigo con la música", MicAction.CONTINUE

    if any(w in c for w in ["siguiente", "cambia canción", "salta a la siguiente", "adelante", "otra canción"]):
        next_track()
        return "Canción siguiente", MicAction.CONTINUE

    if any(w in c for w in ["anterior", "retrocede", "volver a la anterior"]):
        previous_track()
        return "Canción anterior", MicAction.CONTINUE

    if any(w in c for w in ["sube el volumen", "volumen más", "más alto", "ponlo más alto"]):
        volume_up()
        return "Volumen subido", MicAction.VOLUME_UP

    if any(w in c for w in ["baja el volumen", "volumen menos", "más bajo", "ponlo más bajo"]):
        volume_down()
        return "Volumen bajado", MicAction.VOLUME_DOWN

    if any(w in c for w in ["abre spotify", "abre la música", "abre spotify por favor",
                            "abre la app de música", "inicia spotify", "abre spotify ahora"]):
        open_spotify()
        return "Abriendo Spotify", MicAction.PLAY

    if any(w in c for w in ["cierra spotify", "saca la música", "apaga la música", "detener spotify"]):
        stop()
        return "Música detenida", MicAction.STOP

    # --- Búsqueda de canción / artista / playlist (lo último) ---
    if search_term:
        items = spotify_search_api(search_term)
        if items and items != "NO_CREDS":
            track = items[0]
            name = track.get("name") or search_term.title()
            artist = track["artists"][0]["name"] if track.get("artists") else ""
            play_uri(track["uri"])
            if artist:
                return f"Reproduciendo «{name}» de {artist}", MicAction.PLAY
            return f"Reproduciendo «{name}»", MicAction.PLAY
        search(search_term)
        return f"Sonando «{search_term.title()}» en Spotify", MicAction.PLAY

    return None, None

class MicAction:
    """Acciones de micrófono sugeridas (para textos de estado)"""
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    CONTINUE = "CONTINUE"
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    STOP = "STOP"
    REPEAT = "REPEAT"