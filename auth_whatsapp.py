import os
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

SESSION_DIR = os.path.join(os.path.dirname(__file__), ".whatsapp_session")

proxy_url = os.getenv("http_proxy") or os.getenv("HTTP_PROXY", "")
proxy_cfg = None
if proxy_url:
    p = urlparse(proxy_url)
    proxy_cfg = {
        "server": f"{p.scheme}://{p.hostname}:{p.port}",
        "username": p.username or "",
        "password": p.password or "",
    }

with sync_playwright() as pw:
    browser = pw.chromium.launch_persistent_context(
        user_data_dir=SESSION_DIR,
        headless=False,
        args=["--no-sandbox", "--start-minimized"],
        proxy=proxy_cfg,
    )
    page = browser.new_page()
    page.goto("https://web.whatsapp.com", timeout=60000)
    print("Escaneie o QR code. Aguardando login...")
    page.wait_for_selector('div[aria-label="Lista de conversas"]', timeout=300000)
    print("Login OK! Sessão salva. Pode fechar.")
    input("Pressione ENTER para fechar o browser...")
    browser.close()
