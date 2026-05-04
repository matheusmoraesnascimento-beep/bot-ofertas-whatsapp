import json
import os
from datetime import datetime

STATE_FILE = os.getenv("BOT_STATE_FILE", "bot_state.json")
FORCE_RUN_FILE = "bot_force_run.flag"


def ler_estado() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"status": "desconhecido", "ultima_rodada": None, "proxima_rodada": None, "pausado": False}
    with open(STATE_FILE) as f:
        return json.load(f)


def salvar_estado(status: str, proxima_rodada: str = None):
    estado = ler_estado()
    estado["status"] = status
    estado["ultima_rodada"] = datetime.now().isoformat()
    if proxima_rodada:
        estado["proxima_rodada"] = proxima_rodada
    with open(STATE_FILE, "w") as f:
        json.dump(estado, f)


def pausar(pausado: bool):
    estado = ler_estado()
    estado["pausado"] = pausado
    with open(STATE_FILE, "w") as f:
        json.dump(estado, f)


def esta_pausado() -> bool:
    return ler_estado().get("pausado", False)


def forcar_rodada():
    open(FORCE_RUN_FILE, "w").close()


def consumir_forca() -> bool:
    if os.path.exists(FORCE_RUN_FILE):
        os.remove(FORCE_RUN_FILE)
        return True
    return False
