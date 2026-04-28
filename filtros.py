import csv
import os
from datetime import datetime, timedelta

HISTORICO_FILE = "ofertas_enviadas.csv"
CAMPOS = ["produto", "loja", "preco", "link", "data_envio"]


def calcular_desconto(preco_atual, preco_antigo):
    if not preco_antigo or preco_antigo <= 0:
        return 0
    return round((1 - preco_atual / preco_antigo) * 100, 1)


def _carregar_historico():
    if not os.path.exists(HISTORICO_FILE):
        return []
    with open(HISTORICO_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _ja_enviado(oferta, historico, horas=24):
    limite = datetime.now() - timedelta(hours=horas)
    for registro in historico:
        if registro["link"] == oferta["link_afiliado"]:
            try:
                data = datetime.fromisoformat(registro["data_envio"])
                if data > limite:
                    return True
            except ValueError:
                pass
    return False


def filtrar_melhores_ofertas(ofertas, min_desconto=None):
    from bot import MIN_DESCONTO
    min_desc = min_desconto if min_desconto is not None else MIN_DESCONTO

    validas = []
    for o in ofertas:
        if not o.get("link_afiliado") or not o.get("imagem"):
            continue
        desc = o.get("desconto_percentual", 0)
        if desc >= min_desc:
            validas.append(o)

    validas.sort(key=lambda x: x.get("desconto_percentual", 0), reverse=True)
    return validas


def remover_repetidas(ofertas):
    historico = _carregar_historico()
    return [o for o in ofertas if not _ja_enviado(o, historico)]


def salvar_em_historico(oferta):
    file_exists = os.path.exists(HISTORICO_FILE)
    with open(HISTORICO_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "produto": oferta.get("produto", ""),
            "loja": oferta.get("loja", ""),
            "preco": oferta.get("preco_atual", ""),
            "link": oferta.get("link_afiliado", ""),
            "data_envio": datetime.now().isoformat(),
        })
