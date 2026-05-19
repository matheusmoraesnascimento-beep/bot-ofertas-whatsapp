import os
import time
from playwright.sync_api import sync_playwright
import qrcode

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".whatsapp_session")


def main():
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = ctx.new_page()
        page.goto("https://web.whatsapp.com", timeout=60000)
        print("Aguardando QR...", flush=True)
        last = None
        for _ in range(120):
            try:
                el = page.locator("[data-ref]").first
                ref = el.get_attribute("data-ref", timeout=2000)
                if ref and ref != last:
                    last = ref
                    os.system("clear")
                    qr = qrcode.QRCode(border=1)
                    qr.add_data(ref)
                    qr.make()
                    qr.print_ascii(invert=True)
                    print("Escaneie no WhatsApp do celular (Configurações > Aparelhos conectados)", flush=True)
            except Exception:
                pass
            if page.locator('div[aria-label="Lista de conversas"]').count() > 0:
                print("\nLOGADO! Sessao salva.", flush=True)
                break
            time.sleep(3)
        ctx.close()


if __name__ == "__main__":
    main()
