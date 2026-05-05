"""
Gera tokens OAuth do Mercado Livre.
Uso: python3 ml_auth.py
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv("config.env")

CLIENT_ID = os.getenv("ML_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")
REDIRECT_URI = "https://webhook.site/701c8460-33c5-4792-bc52-d247446dde04"

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERRO: ML_CLIENT_ID e ML_CLIENT_SECRET precisam estar em config.env")
    sys.exit(1)

auth_url = (
    f"https://auth.mercadolivre.com.br/authorization"
    f"?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
)

print("\n1. Abra este link no browser e autorize o app:")
print(f"\n   {auth_url}\n")
print("2. Após autorizar, o browser vai redirecionar para uma URL tipo:")
print("   https://localhost/?code=TG-XXXXXXXXX-XXXXXXXXX\n")

code = input("3. Cole aqui o valor do 'code' da URL: ").strip()
if not code:
    print("ERRO: código vazio")
    sys.exit(1)

r = requests.post(
    "https://api.mercadolibre.com/oauth/token",
    data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    },
    timeout=15,
)

if r.status_code != 200:
    print(f"ERRO {r.status_code}: {r.text}")
    sys.exit(1)

data = r.json()
access_token = data.get("access_token", "")
refresh_token = data.get("refresh_token", "")

print("\n✅ Tokens obtidos com sucesso!\n")
print("Adicione no Railway estas variáveis:")
print(f"  ML_ACCESS_TOKEN={access_token}")
print(f"  ML_REFRESH_TOKEN={refresh_token}")
print("\nO refresh_token é o mais importante — o bot usa ele para renovar automaticamente.")
