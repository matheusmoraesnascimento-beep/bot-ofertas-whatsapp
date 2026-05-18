import os
import time
import hmac
import hashlib
import logging
import requests

logger = logging.getLogger(__name__)

APP_ID = os.getenv("SHOPEE_APP_ID", "")
SECRET = os.getenv("SHOPEE_SECRET", "")
AFFILIATE_ID = os.getenv("SHOPEE_AFFILIATE_ID", "")
BASE_URL = "https://open-api.affiliate.shopee.com.br/graphql"


def _assinar(payload: str) -> str:
    ts = str(int(time.time()))
    msg = APP_ID + ts + payload + SECRET
    sig = hmac.new(SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return ts, sig


def _headers(payload: str) -> dict:
    ts, sig = _assinar(payload)
    return {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 appid={APP_ID},timestamp={ts},sign={sig}",
    }


def buscar_ofertas_shopee(categoria):
    if not APP_ID or not SECRET:
        logger.warning("Shopee: credenciais não configuradas, pulando")
        return []

    query = """
    {
      productOffer(
        listType: 0,
        sortType: 2,
        page: 1,
        limit: 5,
        keyword: "%s"
      ) {
        nodes {
          productName
          priceMin
          priceMax
          commissionRate
          sales
          imageUrl
          productLink
          offerLink
          ratingStar
          priceDiscountRate
        }
        pageInfo { hasNextPage }
      }
    }
    """ % categoria.replace('"', '')

    payload = '{"query": ' + repr(query) + '}'

    try:
        resp = requests.post(
            BASE_URL,
            data=payload,
            headers=_headers(payload),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        nodes = (
            data.get("data", {})
            .get("productOffer", {})
            .get("nodes", [])
        )

        ofertas = []
        for node in nodes:
            try:
                preco_raw = node.get("priceMin")
                if not preco_raw:
                    continue
                
                # Shopee API retorna preços multiplicados por 100.000 (unidades micro)
                preco_atual = float(preco_raw) / 100000

                desconto_raw = node.get("priceDiscountRate", 0)
                # priceDiscountRate costuma vir como inteiro (ex: 15 para 15%)
                # Se vier como float (ex: 0.15), multiplicamos por 100
                desconto = float(desconto_raw)
                if 0 < desconto < 1:
                    desconto = round(desconto * 100, 1)
                else:
                    desconto = round(desconto, 1)

                preco_antigo = None
                if desconto > 0:
                    preco_antigo = round(preco_atual / (1 - desconto / 100), 2)

                link = node.get("offerLink") or node.get("productLink")
                if not link:
                    continue

                ofertas.append({
                    "produto": node.get("productName", ""),
                    "loja": "Shopee",
                    "preco_atual": preco_atual,
                    "preco_antigo": preco_antigo,
                    "desconto_percentual": desconto,
                    "link_afiliado": link,
                    "imagem": node.get("imageUrl"),
                    "categoria": categoria,
                })
            except Exception as e:
                logger.debug(f"Shopee: erro ao processar node — {e}")
                continue

        logger.info(f"Shopee [{categoria}]: {len(ofertas)} ofertas encontradas")
        return ofertas

    except requests.RequestException as e:
        logger.error(f"Shopee request erro [{categoria}]: {e}")
        return []
    except Exception as e:
        logger.error(f"Shopee erro inesperado [{categoria}]: {e}")
        return []
