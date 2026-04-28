import os
import time
import logging
import random
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME", "")
SESSION_DIR = os.path.join(os.path.dirname(__file__), ".whatsapp_session")


def _delay():
    time.sleep(random.uniform(3, 7))


def enviar_para_grupo_whatsapp(mensagem: str):
    if not GROUP_NAME:
        logger.error("WhatsApp: WHATSAPP_GROUP_NAME não configurado")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            args=["--no-sandbox"],
        )
        page = browser.new_page()

        try:
            page.goto("https://web.whatsapp.com", timeout=60000)
            logger.info("WhatsApp Web aberto. Aguardando carregamento...")

            # Aguarda QR scan na primeira vez ou session load
            page.wait_for_selector('div[aria-label="Lista de conversas"]', timeout=90000)
            logger.info("WhatsApp Web carregado")

            _abrir_grupo(page, GROUP_NAME)
            _enviar_mensagem(page, mensagem)
            logger.info(f"Mensagem enviada para grupo '{GROUP_NAME}'")
            _delay()
            return True

        except PlaywrightTimeout as e:
            logger.error(f"WhatsApp timeout: {e}")
            return False
        except Exception as e:
            logger.error(f"WhatsApp erro: {e}")
            return False
        finally:
            browser.close()


def _abrir_grupo(page, nome_grupo: str):
    try:
        # Tenta primeiro pelo título exato
        resultado = page.locator(f'span[title="{nome_grupo}"]').first
        if resultado.count() > 0:
            resultado.click()
            _delay()
            logger.info(f"Grupo '{nome_grupo}' aberto por título")
            return

        # Fallback: busca pelo campo de pesquisa
        caixa_busca = page.locator('[data-tab="3"][contenteditable="true"], [data-testid="chat-list-search"]').first
        caixa_busca.click()
        _delay()
        caixa_busca.fill(nome_grupo)
        _delay()

        # Aguarda resultado e clica no primeiro
        resultado = page.locator(f'span[title="{nome_grupo}"]').first
        resultado.wait_for(timeout=15000)
        resultado.click()
        _delay()
        logger.info(f"Grupo '{nome_grupo}' aberto via busca")

    except Exception as e:
        raise RuntimeError(f"Não foi possível abrir grupo '{nome_grupo}': {e}")


def _enviar_mensagem(page, mensagem: str):
    try:
        caixa = page.locator('div[contenteditable="true"][data-tab="10"]')
        caixa.wait_for(timeout=10000)
        caixa.click()

        # Insere linha por linha para preservar quebras
        linhas = mensagem.split("\n")
        for i, linha in enumerate(linhas):
            caixa.type(linha, delay=30)
            if i < len(linhas) - 1:
                page.keyboard.press("Shift+Enter")

        _delay()
        page.keyboard.press("Enter")
        _delay()

    except Exception as e:
        raise RuntimeError(f"Erro ao enviar mensagem: {e}")
