import os
import sys
import time
import logging
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from amazon import buscar_ofertas_amazon
from shopee import buscar_ofertas_shopee
from filtros import filtrar_melhores_ofertas, remover_repetidas, salvar_em_historico

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

def enviar_para_grupo_whatsapp(mensagem: str) -> bool:
    if DRY_RUN:
        print("\n" + "="*50)
        print(mensagem)
        print("="*50 + "\n")
        return True
    from whatsapp import enviar_para_grupo_whatsapp as _enviar
    return _enviar(mensagem)


def ler_categorias(arquivo="categorias.txt"):
    try:
        with open(arquivo, encoding="utf-8") as f:
            return [linha.strip() for linha in f if linha.strip()]
    except FileNotFoundError:
        logger.error(f"Arquivo {arquivo} não encontrado")
        return []


def montar_mensagem(oferta: dict) -> str:
    preco_antigo = f"R$ {oferta['preco_antigo']:.2f}" if oferta.get("preco_antigo") else "N/D"
    return (
        "🔥 OFERTA ENCONTRADA\n\n"
        f"🛍️ {oferta['produto']}\n\n"
        f"💰 De: {preco_antigo}\n"
        f"✅ Por: R$ {oferta['preco_atual']:.2f}\n"
        f"📉 Desconto: {oferta['desconto_percentual']}%\n\n"
        f"🏪 Loja: {oferta['loja']}\n\n"
        f"👉 Comprar com desconto:\n{oferta['link_afiliado']}\n\n"
        "⚠️ Preço pode mudar a qualquer momento."
    )


def executar_rodada():
    logger.info("=== Iniciando rodada de busca ===")
    categorias = ler_categorias()

    if not categorias:
        logger.warning("Nenhuma categoria encontrada")
        return

    ofertas = []
    for categoria in categorias:
        logger.info(f"Buscando: {categoria}")
        try:
            ofertas.extend(buscar_ofertas_amazon(categoria))
        except Exception as e:
            logger.error(f"Amazon falhou [{categoria}]: {e}")
        try:
            ofertas.extend(buscar_ofertas_shopee(categoria))
        except Exception as e:
            logger.error(f"Shopee falhou [{categoria}]: {e}")

    logger.info(f"Total bruto: {len(ofertas)} ofertas")

    filtradas = filtrar_melhores_ofertas(ofertas, MIN_DESCONTO)
    logger.info(f"Após filtro desconto: {len(filtradas)}")

    novas = remover_repetidas(filtradas)
    logger.info(f"Após dedup 24h: {len(novas)} — enviando até {MAX_OFERTAS_POR_RODADA}")

    enviadas = 0
    for oferta in novas[:MAX_OFERTAS_POR_RODADA]:
        mensagem = montar_mensagem(oferta)
        sucesso = enviar_para_grupo_whatsapp(mensagem)
        if sucesso:
            salvar_em_historico(oferta)
            enviadas += 1
            logger.info(f"Enviado: {oferta['produto']} ({oferta['loja']}) {oferta['desconto_percentual']}% off")
            if enviadas < MAX_OFERTAS_POR_RODADA:
                logger.info(f"Aguardando {INTERVALO_ENTRE_POSTS}s antes do próximo post...")
                time.sleep(INTERVALO_ENTRE_POSTS)

    logger.info(f"=== Rodada concluída: {enviadas} enviadas ===")


def main():
    logger.info("Bot iniciado")
    logger.info(f"Intervalo entre rodadas: {RODAR_A_CADA_MINUTOS} min | Desconto mínimo: {MIN_DESCONTO}%")

    while True:
        try:
            executar_rodada()
        except Exception as e:
            logger.error(f"Erro crítico na rodada: {e}")

        logger.info(f"Próxima rodada em {RODAR_A_CADA_MINUTOS} minutos...")
        time.sleep(RODAR_A_CADA_MINUTOS * 60)


if __name__ == "__main__":
    main()
