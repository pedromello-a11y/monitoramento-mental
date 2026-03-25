import httpx
from config import WHAPI_TOKEN

_BASE_URL = "https://gate.whapi.cloud"
_HEADERS = lambda: {"Authorization": f"Bearer {WHAPI_TOKEN}"}


async def send_message(to: str, text: str) -> bool:
    if not WHAPI_TOKEN:
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{_BASE_URL}/messages/text",
                headers=_HEADERS(),
                json={"to": to, "body": text},
                timeout=10,
            )
        return r.is_success
    except Exception:
        return False


async def send_buttons(to: str, text: str, options: list) -> bool:
    """Envia mensagem interativa com lista de opções via Whapi.
    Usa o tipo 'list' (suporta até 10 itens por seção, ideal para escalas 0-10).
    """
    if not WHAPI_TOKEN:
        return False
    rows = [{"id": str(o), "title": str(o)} for o in options]
    payload = {
        "to": to,
        "type": "list",
        "body": {"text": text},
        "action": {
            "button": "Escolher",
            "sections": [{"title": "Opções", "rows": rows}],
        },
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{_BASE_URL}/messages/interactive",
                headers=_HEADERS(),
                json=payload,
                timeout=10,
            )
        return r.is_success
    except Exception:
        return False
