#!/bin/bash
# Setup PC local + GitHub Pages (free, atrás de proxy corporativo)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=== Setup bot grátis (PC local + GitHub Pages) ==="

# 1. xvfb (Playwright headed)
if ! command -v xvfb-run &>/dev/null; then
    echo "[1/3] Instalando xvfb..."
    sudo apt-get install -y xvfb
else
    echo "[1/3] xvfb ok"
fi

# 2. systemd user service do bot
echo "[2/3] Criando systemd user service..."
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/bot-ofertas.service <<EOF
[Unit]
Description=Bot Ofertas WhatsApp
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$DIR
EnvironmentFile=-$HOME/.proxy.env
ExecStart=/usr/bin/xvfb-run --auto-servernum /usr/bin/python3 start.py
Restart=on-failure
RestartSec=10
StandardOutput=append:$DIR/bot.log
StandardError=append:$DIR/bot.log

[Install]
WantedBy=default.target
EOF

# Salva proxy atual em arquivo herdado pelo service
cat > "$HOME/.proxy.env" <<EOF
HTTP_PROXY=$http_proxy
HTTPS_PROXY=$https_proxy
http_proxy=$http_proxy
https_proxy=$https_proxy
NO_PROXY=$no_proxy
no_proxy=$no_proxy
EOF
chmod 600 "$HOME/.proxy.env"

systemctl --user daemon-reload

# 3. Linger (services rodam sem login ativo)
echo "[3/3] Habilitando linger..."
sudo loginctl enable-linger "$USER"

echo ""
echo "=== Pronto! Próximos passos ==="
echo ""
echo "1. Ajuste BASE_URL no config.env:"
echo "   BASE_URL=https://ofertasrelampagobot.com.br"
echo ""
echo "2. Habilite GitHub Pages no repo (uma vez):"
echo "   gh api repos/matheusmoraesnascimento-beep/bot-ofertas-whatsapp/pages \\"
echo "     -X POST -f source[branch]=master -f source[path]=/docs"
echo ""
echo "3. Inicie o bot:"
echo "   systemctl --user enable --now bot-ofertas"
echo ""
echo "4. Verifique:"
echo "   systemctl --user status bot-ofertas"
echo "   tail -f bot.log"
