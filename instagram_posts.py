import os
import io
import logging
import shutil
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

from curl_cffi import requests as cffi_requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from db import top_ofertas_para_post

logger = logging.getLogger(__name__)

POSTS_DIR = Path("posts")
IMG_SIZE = 1080
REELS_W, REELS_H = 1080, 1920

COR_FUNDO = (255, 255, 255)
COR_BADGE = (220, 38, 38)
COR_PRECO_ATUAL = (220, 38, 38)
COR_PRECO_ANTIGO = (150, 150, 150)
COR_RODAPE_BG = (245, 245, 245)
COR_TEXTO = (30, 30, 30)
COR_LOJA = (80, 80, 80)


def _baixar_imagem(url: str) -> Image.Image | None:
    if not url:
        return None
    try:
        r = cffi_requests.get(url, timeout=10, impersonate="chrome124")
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        logger.warning(f"Falha download imagem: {e}")
        return None


def _fonte(tamanho: int, negrito: bool = False):
    candidatos_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    candidatos_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    candidatos = candidatos_bold if negrito else candidatos_regular
    for path in candidatos:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, tamanho)
            except Exception:
                continue
    return ImageFont.load_default()


def _gerar_imagem(oferta: dict, indice: int) -> Image.Image:
    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), COR_FUNDO)
    draw = ImageDraw.Draw(img)

    foto = _baixar_imagem(oferta.get("imagem"))
    if foto:
        foto_rgb = foto.convert("RGB")
        foto_rgb.thumbnail((900, 600), Image.LANCZOS)
        fx = (IMG_SIZE - foto_rgb.width) // 2
        fy = 80 + (600 - foto_rgb.height) // 2
        img.paste(foto_rgb, (fx, fy))
    else:
        cores_fallback = [(255, 237, 213), (219, 234, 254), (220, 252, 231)]
        cor = cores_fallback[indice % len(cores_fallback)]
        draw.rectangle([0, 0, IMG_SIZE, 700], fill=cor)
        fonte_fb = _fonte(48, negrito=True)
        nome_curto = oferta["produto"][:60]
        draw.text((540, 380), nome_curto, fill=COR_TEXTO, font=fonte_fb, anchor="mm")

    desconto = int(oferta.get("desconto", 0))
    if desconto > 0:
        badge_txt = f"-{desconto}%"
        fonte_badge = _fonte(52, negrito=True)
        bw, bh = 180, 80
        bx, by = IMG_SIZE - bw - 20, 20
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=12, fill=COR_BADGE)
        draw.text((bx + bw // 2, by + bh // 2), badge_txt, fill="white",
                  font=fonte_badge, anchor="mm")

    draw.rectangle([0, 700, IMG_SIZE, IMG_SIZE], fill=COR_RODAPE_BG)

    nome_curto = textwrap.shorten(oferta["produto"], width=55, placeholder="...")
    fonte_nome = _fonte(38, negrito=True)
    draw.text((54, 720), nome_curto, fill=COR_TEXTO, font=fonte_nome)

    preco_atual = oferta.get("preco", 0) or 0
    fonte_preco_atual = _fonte(64, negrito=True)
    fonte_preco_antigo = _fonte(36)

    preco_antigo = None
    if desconto and desconto < 100 and preco_atual:
        preco_antigo = round(preco_atual / (1 - desconto / 100), 2)

    y_preco = 800
    if preco_antigo:
        txt_antigo = f"R$ {preco_antigo:.2f}"
        draw.text((54, y_preco), txt_antigo, fill=COR_PRECO_ANTIGO, font=fonte_preco_antigo)
        bbox = draw.textbbox((54, y_preco), txt_antigo, font=fonte_preco_antigo)
        mid_y = (bbox[1] + bbox[3]) // 2
        draw.line([(bbox[0], mid_y), (bbox[2], mid_y)], fill=COR_PRECO_ANTIGO, width=2)
        y_preco += 46

    draw.text((54, y_preco), f"R$ {preco_atual:.2f}", fill=COR_PRECO_ATUAL,
              font=fonte_preco_atual)

    fonte_loja = _fonte(32)
    loja = oferta.get("loja", "")
    draw.text((54, 960), f"📍 {loja}", fill=COR_LOJA, font=fonte_loja)
    fonte_cta = _fonte(30, negrito=True)
    draw.text((54, 1010), "Comenta QUERO que mando o link 🔥", fill=COR_TEXTO,
              font=fonte_cta)

    return img


def _gerar_caption(oferta: dict) -> str:
    nome_curto = textwrap.shorten(oferta["produto"], width=60, placeholder="...")
    preco_atual = oferta.get("preco", 0) or 0
    desconto = int(oferta.get("desconto", 0))
    loja = oferta.get("loja", "")

    preco_antigo = None
    if desconto and desconto < 100 and preco_atual:
        preco_antigo = round(preco_atual / (1 - desconto / 100), 2)

    linhas = [f"{nome_curto} 🔥", ""]
    if preco_antigo:
        linhas.append(f"De R${preco_antigo:.2f} por R${preco_atual:.2f} (-{desconto}%)")
    else:
        linhas.append(f"R${preco_atual:.2f} (-{desconto}%)")

    loja_tag = loja.lower().replace(" ", "").replace("ç", "c").replace("á", "a")
    linhas.extend([
        f"📍 {loja}",
        "",
        "🔗 LINK NA BIO — clica e entra no grupo do WhatsApp pra receber em tempo real",
        "",
        "⚡ Bot rastreia 24/7. Curadoria humana. Sem spam.",
        "",
        f"#oferta #promocao #{loja_tag} #ofertas #desconto #economize #ofertasdodia #achados",
    ])
    return "\n".join(linhas)


def gerar_posts_instagram(n: int = 3) -> list[Path]:
    ofertas = top_ofertas_para_post(n)
    if not ofertas:
        logger.warning("Instagram posts: sem ofertas nas últimas 24h")
        return []

    hoje = datetime.now().strftime("%Y-%m-%d")
    pasta = POSTS_DIR / hoje
    pasta.mkdir(parents=True, exist_ok=True)

    gerados = []
    for i, oferta in enumerate(ofertas, start=1):
        try:
            img = _gerar_imagem(oferta, i - 1)
            img_path = pasta / f"post_{i}.jpg"
            img.save(img_path, "JPEG", quality=92)

            caption = _gerar_caption(oferta)
            txt_path = pasta / f"post_{i}.txt"
            txt_path.write_text(caption, encoding="utf-8")

            gerados.append(img_path)
            logger.info(f"Instagram post {i} gerado: {oferta['produto'][:50]}")
        except Exception as e:
            logger.error(f"Erro gerando post {i}: {e}")

    return gerados


def _gerar_imagem_reels(oferta: dict, indice: int) -> Image.Image:
    img = Image.new("RGB", (REELS_W, REELS_H), COR_FUNDO)
    draw = ImageDraw.Draw(img)

    # Fundo degradê escuro na metade inferior
    for y in range(REELS_H // 2, REELS_H):
        t = (y - REELS_H // 2) / (REELS_H // 2)
        r = int(20 + (245 - 20) * (1 - t))
        g = int(20 + (245 - 20) * (1 - t))
        b = int(20 + (245 - 20) * (1 - t))
        draw.line([(0, y), (REELS_W, y)], fill=(r, g, b))

    foto = _baixar_imagem(oferta.get("imagem"))
    area_foto_h = REELS_H // 2
    if foto:
        foto_rgb = foto.convert("RGB")
        foto_rgb.thumbnail((REELS_W, area_foto_h - 40), Image.LANCZOS)
        fx = (REELS_W - foto_rgb.width) // 2
        fy = 40 + (area_foto_h - 40 - foto_rgb.height) // 2
        img.paste(foto_rgb, (fx, fy))
    else:
        cores_fallback = [(255, 237, 213), (219, 234, 254), (220, 252, 231)]
        cor = cores_fallback[indice % len(cores_fallback)]
        draw.rectangle([0, 0, REELS_W, area_foto_h], fill=cor)

    desconto = int(oferta.get("desconto", 0))
    if desconto > 0:
        badge_txt = f"-{desconto}%"
        fonte_badge = _fonte(64, negrito=True)
        bw, bh = 200, 96
        bx, by = REELS_W - bw - 24, 24
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=16, fill=COR_BADGE)
        draw.text((bx + bw // 2, by + bh // 2), badge_txt, fill="white",
                  font=fonte_badge, anchor="mm")

    # Conteúdo zona inferior (branca/clara)
    y_base = REELS_H // 2 + 60
    nome_curto = textwrap.shorten(oferta["produto"], width=45, placeholder="...")
    fonte_nome = _fonte(52, negrito=True)
    for linha in textwrap.wrap(nome_curto, width=22):
        draw.text((60, y_base), linha, fill=COR_TEXTO, font=fonte_nome)
        y_base += 68

    y_base += 20
    preco_atual = oferta.get("preco", 0) or 0
    preco_antigo = None
    if desconto and desconto < 100 and preco_atual:
        preco_antigo = round(preco_atual / (1 - desconto / 100), 2)

    if preco_antigo:
        fonte_antigo = _fonte(44)
        txt_antigo = f"R$ {preco_antigo:.2f}"
        draw.text((60, y_base), txt_antigo, fill=COR_PRECO_ANTIGO, font=fonte_antigo)
        bbox = draw.textbbox((60, y_base), txt_antigo, font=fonte_antigo)
        mid_y = (bbox[1] + bbox[3]) // 2
        draw.line([(bbox[0], mid_y), (bbox[2], mid_y)], fill=COR_PRECO_ANTIGO, width=3)
        y_base += 60

    fonte_preco = _fonte(88, negrito=True)
    draw.text((60, y_base), f"R$ {preco_atual:.2f}", fill=COR_PRECO_ATUAL, font=fonte_preco)
    y_base += 110

    fonte_loja = _fonte(40)
    loja = oferta.get("loja", "")
    draw.text((60, y_base), f"📍 {loja}", fill=COR_LOJA, font=fonte_loja)
    y_base += 70

    fonte_cta = _fonte(46, negrito=True)
    draw.text((60, y_base), "🔗 Link na bio!", fill=COR_BADGE, font=fonte_cta)
    y_base += 70
    fonte_cta2 = _fonte(38)
    draw.text((60, y_base), "Comenta QUERO que mando no direct 👇", fill=COR_TEXTO, font=fonte_cta2)

    return img


def _imagem_para_video(img_path: Path, video_path: Path, duracao: int = 10) -> bool:
    ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1",
        "-i", str(img_path),
        "-t", str(duracao),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={REELS_W}:{REELS_H}",
        "-movflags", "+faststart",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    if result.returncode != 0:
        logger.error(f"ffmpeg erro: {result.stderr.decode()[:200]}")
        return False
    return True


def gerar_reels_instagram(n: int = 3) -> list[dict]:
    ofertas = top_ofertas_para_post(n)
    if not ofertas:
        logger.warning("Reels: sem ofertas nas últimas 24h")
        return []

    hoje = datetime.now().strftime("%Y-%m-%d")
    pasta = POSTS_DIR / hoje / "reels"
    pasta.mkdir(parents=True, exist_ok=True)

    gerados = []
    for i, oferta in enumerate(ofertas, start=1):
        try:
            img = _gerar_imagem_reels(oferta, i - 1)
            img_path = pasta / f"reel_{i}.jpg"
            img.save(img_path, "JPEG", quality=92)

            video_path = pasta / f"reel_{i}.mp4"
            ok = _imagem_para_video(img_path, video_path)

            caption = _gerar_caption(oferta)
            txt_path = pasta / f"reel_{i}.txt"
            txt_path.write_text(caption, encoding="utf-8")

            gerados.append({"imagem": img_path, "video": video_path if ok else None,
                            "caption": txt_path, "oferta": oferta["produto"]})
            logger.info(f"Reel {i} gerado: {oferta['produto'][:50]}")
        except Exception as e:
            logger.error(f"Erro gerando reel {i}: {e}")

    return gerados


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    paths = gerar_posts_instagram()
    print(f"Gerados: {len(paths)}")
    for p in paths:
        print(" ", p)
