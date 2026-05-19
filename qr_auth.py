import os
import time
from playwright.sync_api import sync_playwright
import qrcode

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".whatsapp_session")
HEADLESS = os.getenv("QR_HEADLESS", "false").lower() == "true"


def render_qr(ref: str):
    os.system("clear")
    qr = qrcode.QRCode(border=1)
    qr.add_data(ref)
    qr.make()
    qr.print_ascii(invert=True)
    print(f"\nScaneie no celular (WhatsApp > Aparelhos conectados > Conectar)", flush=True)


def main():
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()
        page.goto("https://web.whatsapp.com", timeout=60000)
        print("Pagina carregada. Procurando QR...", flush=True)
        last = None
        already_logged = False
        for i in range(120):
            try:
                if page.locator('div[aria-label="Lista de conversas"], div[aria-label="Chats"]').count() > 0:
                    print("\nLOGADO! Sessao salva em .whatsapp_session/", flush=True)
                    already_logged = True
                    break
            except Exception:
                pass
            try:
                refs = page.locator("[data-ref]").all()
                ref = None
                for el in refs:
                    try:
                        v = el.get_attribute("data-ref", timeout=500)
                        if v:
                            ref = v
                            break
                    except Exception:
                        continue
                if ref and ref != last:
                    last = ref
                    render_qr(ref)
            except Exception:
                pass
            if i % 10 == 0:
                try:
                    page.screenshot(path="/tmp/wa_debug.png", full_page=False)
                except Exception:
                    pass
                print(f"[debug] iteracao {i} url={page.url[:80]}", flush=True)
            time.sleep(3)
        if not already_logged:
            print("\nTimeout. Veja /tmp/wa_debug.png pelo SCP/console.", flush=True)
        ctx.close()


if __name__ == "__main__":
    main()
