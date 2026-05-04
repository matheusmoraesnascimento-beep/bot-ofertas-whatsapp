import os
import sys
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Fix encoding para Windows (emojis na mensagem)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv("config.env")

# Config
MIN_DESCONTO = int(os.getenv("MIN_DESCONTO", "20"))
MAX_OFERTAS_POR_RODADA = int(os.getenv("MAX_OFERTAS_POR_RODADA", "5"))
INTERVALO_ENTRE_POSTS = int(os.getenv("INTERVALO_ENTRE_POSTS", "60"))
RODAR_A_CADA_MINUTOS = int(os.getenv("RODAR_A_CADA_MINUTOS", "30"))
HORA_INICIO = int(os.getenv("HORA_INICIO", "8"))
HORA_FIM = int(os.getenv("HORA_FIM", "22"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from amazon import buscar_ofertas_amazon
from shopee import buscar_ofertas_shopee
from mercadolivre import buscar_ofertas_mercadolivre
from filtros import filtrar_melhores_ofertas, remover_repetidas, salvar_em_historico
from painel.state import salvar_estado, esta_pausado, consumir_forca
from inteligencia import calcular_score, categoria_ativa, registrar_precos

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

def enviar_para_grupo_whatsapp(mensagem: str, imagem_url: str = None) -> bool:
    if DRY_RUN:
        print("\n" + "="*50)
        print(mensagem)
        if imagem_url:
            print(f"[IMAGEM: {imagem_url}]")
        print("="*50 + "\n")
        return True
    from whatsapp import enviar_para_grupo_whatsapp as _enviar
    return _enviar(mensagem, imagem_url=imagem_url)


def ler_categorias(arquivo="categorias.txt"):
    try:
        with open(arquivo, encoding="utf-8") as f:
            return [linha.strip() for linha in f if linha.strip()]
    except FileNotFoundError:
        logger.error(f"Arquivo {arquivo} não encontrado")
        return []


def montar_mensagem(oferta: dict) -> str:
    preco_atual = oferta["preco_atual"]
    preco_antigo = oferta.get("preco_antigo")
    desconto = oferta.get("desconto_percentual", 0)

    # Headline com economia em R$
    if preco_antigo:
        economia = preco_antigo - preco_atual
        headline = f"🔥 BAIXOU R$ {economia:.2f} (-{desconto:.0f}%)"
    else:
        headline = f"🔥 OFERTA -{desconto:.0f}%"

    linhas = [headline, "", f"🛍️ {oferta['produto']}"]

    # Prova social: rating + reviews
    rating = oferta.get("rating")
    num_reviews = oferta.get("num_reviews")
    if rating and num_reviews:
        if num_reviews >= 1000:
            reviews_fmt = f"{num_reviews/1000:.1f}k"
        else:
            reviews_fmt = str(num_reviews)
        linhas.append(f"⭐ {rating:.1f} ({reviews_fmt} avaliações)")

    linhas.append("")
    if preco_antigo:
        linhas.append(f"❌ De: R$ {preco_antigo:.2f}")
    linhas.append(f"✅ Por: R$ {preco_atual:.2f}")
    if preco_antigo:
        linhas.append(f"💸 Você economiza R$ {preco_antigo - preco_atual:.2f}")

    linhas.extend([
        "",
        f"👉 {oferta['link_afiliado']}",
        "",
        "⏰ Estoque limitado — preço pode mudar.",
    ])

    return "\n".join(linhas)


def dentro_da_janela() -> bool:
    hora = datetime.now().hour
    if HORA_INICIO <= HORA_FIM:
        return HORA_INICIO <= hora < HORA_FIM
    # janela atravessa meia-noite (ex: 20-6)
    return hora >= HORA_INICIO or hora < HORA_FIM


def executar_rodada():
    salvar_estado("rodando")
    logger.info("=== Iniciando rodada de busca ===")
    categorias = ler_categorias()

    if not categorias:
        logger.warning("Nenhuma categoria encontrada")
        return

    ofertas = []
    for categoria in categorias:
        if not categoria_ativa(categoria):
            logger.info(f"Pulando {categoria} (fora da janela da categoria)")
            continue
        logger.info(f"Buscando: {categoria}")
        try:
            ofertas.extend(buscar_ofertas_amazon(categoria))
        except Exception as e:
            logger.error(f"Amazon falhou [{categoria}]: {e}")
        try:
            ofertas.extend(buscar_ofertas_shopee(categoria))
        except Exception as e:
            logger.error(f"Shopee falhou [{categoria}]: {e}")
        try:
            ofertas.extend(buscar_ofertas_mercadolivre(categoria))
        except Exception as e:
            logger.error(f"ML falhou [{categoria}]: {e}")

    logger.info(f"Total bruto: {len(ofertas)} ofertas")

    registrar_precos(ofertas)
    filtradas = filtrar_melhores_ofertas(ofertas, MIN_DESCONTO)
    logger.info(f"Após filtro desconto: {len(filtradas)}")

    for o in filtradas:
        o["_score"] = calcular_score(o)
    filtradas.sort(key=lambda o: o["_score"], reverse=True)

    novas = remover_repetidas(filtradas)
    logger.info(f"Após dedup 24h: {len(novas)} — enviando até {MAX_OFERTAS_POR_RODADA}")

    enviadas = 0
    for oferta in novas[:MAX_OFERTAS_POR_RODADA]:
        mensagem = montar_mensagem(oferta)
        sucesso = enviar_para_grupo_whatsapp(mensagem, imagem_url=oferta.get("imagem"))
        if sucesso:
            salvar_em_historico(oferta)
            enviadas += 1
            logger.info(f"Enviado: {oferta['produto']} ({oferta['loja']}) {oferta['desconto_percentual']}% off")
            if enviadas < MAX_OFERTAS_POR_RODADA:
                logger.info(f"Aguardando {INTERVALO_ENTRE_POSTS}s antes do próximo post...")
                time.sleep(INTERVALO_ENTRE_POSTS)

    logger.info(f"=== Rodada concluída: {enviadas} enviadas ===")
    proxima = (datetime.now() + timedelta(minutes=RODAR_A_CADA_MINUTOS)).isoformat()
    salvar_estado("aguardando", proxima_rodada=proxima)


def main():
    logger.info("Bot iniciado")
    logger.info(f"Intervalo: {RODAR_A_CADA_MINUTOS} min | Desconto mínimo: {MIN_DESCONTO}% | Janela: {HORA_INICIO}h-{HORA_FIM}h")

    while True:
        if esta_pausado():
            logger.info("Bot pausado. Aguardando...")
            time.sleep(60)
            continue

        if not dentro_da_janela() and not consumir_forca():
            hora = datetime.now().hour
            logger.info(f"Fora da janela ({hora}h). Aguardando {RODAR_A_CADA_MINUTOS} min...")
            time.sleep(RODAR_A_CADA_MINUTOS * 60)
            continue

        consumir_forca()  # limpa flag se estava forçado
        try:
            executar_rodada()
        except Exception as e:
            logger.error(f"Erro crítico na rodada: {e}")
            salvar_estado("erro")

        logger.info(f"Próxima rodada em {RODAR_A_CADA_MINUTOS} minutos...")
        time.sleep(RODAR_A_CADA_MINUTOS * 60)


if __name__ == "__main__":
    main()
