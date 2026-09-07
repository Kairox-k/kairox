#!/usr/bin/env bash
# Lanzador de Kairox: fija el nivel del micrófono y abre la aplicación
cd /home/jhon/voice_assistant

# Nivel de micrófono óptimo para la escucha de Kairox.
# Un valor alto (55%+) satura la entrada con ruido ambiente y Kairox no entiende la voz.
# A ~20% el piso de ruido es limpio y la voz se reconoce bien.
pactl set-source-volume @DEFAULT_SOURCE@ 20% 2>/dev/null

# Lanzar Kairox: si una instancia previa quedó colgada/congelada, se cierra
# y se abre una nueva (evita que -verificando con pgrep- se quede sin abrir).
pkill -f "assistant_gui.py" 2>/dev/null
sleep 1

exec python3 /home/jhon/voice_assistant/assistant_gui.py