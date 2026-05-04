import sqlite3
import os
from datetime import datetime, timedelta

DB_FILE = os.getenv("DB_FILE", "ofertas.db")


def _conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS ofertas_enviadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto TEXT,
                loja TEXT,
                preco REAL,
                link TEXT,
                desconto REAL,
                imagem TEXT,
                data_envio TEXT
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_link ON ofertas_enviadas(link)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_data ON ofertas_enviadas(data_envio)")
        con.execute("""
            CREATE TABLE IF NOT EXISTS historico_precos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT NOT NULL,
                produto TEXT,
                loja TEXT,
                preco REAL NOT NULL,
                data TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_hp_link ON historico_precos(link)")


def ja_enviado(link: str, horas: int = 24) -> bool:
    limite = (datetime.now() - timedelta(hours=horas)).isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM ofertas_enviadas WHERE link = ? AND data_envio > ? LIMIT 1",
            (link, limite),
        ).fetchone()
    return row is not None


def salvar_oferta(oferta: dict):
    with _conn() as con:
        con.execute(
            """INSERT INTO ofertas_enviadas
               (produto, loja, preco, link, desconto, imagem, data_envio)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                oferta.get("produto", ""),
                oferta.get("loja", ""),
                oferta.get("preco_atual"),
                oferta.get("link_afiliado", ""),
                oferta.get("desconto_percentual", 0),
                oferta.get("imagem", ""),
                datetime.now().isoformat(),
            ),
        )
        con.commit()


def listar_ofertas(limit: int = 200) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT produto, loja, preco, link, desconto, imagem, data_envio
               FROM ofertas_enviadas ORDER BY data_envio DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    cols = ["produto", "loja", "preco", "link", "desconto", "imagem", "data_envio"]
    return [dict(zip(cols, r)) for r in rows]


def migrar_csv(csv_path: str = "ofertas_enviadas.csv"):
    import csv as _csv
    if not os.path.exists(csv_path):
        return
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    with _conn() as con:
        for r in rows:
            con.execute(
                """INSERT OR IGNORE INTO ofertas_enviadas
                   (produto, loja, preco, link, data_envio)
                   VALUES (?, ?, ?, ?, ?)""",
                (r.get("produto"), r.get("loja"), r.get("preco"),
                 r.get("link"), r.get("data_envio")),
            )
        con.commit()
    print(f"Migrados {len(rows)} registros do CSV")


def registrar_preco(oferta: dict):
    with _conn() as con:
        con.execute(
            "INSERT INTO historico_precos (link, produto, loja, preco, data) VALUES (?,?,?,?,?)",
            (oferta["link_afiliado"], oferta.get("produto"), oferta.get("loja"),
             oferta["preco_atual"], datetime.now().isoformat()),
        )
        con.commit()


def preco_minimo_historico(link: str, dias: int = 30) -> float | None:
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT MIN(preco) FROM historico_precos WHERE link = ? AND data > ?",
            (link, limite),
        ).fetchone()
    return row[0] if row and row[0] is not None else None
