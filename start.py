import subprocess
import sys
import os
import base64
import zipfile
import io

SESSION_DIR = os.path.join(os.path.dirname(__file__), ".whatsapp_session")


def _restaurar_sessao():
    b64 = os.getenv("WHATSAPP_SESSION_B64", "")
    if not b64:
        return
    if os.path.isdir(SESSION_DIR) and os.listdir(SESSION_DIR):
        print("[start] Sessão já existe localmente, pulando restauração.")
        return
    print("[start] Restaurando sessão WhatsApp do env var...")
    try:
        data = base64.b64decode(b64)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(os.path.dirname(SESSION_DIR))
        print(f"[start] Sessão restaurada em {SESSION_DIR}")
    except Exception as e:
        print(f"[start] ERRO ao restaurar sessão: {e}")


_restaurar_sessao()

bot = subprocess.Popen([sys.executable, "bot.py"])
painel = subprocess.Popen([sys.executable, "-m", "painel.app"])

try:
    bot.wait()
except KeyboardInterrupt:
    bot.terminate()
    painel.terminate()
