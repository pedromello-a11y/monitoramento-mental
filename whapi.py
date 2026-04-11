"""Cliente de envio WhatsApp via gateway whatsapp-web.js (wa_gateway)."""
import httpx
from config import WA_GATEWAY_URL, WA_BRIDGE_SECRET


async def send_buttons(to: str, text: str, options: list) -> bool:
    """Envia mensagem com opções. Via gateway envia como texto simples."""
    options_text = "\n".join(str(o) for o in options)
    return await send_message(to, f"{text}\n\n{options_text}")


async def send_message(to: str, text: str) -> bool:
    """Envia mensagem via gateway local (whatsapp-web.js).

    `to` deve ser o número com DDI, ex: "5511999998888".
    Retorna True se enviado com sucesso.
    """
    if not WA_GATEWAY_URL:
        return False
    try:
        headers = {"Content-Type": "application/json"}
        if WA_BRIDGE_SECRET:
            headers["X-Bridge-Secret"] = WA_BRIDGE_SECRET
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{WA_GATEWAY_URL.rstrip('/')}/send",
                headers=headers,
                json={"to": to, "body": text},
            )
        return r.is_success
    except Exception:
        return False
