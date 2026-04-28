import os
import time
import random
import logging
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "")


def _montar_link(asin: str) -> str:
    base = f"https://www.amazon.com.br/dp/{asin}"
    return f"{base}?tag={ASSOCIATE_TAG}" if ASSOCIATE_TAG else base


def _extrair_preco(texto: str):
    if not texto:
        return None
    try:
        limpo = texto.replace("R$", "").replace("\xa0", "").replace(".", "").replace(",", ".").strip()
        return float(limpo)
    except ValueError:
        return None


def buscar_ofertas_amazon(categoria: str) -> list:
    if not ASSOCIATE_TAG:
        logger.warning("Amazon: AMAZON_ASSOCIATE_TAG não configurado")

    url = f"https://www.amazon.com.br/s?k={categoria.replace(' ', '+')}&sort=review-rank"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"Accept-Language": "pt-BR,pt;q=0.9"})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))
            html = page.content()
            browser.close()
    except Exception as e:
        logger.error(f"Amazon Playwright erro [{categoria}]: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div[data-asin][data-component-type='s-search-result']")

    ofertas = []
    for card in cards[:10]:
        try:
            asin = card.get("data-asin", "").strip()
            if not asin:
                continue

            titulo_el = card.select_one("h2 span")
            titulo = titulo_el.get_text(strip=True) if titulo_el else None
            if not titulo:
                continue

            preco_el = card.select_one("span.a-price > span.a-offscreen")
            preco_atual = _extrair_preco(preco_el.get_text() if preco_el else None)
            if not preco_atual:
                continue

            preco_antigo_el = card.select_one("span.a-price.a-text-price > span.a-offscreen")
            preco_antigo = _extrair_preco(preco_antigo_el.get_text() if preco_antigo_el else None)

            desconto = 0.0
            if preco_antigo and preco_antigo > preco_atual:
                desconto = round((1 - preco_atual / preco_antigo) * 100, 1)
            else:
                badge_el = card.select_one("span.a-badge-label")
                if badge_el:
                    m = re.search(r"(\d+)%", badge_el.get_text())
                    if m:
                        desconto = float(m.group(1))
                        if not preco_antigo:
                            preco_antigo = round(preco_atual / (1 - desconto / 100), 2)

            img_el = card.select_one("img.s-image")
            imagem = img_el.get("src") if img_el else None

            ofertas.append({
                "produto": titulo,
                "loja": "Amazon",
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "desconto_percentual": desconto,
                "link_afiliado": _montar_link(asin),
                "imagem": imagem,
                "categoria": categoria,
            })
        except Exception as e:
            logger.debug(f"Amazon: erro card — {e}")
            continue

    logger.info(f"Amazon [{categoria}]: {len(ofertas)} produtos")
    return ofertas
