import os
import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "")
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")


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
    if not SCRAPERAPI_KEY:
        logger.error("Amazon: SCRAPERAPI_KEY não configurado")
        return []
    if not ASSOCIATE_TAG:
        logger.warning("Amazon: AMAZON_ASSOCIATE_TAG não configurado")

    target = f"https://www.amazon.com.br/s?k={categoria.replace(' ', '+')}&sort=review-rank"
    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={target}&country_code=br"

    try:
        resp = requests.get(proxy_url, timeout=60)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.error(f"Amazon ScraperAPI erro [{categoria}]: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div[data-asin][data-component-type='s-search-result']")

    ofertas = []
    for card in cards[:20]:
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
