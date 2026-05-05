import os
import re
import json
import logging
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)

ML_AFFILIATE_ID = os.getenv("ML_AFFILIATE_ID", "moma2385656")
ML_TOOL_ID = os.getenv("ML_TOOL_ID", "30629786")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _link_afiliado(permalink: str) -> str:
    encoded = quote(permalink, safe="")
    return (
        f"https://www.mercadolivre.com.br/social/{ML_AFFILIATE_ID}"
        f"?matt_word={ML_AFFILIATE_ID}&matt_tool={ML_TOOL_ID}"
        f"&forceInApp=true&productURL={encoded}"
    )


def _imagem_url(picture_id: str) -> str | None:
    if not picture_id:
        return None
    return f"https://http2.mlstatic.com/D_NQ_NP_{picture_id}-O.webp"


def _extrair_items(html: str) -> list:
    idx = html.find('"items":')
    if idx < 0:
        return []
    try:
        items, _ = json.JSONDecoder().raw_decode(html[idx + len('"items":'):])
        return items if isinstance(items, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def buscar_ofertas_mercadolivre(categoria: str) -> list:
    try:
        resp = requests.get(
            "https://www.mercadolivre.com.br/ofertas",
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"ML request erro: {e}")
        return []

    items = _extrair_items(resp.text)
    if not items:
        logger.warning("ML: nenhum item extraído do JSON da página de ofertas")
        return []

    ofertas = []
    for item in items:
        try:
            card = item.get("card", {})
            meta = card.get("metadata", {})
            components = {c["type"]: c for c in card.get("components", [])}

            title_data = components.get("title", {}).get("title", {})
            nome = title_data.get("text", "")
            if not nome:
                continue

            url = meta.get("url", "")
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://" + url

            price_data = components.get("price", {}).get("price", {})
            preco_atual = price_data.get("current_price", {}).get("value")
            if not preco_atual:
                continue

            preco_anterior = price_data.get("previous_price", {}).get("value")
            preco_antigo = preco_anterior if preco_anterior and preco_anterior > preco_atual else None

            desconto = float(price_data.get("discount", {}).get("value", 0) or 0)
            if not desconto and preco_antigo:
                desconto = round((1 - preco_atual / preco_antigo) * 100, 1)

            reviews_data = components.get("reviews", {}).get("reviews", {})
            rating = reviews_data.get("rating_average")
            num_reviews = reviews_data.get("total")

            pictures = card.get("pictures", {}).get("pictures", [])
            pic_id = pictures[0].get("id") if pictures else None
            imagem = _imagem_url(pic_id)

            # filtra por categoria: verifica se nome contém palavra da categoria
            palavras = [p.lower() for p in categoria.split() if len(p) > 3]
            if palavras and not any(p in nome.lower() for p in palavras):
                continue

            ofertas.append({
                "produto": nome,
                "loja": "Mercado Livre",
                "preco_atual": float(preco_atual),
                "preco_antigo": float(preco_antigo) if preco_antigo else None,
                "desconto_percentual": desconto,
                "link_afiliado": _link_afiliado(url),
                "imagem": imagem,
                "categoria": categoria,
                "rating": rating,
                "num_reviews": num_reviews,
            })
        except Exception as e:
            logger.debug(f"ML: erro item — {e}")
            continue

    logger.info(f"ML [{categoria}]: {len(ofertas)} produtos")
    return ofertas
