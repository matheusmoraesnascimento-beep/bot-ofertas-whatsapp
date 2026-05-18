#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$DIR/bot.log"
SESSION_DIR="$DIR/.whatsapp_session"

cd "$DIR"

# Remove singleton lock do Chromium se sobrou
rm -f "$SESSION_DIR/SingletonLock" "$SESSION_DIR/SingletonCookie" "$SESSION_DIR/SingletonSocket"

# Autentica WhatsApp se sessão não existe
if [ ! -d "$SESSION_DIR/Default" ]; then
    echo "Sessão WhatsApp não encontrada. Abrindo QR code..."
    python3 auth_whatsapp.py
    echo ""
fi

echo "Rodando agora..."
xvfb-run --auto-servernum python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('config.env')
import bot
bot.executar_rodada()
" 2>&1 | tee -a "$LOG_FILE"

echo ""
echo "Concluído. Próximas rodadas via cron: 07h e 18h todo dia."
echo "Logs: tail -f $LOG_FILE"
