#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION_DIR="$DIR/.whatsapp_session"
LOG_FILE="$DIR/bot.log"

cd "$DIR"

# Remove singleton lock se sobrou de run anterior
rm -f "$SESSION_DIR/SingletonLock" "$SESSION_DIR/SingletonCookie" "$SESSION_DIR/SingletonSocket"

# Carrega proxy do bashrc
source ~/.bashrc 2>/dev/null || true

echo "$(date '+%Y-%m-%d %H:%M:%S') [CRON] Iniciando rodada" >> "$LOG_FILE"
xvfb-run --auto-servernum python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('config.env')
import bot
bot.executar_rodada()
" >> "$LOG_FILE" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') [CRON] Rodada concluída" >> "$LOG_FILE"
