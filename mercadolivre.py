import os
import time
import logging
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)

ML_AFFILIATE_ID = os.getenv("ML_AFFILIATE_ID", "moma2385656")
ML_TOOL_ID = os.getenv("ML_TOOL_ID", "30629786")
ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "")
ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "")
ML_REFRESH_TOKEN = os.getenv("ML_REFRESH_TOKEN", "")

_token_cache = {"token": None, "expires_at": 0}


def _refresh_token() -> str | None:
    refresh = os.getenv("ML_REFRESH_TOKEN", ML_REFRESH_TOKEN)
    if not refresh or not ML_CLIENT_ID or not ML_CLIENT_SECRET:
        return None
    try:
        r = requests.post(
            "https://api.mercadolibre.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": ML_CLIENT_ID,
                "client_secret": ML_CLIENT_SECRET,
                "refresh_token": refresh,
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        from dotenv import set_key
        set_key("config.env", "ML_ACCESS_TOKEN", data["access_token"])
        set_key("config.env", "ML_REFRESH_TOKEN", data["refresh_token"])
        os.environ["ML_REFRESH_TOKEN"] = data["refresh_token"]
        os.environ["ML_ACCESS_TOKEN"] = data["access_token"]
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + data.get("expires_in", 21600) - 60
        return data["access_token"]
    except Exception as e:
        logger.error(f"ML refresh erro: {e}")
        return None


def _get_token() -> str | None:
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    static = os.getenv("ML_ACCESS_TOKEN", ML_ACCESS_TOKEN)
    if static:
        _token_cache["token"] = static
        _token_cache["expires_at"] = time.time() + 3600
        return static

    return _refresh_token()


def _link_afiliado(permalink: str) -> str:
    encoded = quote(permalink, safe="")
    return (
        f"https://www.mercadolivre.com.br/social/{ML_AFFILIATE_ID}"
        f"?matt_word={ML_AFFILIATE_ID}&matt_tool={ML_TOOL_ID}"
        f"&forceInApp=true&productURL={encoded}"
    )


def buscar_ofertas_mercadolivre(categoria: str) -> list:
    token = _get_token()
    if not token:
        logger.warning("ML: sem token, pulando")
        return []

    def _fazer_busca(tok):
        return requests.get(
            "https://api.mercadolibre.com/sites/MLB/search",
            params={"q": categoria, "sort": "relevance", "limit": 20, "condition": "new"},
            headers={"Authorization": f"Bearer {tok}"},
            timeout=15,
        )

    try:
        r = _fazer_busca(token)
        if r.status_code == 401:
            logger.info("ML: token expirado, renovando...")
            _token_cache["expires_at"] = 0
            novo = _refresh_token()
            if novo:
                r = _fazer_busca(novo)
        r.raise_for_status()
        resultados = r.json().get("results", [])
    except Exception as e:
        logger.error(f"ML request erro [{categoria}]: {e}")
        return []

    ofertas = []
    for item in resultados:
        try:
            preco_atual = float(item.get("price", 0))
            permalink = item.get("permalink", "")
            if not preco_atual or not permalink:
                continue

            preco_antigo = None
            desconto = 0.0
            original = item.get("original_price")
            if original and float(original) > preco_atual:
                preco_antigo = float(original)
                desconto = round((1 - preco_atual / preco_antigo) * 100, 1)

            imagem = item.get("thumbnail", "").replace("-I.jpg", "-O.jpg") or None

            ofertas.append({
                "produto": item.get("title", ""),
                "loja": "Mercado Livre",
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "desconto_percentual": desconto,
                "link_afiliado": _link_afiliado(permalink),
                "imagem": imagem,
                "categoria": categoria,
                "rating": None,
                "num_reviews": item.get("sold_quantity"),
            })
        except Exception as e:
            logger.debug(f"ML: erro item — {e}")
            continue

    logger.info(f"ML [{categoria}]: {len(ofertas)} produtos")
    return ofertas
