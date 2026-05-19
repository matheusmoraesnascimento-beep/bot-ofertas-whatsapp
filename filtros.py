import csv
import os
import re
import unicodedata
from datetime import datetime, timedelta
from db import init_db, ja_enviado as _ja_enviado_db, ja_enviado_titulo as _ja_enviado_titulo_db, salvar_oferta as _salvar_db, migrar_csv

init_db()
migrar_csv()  # no-op se CSV não existir

HISTORICO_FILE = "ofertas_enviadas.csv"
CAMPOS = ["produto", "loja", "preco", "link", "data_envio"]

DEDUP_HORAS = int(os.getenv("DEDUP_HORAS", "48"))

BLACKLIST_KEYWORDS = [
    "gamer", "gaming", "mouse", "teclado", "headset", "monitor",
    "placa de video", "ssd", "hd interno", "hd externo",
    "xbox", "playstation", "ps4", "ps5", "controle joystick",
    "memoria ram", "processador",
]


def calcular_desconto(preco_atual, preco_antigo):
    if not preco_antigo or preco_antigo <= 0:
        return 0
    return round((1 - preco_atual / preco_antigo) * 100, 1)


def _normalizar_titulo(titulo: str) -> str:
    if not titulo:
        return ""
    t = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    palavras = t.split()[:8]
    return " ".join(palavras)


def _tem_blacklist(titulo: str) -> bool:
    t = (titulo or "").lower()
    return any(kw in t for kw in BLACKLIST_KEYWORDS)


MIN_RATING = 4.0
MIN_REVIEWS = 50


def _score_oferta(o):
    if o.get("preco_antigo") and o.get("preco_atual"):
        return o["preco_antigo"] - o["preco_atual"]
    return o.get("desconto_percentual", 0)


def _aplicar_filtros(ofertas, min_desc, max_desc, preco_max, checar_rating, checar_blacklist):
    cortes = {"sem_link_img": 0, "desconto_baixo": 0, "desconto_alto": 0, "preco_alto": 0, "rating_baixo": 0, "poucas_reviews": 0, "blacklist": 0}
    validas = []
    for o in ofertas:
        if not o.get("link_afiliado") or not o.get("imagem"):
            cortes["sem_link_img"] += 1
            continue
        if checar_blacklist and _tem_blacklist(o.get("produto", "")):
            cortes["blacklist"] += 1
            continue
        desc = o.get("desconto_percentual", 0)
        if min_desc is not None and desc < min_desc:
            cortes["desconto_baixo"] += 1
            continue
        if max_desc is not None and desc > max_desc:
            cortes["desconto_alto"] += 1
            continue
        if preco_max is not None and o.get("preco_atual", 0) > preco_max:
            cortes["preco_alto"] += 1
            continue
        if checar_rating and o.get("loja") == "Amazon":
            rating = o.get("rating")
            num_reviews = o.get("num_reviews")
            if rating is not None and rating < MIN_RATING:
                cortes["rating_baixo"] += 1
                continue
            if num_reviews is not None and num_reviews < MIN_REVIEWS:
                cortes["poucas_reviews"] += 1
                continue
        validas.append(o)
    return validas, cortes


def filtrar_melhores_ofertas(ofertas, min_desconto=None):
    import logging
    logger = logging.getLogger(__name__)
    from bot import MIN_DESCONTO
    min_desc = min_desconto if min_desconto is not None else MIN_DESCONTO
    max_desc = int(os.getenv("MAX_DESCONTO", "90"))
    preco_max = float(os.getenv("PRECO_MAX", "1000"))
    minimo_garantido = int(os.getenv("MIN_OFERTAS_GARANTIDAS", "5"))

    estagios = [
        ("estrito", dict(min_desc=min_desc, max_desc=max_desc, preco_max=preco_max, checar_rating=True, checar_blacklist=True)),
        ("medio",   dict(min_desc=max(min_desc // 2, 5), max_desc=None, preco_max=None, checar_rating=False, checar_blacklist=True)),
        ("frouxo",  dict(min_desc=1, max_desc=None, preco_max=None, checar_rating=False, checar_blacklist=True)),
        ("aberto",  dict(min_desc=None, max_desc=None, preco_max=None, checar_rating=False, checar_blacklist=True)),
        ("ultimo",  dict(min_desc=None, max_desc=None, preco_max=None, checar_rating=False, checar_blacklist=False)),
    ]

    validas = []
    for nome, params in estagios:
        validas, cortes = _aplicar_filtros(ofertas, **params)
        logger.info(f"Filtro [{nome}]: {len(validas)} válidas, cortes={cortes}")
        if len(validas) >= minimo_garantido:
            break

    validas.sort(key=_score_oferta, reverse=True)
    return validas


def remover_repetidas(ofertas):
    novas = []
    titulos_lote = set()
    for o in ofertas:
        link = o.get("link_afiliado", "")
        titulo_norm = _normalizar_titulo(o.get("produto", ""))
        if _ja_enviado_db(link, horas=DEDUP_HORAS):
            continue
        if titulo_norm and _ja_enviado_titulo_db(titulo_norm, horas=DEDUP_HORAS):
            continue
        if titulo_norm and titulo_norm in titulos_lote:
            continue
        titulos_lote.add(titulo_norm)
        o["_titulo_norm"] = titulo_norm
        novas.append(o)
    return novas


def salvar_em_historico(oferta):
    if "_titulo_norm" not in oferta:
        oferta["_titulo_norm"] = _normalizar_titulo(oferta.get("produto", ""))
    _salvar_db(oferta)
