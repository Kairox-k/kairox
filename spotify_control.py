#!/usr/bin/env python3
"""
Control de Spotify para Kairox
Usa playerctl (MPRIS) para reproducir/pausar/navegar canciones
y abre el cliente de Spotify si no está corriendo.
"""

import subprocess
import shutil

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
    return _playerctl(["loop", "Playlist"])

def repeat_track():
    """Repite la canción actual"""
    if not is_running():
        open_spotify()
    return _playerctl(["loop", "Track"])

def repeat_off():
    """Desactiva la repetición"""
    return _playerctl(["loop", "None"])

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

    # Repetición primero (para que "play" dentro de "playlist" no te engañe)
    if any(w in c for w in ["repite la playlist", "repite la lista", "repetir playlist",
                            "repetir la lista", "repetición de lista", "modo repetición",
                            "repite todo", "repetición de playlist"]):
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

    if any(w in c for w in ["pon musica", "pon la música", "play", "reproduce música",
                            "reproducir", "dale música", "inicia música", "pón música"]) and \
       not any(w in c for w in ["repite", "repetir"]):
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

    if any(w in c for w in ["cierra spotify", "saca la música", "apaga la música", "detener spotify"]):
        stop()
        return "Música detenida", MicAction.STOP

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