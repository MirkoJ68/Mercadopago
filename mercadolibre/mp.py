"""Integración con Mercado Pago (Checkout Pro): crear la preferencia, sincronizar pagos y validar webhooks.

Regla de oro: el estado de un pago SIEMPRE se confirma consultando la API de Mercado Pago con el Access Token.
Nunca se confía en lo que llega por la URL de retorno ni en el cuerpo del webhook.
"""
import hashlib
import hmac
import os

import mercadopago

from models import Pago, Pedido, db
from pagos import aprobar_pedido

# estado del pago en Mercado Pago -> estado interno de la tabla Pago
ESTADOS = {
    "approved": "aprobado",
    "authorized": "pendiente_mp", "in_process": "pendiente_mp", "pending": "pendiente_mp", "in_mediation": "pendiente_mp",
    "rejected": "rechazado", "cancelled": "rechazado", "refunded": "rechazado", "charged_back": "rechazado",
}


def _sdk():
    token = os.environ.get("MP_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Falta MP_ACCESS_TOKEN en el .env")
    return mercadopago.SDK(token)


def crear_preferencia(pedido, base_url):
    """Crea la preferencia de pago del pedido y devuelve la URL de Mercado Pago (init_point).

    Se envía UN solo ítem con el total del pedido (ya incluye cupón y envío), así el monto cobrado
    coincide exactamente con pedido.total.
    """
    retorno = f"{base_url}/pedido/{pedido.id}/mp-retorno"
    datos = {
        "items": [{
            "id": str(pedido.id),
            "title": f"Pedido #{pedido.codigo} - {pedido.cantidad} x {pedido.producto.nombre}"[:250],
            "quantity": 1,
            "unit_price": round(float(pedido.total), 2),
            "currency_id": "ARS",
        }],
        "external_reference": str(pedido.id),
        "back_urls": {"success": retorno, "failure": retorno, "pending": retorno},
        # sin pagos en efectivo: dejarían pedidos "colgados" días con el stock reservado
        "payment_methods": {"excluded_payment_types": [{"id": "ticket"}, {"id": "atm"}]},
        "statement_descriptor": "ULTRA SND",
    }
    if base_url.startswith("https://"):  # Mercado Pago exige URLs públicas con HTTPS para estas dos opciones
        datos["auto_return"] = "approved"
        datos["notification_url"] = f"{base_url}/webhook/mercadopago"
    r = _sdk().preference().create(datos)
    if r["status"] not in (200, 201):
        raise RuntimeError(f"Mercado Pago rechazó la preferencia: {r.get('response')}")
    return r["response"]["init_point"]


def firma_valida(req):
    """Valida la cabecera x-signature del webhook (HMAC-SHA256 con la clave secreta de la integración).

    Es una defensa extra: igual se vuelve a consultar el pago a la API, así que un webhook falso no puede aprobar nada.
    Si no hay MP_WEBHOOK_SECRET configurado, no se valida (solo para desarrollo).
    """
    secreto = os.environ.get("MP_WEBHOOK_SECRET")
    if not secreto:
        return True
    partes = dict(p.strip().split("=", 1) for p in req.headers.get("x-signature", "").split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    manifiesto = f"id:{req.args.get('data.id', '').lower()};request-id:{req.headers.get('x-request-id', '')};ts:{ts};"
    esperado = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


def sincronizar_pago(payment_id):
    """Consulta el pago en Mercado Pago y actualiza Pago y Pedido. Es idempotente (se puede llamar muchas veces)."""
    r = _sdk().payment().get(payment_id)
    if r["status"] != 200:
        return None
    mp = r["response"]
    ref = str(mp.get("external_reference") or "")
    pedido = db.session.get(Pedido, int(ref)) if ref.isdigit() else None
    if not pedido:
        return None

    estado = ESTADOS.get(mp.get("status"), "pendiente_mp")
    monto = float(mp.get("transaction_amount") or 0)
    pago = Pago.query.filter_by(mp_payment_id=str(mp["id"])).first()
    if pago and pago.estado == "aprobado":
        return pago  # ya procesado
    if not pago:
        tarjeta = mp.get("card") or {}
        pago = Pago(
            pedido_id=pedido.id, proveedor="mercadopago", mp_payment_id=str(mp["id"]),
            marca=(mp.get("payment_method_id") or "")[:30], ultimos4=(tarjeta.get("last_four_digits") or "")[:4],
            tipo_tarjeta="debito" if mp.get("payment_type_id") == "debit_card" else "credito",
            cuotas=mp.get("installments") or 1, monto=monto, estado=estado, referencia="MP-" + str(mp["id"])[:15])
        db.session.add(pago)
        db.session.flush()  # necesita id para la factura

    pago.estado, pago.codigo_respuesta = estado, "MP"
    pago.mensaje = (mp.get("status_detail") or "")[:120]
    pago.codigo_autorizacion = str(mp.get("authorization_code") or "")[:8] or None

    if estado == "aprobado":
        if pedido.estado != "pendiente":
            aviso = "REVISAR: pago aprobado sobre un pedido que ya no estaba pendiente (reembolsar)"
        elif abs(monto - pedido.total) > 0.01:
            aviso = "REVISAR: el monto cobrado no coincide con el pedido"
        else:
            aviso = None
            aprobar_pedido(pedido, pago)
        if aviso:
            pago.mensaje = aviso
            print(f"[ultra.snd] Pago MP {mp['id']} / pedido #{pedido.id}: {aviso}", flush=True)
    db.session.commit()
    return pago
