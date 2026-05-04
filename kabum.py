import os
import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

logger = logging.getLogger(__name__)

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "")
KABUM_AFFILIATE_TAG = os.getenv("KABUM_AFFILIATE_TAG", "")


def _link_afiliado(url: str) -> str:
    if KABUM_AFFILIATE_TAG:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}utm_source=afiliados&utm_medium={KABUM_AFFILIATE_TAG}"
    return url


def buscar_ofertas_kabum(categoria: str) -> list:
    if not SCRAPERAPI_KEY:
        return []

    target = f"https://www.kabum.com.br/busca/{quote(categoria)}?sort=0"
    proxy_url = f"http://api.scraperapi.com?api_key={SCRAPERAPI_KEY}&url={quote(target)}&country_code=br"

    try:
        resp = requests.get(proxy_url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Kabum ScraperAPI erro [{categoria}]: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("article.productCard, div[data-testid='product-card']")

    if not cards:
        cards = soup.select("article[class*=Card], article[class*=card]")

    ofertas = []
    for card in cards[:20]:
        try:
            nome_el = card.select_one("span.nameCard, h2, [class*=name]")
            nome = nome_el.get_text(strip=True) if nome_el else None
            if not nome:
                continue

            link_el = card.select_one("a[href]")
            if not link_el:
                continue
            href = link_el.get("href", "")
            if not href.startswith("http"):
                href = "https://www.kabum.com.br" + href

            preco_el = card.select_one("[class*=priceCard], [class*=price]")
            if not preco_el:
                continue
            preco_txt = preco_el.get_text(strip=True)
            m = re.search(r"R?\$?\s*([\d.,]+)", preco_txt.replace(".", "").replace(",", "."))
            if not m:
                continue
            try:
                preco_atual = float(re.sub(r"[^\d.]", "", m.group(1)))
            except ValueError:
                continue

            preco_antigo = None
            antigo_el = card.select_one("[class*=oldPrice], [class*=old], s, del")
            if antigo_el:
                m2 = re.search(r"[\d.,]+", antigo_el.get_text().replace(".", "").replace(",", "."))
                if m2:
                    try:
                        preco_antigo = float(re.sub(r"[^\d.]", "", m2.group()))
                        if preco_antigo <= preco_atual:
                            preco_antigo = None
                    except ValueError:
                        preco_antigo = None

            desconto = 0.0
            if preco_antigo:
                desconto = round((1 - preco_atual / preco_antigo) * 100, 1)

            img_el = card.select_one("img")
            imagem = img_el.get("src") or img_el.get("data-src") if img_el else None

            ofertas.append({
                "produto": nome,
                "loja": "Kabum",
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "desconto_percentual": desconto,
                "link_afiliado": _link_afiliado(href),
                "imagem": imagem,
                "categoria": categoria,
                "rating": None,
                "num_reviews": None,
            })
        except Exception as e:
            logger.debug(f"Kabum: erro card — {e}")
            continue

    logger.info(f"Kabum [{categoria}]: {len(ofertas)} produtos")
    return ofertas
