#!/usr/bin/env bash
# Lanzador de Kairox: fija el nivel del micrófono y abre la aplicación
cd /home/jhon/voice_assistant

# Nivel de micrófono óptimo para la escucha de Kairox
pactl set-source-volume @DEFAULT_SOURCE@ 55% 2>/dev/null

# Lanzar Kairox (si ya estaba abierto, llevarlo al frente)
if pgrep -f "assistant_gui.py" > /dev/null 2>&1; then
    exit 0
fi

exec python3 /home/jhon/voice_assistant/assistant_gui.py