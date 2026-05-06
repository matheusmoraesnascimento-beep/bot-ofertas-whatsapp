import os
import sys
import re
import time
import random
import logging
import unicodedata
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Fix encoding para Windows (emojis na mensagem)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv("config.env")

from instagram_posts import gerar_posts_instagram as _gerar_posts_ig, gerar_reels_instagram as _gerar_reels_ig

# Config
MIN_DESCONTO = int(os.getenv("MIN_DESCONTO", "20"))
MAX_OFERTAS_POR_RODADA = int(os.getenv("MAX_OFERTAS_POR_RODADA", "5"))
INTERVALO_ENTRE_POSTS = int(os.getenv("INTERVALO_ENTRE_POSTS", "60"))
# Horários fixos de execução (Brasília) — ex: "8,18"
HORARIOS_EXECUCAO = [int(h) for h in os.getenv("HORARIOS_EXECUCAO", "8,18").split(",") if h.strip()]

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000").rstrip("/")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from amazon import buscar_ofertas_amazon
from shopee import buscar_ofertas_shopee
from mercadolivre import buscar_ofertas_mercadolivre
from kabum import buscar_ofertas_kabum
from filtros import filtrar_melhores_ofertas, remover_repetidas, salvar_em_historico
from painel.state import salvar_estado, esta_pausado, consumir_forca
from inteligencia import calcular_score, categoria_ativa, registrar_precos
from db import init_db, criar_ou_buscar_link

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


def gerar_slug(produto: str, loja: str) -> str:
    texto = f"{produto}-{loja}".lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:60]


def montar_mensagem(oferta: dict) -> str:
    preco_atual = oferta["preco_atual"]
    preco_antigo = oferta.get("preco_antigo")
    desconto = oferta.get("desconto_percentual", 0)

    slug = gerar_slug(oferta["produto"], oferta.get("loja", ""))
    criar_ou_buscar_link(slug, oferta["link_afiliado"], oferta["produto"])
    link_rastreado = f"{BASE_URL}/r/{slug}"

    if preco_antigo:
        economia = preco_antigo - preco_atual
        headline = f"🔥 BAIXOU R$ {economia:.2f} (-{desconto:.0f}%)"
    else:
        headline = f"🔥 OFERTA -{desconto:.0f}%"

    linhas = [headline, "", f"🛍️ {oferta['produto']}"]

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
        f"👉 {link_rastreado}",
        "",
        "⏰ Estoque limitado — preço pode mudar.",
    ])

    return "\n".join(linhas)


def _aguardar_ate_proximo(horarios: list) -> datetime:
    """Dorme até o próximo horário agendado, acordando em fatias de 10s para checar força."""
    agora = datetime.now()
    candidatos = []
    for h in horarios:
        prox = agora.replace(hour=h, minute=0, second=0, microsecond=0)
        if prox <= agora:
            prox += timedelta(days=1)
        candidatos.append(prox)
    proxima = min(candidatos)
    salvar_estado("aguardando", proxima_rodada=proxima.isoformat())
    logger.info(f"Próxima rodada: {proxima.strftime('%d/%m %H:%M')} — dormindo...")
    while datetime.now() < proxima:
        time.sleep(10)
        if consumir_forca():
            logger.info("Força rodada — acordando imediatamente.")
            return datetime.now()
        if esta_pausado():
            time.sleep(50)  # pausa: checa a cada 60s
    return proxima


def executar_rodada():
    from dotenv import load_dotenv
    load_dotenv("config.env", override=True)
    max_ofertas = int(os.getenv("MAX_OFERTAS_POR_RODADA", "5"))
    min_desconto = int(os.getenv("MIN_DESCONTO", "20"))
    intervalo = int(os.getenv("INTERVALO_ENTRE_POSTS", "60"))

    salvar_estado("rodando")
    logger.info("=== Iniciando rodada de busca ===")
    categorias = ler_categorias()

    if not categorias:
        logger.warning("Nenhuma categoria encontrada")
        return

    ofertas = []
    fontes = [f.strip() for f in os.getenv("FONTES_ATIVAS", "amazon,ml").split(",") if f.strip()]
    logger.info(f"Fontes ativas: {fontes}")

    for categoria in categorias:
        if not categoria_ativa(categoria):
            logger.info(f"Pulando {categoria} (fora da janela da categoria)")
            continue
        logger.info(f"Buscando: {categoria}")
        if "amazon" in fontes:
            try:
                ofertas.extend(buscar_ofertas_amazon(categoria))
            except Exception as e:
                logger.error(f"Amazon falhou [{categoria}]: {e}")
        if "ml" in fontes:
            try:
                ofertas.extend(buscar_ofertas_mercadolivre(categoria))
            except Exception as e:
                logger.error(f"ML falhou [{categoria}]: {e}")

    logger.info(f"Total bruto: {len(ofertas)} ofertas")

    registrar_precos(ofertas)
    filtradas = filtrar_melhores_ofertas(ofertas, min_desconto)
    logger.info(f"Após filtro desconto: {len(filtradas)}")

    for o in filtradas:
        o["_score"] = calcular_score(o)
    filtradas.sort(key=lambda o: o["_score"], reverse=True)

    novas = remover_repetidas(filtradas)
    logger.info(f"Após dedup 48h: {len(novas)} — enviando até {max_ofertas}")

    # Pega os top 3x e embaralha para variar sem perder qualidade
    pool = novas[:max_ofertas * 3]
    random.shuffle(pool)
    novas = pool

    # Garante 1 produto por categoria (rotatividade)
    selecionadas = []
    cats_usadas = set()
    for o in novas:
        cat = o.get("categoria", "")
        if cat not in cats_usadas:
            selecionadas.append(o)
            cats_usadas.add(cat)
        if len(selecionadas) >= max_ofertas:
            break
    # Se não encheu, completa com categorias repetidas (melhor score)
    if len(selecionadas) < max_ofertas:
        for o in novas:
            if o not in selecionadas:
                selecionadas.append(o)
            if len(selecionadas) >= max_ofertas:
                break

    enviadas = 0
    for oferta in selecionadas:
        mensagem = montar_mensagem(oferta)
        sucesso = enviar_para_grupo_whatsapp(mensagem, imagem_url=oferta.get("imagem"))
        if sucesso:
            salvar_em_historico(oferta)
            enviadas += 1
            logger.info(f"Enviado: {oferta['produto']} ({oferta['loja']}) {oferta['desconto_percentual']}% off")
            if enviadas < max_ofertas:
                logger.info(f"Aguardando {intervalo}s antes do próximo post...")
                time.sleep(intervalo)

    logger.info(f"=== Rodada concluída: {enviadas} enviadas ===")


def _posts_instagram_se_necessario():
    hoje = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().hour
    if hora < 8:
        return

    flag_posts = f"posts/{hoje}/.gerado"
    if not os.path.exists(flag_posts):
        try:
            paths = _gerar_posts_ig(3)
            if paths:
                os.makedirs(f"posts/{hoje}", exist_ok=True)
                open(flag_posts, "w").close()
                logger.info(f"Posts Instagram gerados: {len(paths)}")
        except Exception as e:
            logger.error(f"Erro gerando posts Instagram: {e}")

    flag_reels = f"posts/{hoje}/.reels_gerado"
    if not os.path.exists(flag_reels):
        try:
            reels = _gerar_reels_ig(3)
            if reels:
                os.makedirs(f"posts/{hoje}", exist_ok=True)
                open(flag_reels, "w").close()
                logger.info(f"Reels Instagram gerados: {len(reels)}")
        except Exception as e:
            logger.error(f"Erro gerando Reels Instagram: {e}")


def main():
    init_db()
    logger.info("Bot iniciado")
    logger.info(f"Horários: {HORARIOS_EXECUCAO}h | Desconto mínimo: {MIN_DESCONTO}%")

    # Roda imediatamente na primeira vez se flag de força já estiver setada
    if not consumir_forca():
        _aguardar_ate_proximo(HORARIOS_EXECUCAO)

    while True:
        if esta_pausado():
            salvar_estado("aguardando")
            logger.info("Bot pausado. Aguardando...")
            time.sleep(60)
            continue

        try:
            executar_rodada()
        except Exception as e:
            logger.error(f"Erro crítico na rodada: {e}")
            salvar_estado("erro")

        _posts_instagram_se_necessario()
        _aguardar_ate_proximo(HORARIOS_EXECUCAO)


if __name__ == "__main__":
    main()
