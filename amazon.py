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
        texto_original = texto.lower()

        # 1. BLOQUEIO CRÍTICO: Se contiver barra ou unidades de medida no texto do preço, 
        # ignoramos, pois a Amazon coloca o preço por unidade/kg/litro nesse formato.
        indicadores_unidade = ["/", "kg", " g", "ml", "litro", "unidade", "oz"]
        if any(ind in texto_original for ind in indicadores_unidade):
            return None

        # 2. Remove qualquer coisa entre parênteses
        texto = re.sub(r"\(.*?\)", "", texto)

        # 3. Se houver múltiplos "R$", pega apenas o primeiro bloco
        if "R$" in texto:
            partes = texto.split("R$")
            for p in partes:
                if any(char.isdigit() for char in p):
                    p_limpo = re.sub(r"[^\d,.]", "", p)
                    if p_limpo:
                        texto = p
                        break


        # Remove símbolos e espaços, mantendo apenas dígitos, vírgulas e pontos
        texto_limpo = re.sub(r"[^\d,.]", "", texto)
        
        if not texto_limpo:
            return None
            
        # Tenta detectar se o texto está duplicado (ex: "10,0010,00")
        meio = len(texto_limpo) // 2
        if len(texto_limpo) > 4 and texto_limpo[:meio] == texto_limpo[meio:]:
            texto_limpo = texto_limpo[:meio]

        # Lógica para decidir separador decimal
        if "," in texto_limpo and "." in texto_limpo:
            if texto_limpo.rfind(",") > texto_limpo.rfind("."):
                # Formato BR: 1.299,00
                final = texto_limpo.replace(".", "").replace(",", ".")
            else:
                # Formato US: 1,299.00
                final = texto_limpo.replace(",", "")
        elif "," in texto_limpo:
            # Apenas vírgula: 12,99
            final = texto_limpo.replace(",", ".")
        elif "." in texto_limpo:
            partes = texto_limpo.split(".")
            # Se tiver mais de um ponto, é separador de milhar: 1.299.000
            if len(partes) > 2:
                final = texto_limpo.replace(".", "")
            # Se o último bloco tiver 2 dígitos, provavelmente é decimal US: 12.99
            elif len(partes[-1]) == 2:
                final = texto_limpo
            # Caso contrário, assume-se milhar: 1.299
            else:
                final = texto_limpo.replace(".", "")
        else:
            final = texto_limpo

        return float(final)
    except Exception as e:
        logger.debug(f"Erro ao extrair preço '{texto}': {e}")
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

            # 1. Tenta pegar a porcentagem de desconto direta (ex: -15%)
            # Amazon costuma usar classes como 'savingsPercentage' ou texto com '-' e '%'
            desconto_direto = 0.0
            perc_el = card.select_one("span[class*='savingsPercentage'], .a-color-price")
            if perc_el:
                texto_perc = perc_el.get_text().strip()
                m = re.search(r"-?(\d+)%", texto_perc)
                if m:
                    desconto_direto = float(m.group(1))

            # 2. Preço Atual — exclui secundário (por unidade) e riscado (De:)
            preco_el = card.select_one(
                ".a-price:not([data-a-color='secondary']):not([data-a-strike='true']) span.a-offscreen"
            )
            preco_atual = _extrair_preco(preco_el.get_text() if preco_el else None)

            if not preco_atual:
                continue

            # 3. Preço Antigo — somente o "De:" riscado (data-a-strike="true")
            preco_antigo_el = card.select_one("span.a-price[data-a-strike='true'] span.a-offscreen")
            preco_antigo = _extrair_preco(preco_antigo_el.get_text() if preco_antigo_el else None)

            # Sanidade: antigo deve ser maior que atual e não absurdo (>10x)
            if preco_antigo and (preco_antigo <= preco_atual or preco_antigo > preco_atual * 10):
                preco_antigo = None

            # 4. Lógica de decisão de desconto
            desconto = 0.0
            if desconto_direto > 0:
                desconto = desconto_direto
                # Se temos o desconto real, calculamos o preço antigo correto se o capturado estiver errado
                # (ex: se o capturado for o preço por kg, recalculamos o correto baseado no atual)
                if not preco_antigo or abs((1 - preco_atual/preco_antigo)*100 - desconto) > 10:
                    preco_antigo = round(preco_atual / (1 - desconto / 100), 2)
            elif preco_antigo and preco_antigo > preco_atual:
                desconto = round((1 - preco_atual / preco_antigo) * 100, 1)

            # Trava final de segurança para evitar erros de unidade
            if desconto > 80:
                logger.debug(f"Amazon: Desconto de {desconto}% ignorado por ser irreal em '{titulo}'")
                continue

            img_el = card.select_one("img.s-image")
            imagem = img_el.get("src") if img_el else None

            # Rating (estrelas)
            rating = None
            rating_el = card.select_one("i.a-icon-star-small span.a-icon-alt, i.a-icon-star span.a-icon-alt")
            if rating_el:
                m = re.search(r"([\d,\.]+)\s*de\s*5", rating_el.get_text())
                if m:
                    try:
                        rating = float(m.group(1).replace(",", "."))
                    except ValueError:
                        rating = None

            # Número de avaliações
            num_reviews = None
            reviews_el = card.select_one("span.a-size-base.s-underline-text, a[aria-label*='avaliações'] span")
            if reviews_el:
                txt = reviews_el.get_text(strip=True).replace(".", "").replace(",", "")
                m = re.search(r"\d+", txt)
                if m:
                    try:
                        num_reviews = int(m.group(0))
                    except ValueError:
                        num_reviews = None

            ofertas.append({
                "produto": titulo,
                "loja": "Amazon",
                "preco_atual": preco_atual,
                "preco_antigo": preco_antigo,
                "desconto_percentual": desconto,
                "link_afiliado": _montar_link(asin),
                "imagem": imagem,
                "categoria": categoria,
                "rating": rating,
                "num_reviews": num_reviews,
            })
        except Exception as e:
            logger.debug(f"Amazon: erro card — {e}")
            continue

    logger.info(f"Amazon [{categoria}]: {len(ofertas)} produtos")
    return ofertas
