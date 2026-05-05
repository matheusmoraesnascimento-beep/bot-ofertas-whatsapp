# WhatsApp Canal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional WhatsApp channel posting alongside the existing group — bot posts to both in one browser session.

**Architecture:** `whatsapp.py` gets a new `CHANNEL_NAME` env var and `_abrir_canal()` function. `enviar_para_grupo_whatsapp()` calls `_abrir_canal()` + send after the existing group send, only if `CHANNEL_NAME` is set. Canal failure logs a warning but does not affect the return value.

**Tech Stack:** Python 3.12, Playwright (already installed), existing WhatsApp Web session.

---

## File Map

| File | Change |
|------|--------|
| `whatsapp.py` | +`CHANNEL_NAME` module constant, +`_abrir_canal()`, modify `enviar_para_grupo_whatsapp()` |
| `config.env.example` | +`WHATSAPP_CHANNEL_NAME=` |

---

### Task 1: Add `_abrir_canal()` and wire into `enviar_para_grupo_whatsapp()`

**Files:**
- Modify: `whatsapp.py`

- [ ] **Step 1: Add `CHANNEL_NAME` constant**

After the existing `GROUP_NAME` line (line 12):
```python
GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME", "")
```

Add immediately after:
```python
CHANNEL_NAME = os.getenv("WHATSAPP_CHANNEL_NAME", "")
```

- [ ] **Step 2: Add `_abrir_canal()` function**

Add after the `_abrir_grupo()` function (after line 127):

```python
def _abrir_canal(page, nome_canal: str):
    try:
        tab = page.locator('[data-tab="5"], [aria-label*="tualiza"], [aria-label*="hannel"]').first
        tab.wait_for(state="visible", timeout=10000)
        tab.click()
        _delay()

        resultado = page.locator(f'span[title="{nome_canal}"]').first
        if resultado.count() == 0:
            caixa = page.locator('[data-tab="6"][contenteditable="true"], [data-testid="chat-list-search"]').first
            caixa.click()
            _delay()
            caixa.fill(nome_canal)
            _delay()
            resultado = page.locator(f'span[title="{nome_canal}"]').first
            resultado.wait_for(timeout=15000)

        resultado.click()
        _delay()
        logger.info(f"Canal '{nome_canal}' aberto")
    except Exception as e:
        raise RuntimeError(f"Não foi possível abrir canal '{nome_canal}': {e}")
```

- [ ] **Step 3: Modify `enviar_para_grupo_whatsapp()` to also post to channel**

The function currently ends with:
```python
            logger.info(f"Mensagem enviada para grupo '{GROUP_NAME}'")
            _delay()
            return True
```

Replace those 3 lines with:
```python
            logger.info(f"Mensagem enviada para grupo '{GROUP_NAME}'")
            _delay()

            if CHANNEL_NAME:
                try:
                    _abrir_canal(page, CHANNEL_NAME)
                    if imagem_path and Path(imagem_path).exists():
                        _enviar_imagem_com_legenda(page, imagem_path, mensagem)
                    else:
                        _enviar_mensagem(page, mensagem)
                    logger.info(f"Mensagem enviada para canal '{CHANNEL_NAME}'")
                    _delay()
                except Exception as e:
                    logger.warning(f"Canal falhou (grupo ok): {e}")

            return True
```

- [ ] **Step 4: Verify the file imports and structure are intact**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
python3 -c "import whatsapp; print('OK'); print('CHANNEL_NAME:', repr(whatsapp.CHANNEL_NAME))"
```

Expected:
```
OK
CHANNEL_NAME: ''
```

- [ ] **Step 5: Verify `_abrir_canal` is accessible and CHANNEL_NAME reads from env**

```bash
python3 -c "
import os
os.environ['WHATSAPP_CHANNEL_NAME'] = 'Canal Teste'
import importlib, whatsapp
importlib.reload(whatsapp)
print('CHANNEL_NAME:', whatsapp.CHANNEL_NAME)
assert whatsapp.CHANNEL_NAME == 'Canal Teste'
assert callable(whatsapp._abrir_canal)
print('PASS')
"
```

Expected:
```
CHANNEL_NAME: Canal Teste
PASS
```

- [ ] **Step 6: Commit**

```bash
git add whatsapp.py
git commit -m "feat: add WhatsApp channel posting alongside group"
```

---

### Task 2: Update config.env.example

**Files:**
- Modify: `config.env.example`

- [ ] **Step 1: Add `WHATSAPP_CHANNEL_NAME` entry**

Add after the existing `WHATSAPP_GROUP_NAME` line:

```
WHATSAPP_CHANNEL_NAME=
```

- [ ] **Step 2: Verify file looks correct**

```bash
cd "/home/moraes/Área de Trabalho/BOT/bot-ofertas-whatsapp"
grep -n "WHATSAPP" config.env.example
```

Expected output includes both lines:
```
WHATSAPP_GROUP_NAME=Nome do Grupo de Ofertas
WHATSAPP_CHANNEL_NAME=
```

- [ ] **Step 3: Commit**

```bash
git add config.env.example
git commit -m "docs: add WHATSAPP_CHANNEL_NAME to config.env.example"
```

---

### Task 3: Manual setup checklist (no code)

These steps must be done manually before testing in production:

- [ ] **Step 1: Create the WhatsApp channel on your phone**
  - Open WhatsApp → Atualizações tab → "+" → Criar canal
  - Name it exactly as you'll set in `WHATSAPP_CHANNEL_NAME`

- [ ] **Step 2: Add `WHATSAPP_CHANNEL_NAME` to Railway**
  - Railway dashboard → your service → Variables
  - Add: `WHATSAPP_CHANNEL_NAME=<nome exato do canal>`

- [ ] **Step 3: Test via painel**
  - Open painel → force a round
  - Check Railway logs for: `"Mensagem enviada para canal '...'"` or `"Canal falhou (grupo ok): ..."`
  - If canal falhou: the selector for the Updates tab may need adjustment (see note below)

**Note on selector fallback:** If the channel tab selector fails, inspect WhatsApp Web manually and find the correct `aria-label` or `data-tab` value for the "Atualizações" tab, then update the locator string in `_abrir_canal()`:
```python
tab = page.locator('[data-tab="5"], [aria-label*="tualiza"], [aria-label*="hannel"]').first
```
