# WhatsApp Canal — Design Spec
**Data:** 2026-05-05

## Objetivo

Postar ofertas simultaneamente no grupo WhatsApp existente e em um canal WhatsApp (sem limite de membros, só admin posta). Canal é opcional — se `WHATSAPP_CHANNEL_NAME` não estiver definido, bot continua postando só no grupo.

## Arquitetura

Abordagem A: uma sessão de browser, dois destinos sequenciais. `whatsapp.py` abre Chromium uma vez, posta no grupo, depois navega para aba "Atualizações" e posta no canal.

## Configuração

Nova variável de ambiente em `whatsapp.py`:

```python
CHANNEL_NAME = os.getenv("WHATSAPP_CHANNEL_NAME", "")
```

`config.env.example`:
```
WHATSAPP_CHANNEL_NAME=
```

Se vazio → canal ignorado. Sem breaking change no comportamento atual.

## Fluxo de Envio

`enviar_para_grupo_whatsapp()` modificado:

```
1. Abre WhatsApp Web (inalterado)
2. Aguarda "Lista de conversas" (inalterado)
3. _abrir_grupo(page, GROUP_NAME) → envia mensagem/imagem (inalterado)
4. SE CHANNEL_NAME definido:
   a. _abrir_canal(page, CHANNEL_NAME)
   b. envia mesma mensagem/imagem (mesmas funções _enviar_*)
5. Fecha browser
```

**Tratamento de erro:**
- Grupo falha → retorna `False` (comportamento atual preservado)
- Canal falha → loga `warning`, retorna `True` (grupo já enviou, canal é bônus)

## Nova Função `_abrir_canal()`

```python
def _abrir_canal(page, nome_canal: str):
    # Navega para aba Atualizações (múltiplos seletores fallback)
    tab = page.locator('[data-tab="5"], [aria-label*="tualiza"], [aria-label*="hannel"]').first
    tab.click()
    _delay()

    # Tenta abrir canal diretamente pelo título
    resultado = page.locator(f'span[title="{nome_canal}"]').first
    if resultado.count() == 0:
        # Fallback: busca pelo nome
        caixa = page.locator('[data-tab="6"][contenteditable="true"], [data-testid="chat-list-search"]').first
        caixa.click()
        caixa.fill(nome_canal)
        _delay()
        resultado = page.locator(f'span[title="{nome_canal}"]').first
        resultado.wait_for(timeout=15000)

    resultado.click()
    _delay()
```

Após abrir o canal, reutiliza `_enviar_mensagem()` e `_enviar_imagem_com_legenda()` sem modificação — interface de postagem em canal é idêntica à de grupo.

## Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `whatsapp.py` | +`CHANNEL_NAME` const, +`_abrir_canal()`, modifica `enviar_para_grupo_whatsapp()` |
| `config.env.example` | +`WHATSAPP_CHANNEL_NAME=` |

## Fora do Escopo

- Criação automática do canal (feita manualmente via app)
- Retry isolado de canal com falha
- Canal sem grupo (GROUP_NAME ainda obrigatório)
