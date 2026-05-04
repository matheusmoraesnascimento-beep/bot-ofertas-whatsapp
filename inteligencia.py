import os
from datetime import datetime
from db import preco_minimo_historico, registrar_preco


def _carregar_agenda() -> dict:
    raw = os.getenv("AGENDA_CATEGORIAS", "")
    agenda = {}
    for parte in raw.split(","):
        parte = parte.strip()
        if ":" not in parte:
            continue
        cat, horario = parte.rsplit(":", 1)
        if "-" in horario:
            h_ini, h_fim = horario.split("-")
            agenda[cat.strip().lower()] = (int(h_ini), int(h_fim))
    return agenda


def categoria_ativa(categoria: str) -> bool:
    agenda = _carregar_agenda()
    cat_key = categoria.lower()
    if cat_key not in agenda:
        return True
    h_ini, h_fim = agenda[cat_key]
    hora = datetime.now().hour
    if h_ini <= h_fim:
        return h_ini <= hora < h_fim
    return hora >= h_ini or hora < h_fim


def calcular_score(oferta: dict) -> float:
    preco_atual = oferta.get("preco_atual", 0)
    preco_antigo = oferta.get("preco_antigo")
    desconto = oferta.get("desconto_percentual", 0)
    rating = oferta.get("rating") or 4.0
    reviews = oferta.get("num_reviews") or 0

    economia = (preco_antigo - preco_atual) if preco_antigo else 0

    minimo = preco_minimo_historico(oferta.get("link_afiliado", ""))
    bonus_minimo = 1.3 if (minimo and preco_atual <= minimo * 1.05) else 1.0

    reviews_norm = min(reviews, 10000) / 10000

    score = (economia * 0.5 + desconto * 0.3 + rating * 5 + reviews_norm * 10) * bonus_minimo
    return round(score, 2)


def registrar_precos(ofertas: list):
    for o in ofertas:
        try:
            registrar_preco(o)
        except Exception:
            pass
