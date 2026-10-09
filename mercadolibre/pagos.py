"""Lógica de pagos simulada: marcas, validación de tarjetas, recargos, comisiones y facturas."""
import re
import secrets
from datetime import date, datetime, timedelta

# marca: (prefijo, largo del número, largo del CVV)
MARCAS = {
    "Visa": (r"^4", 16, 3),
    "Mastercard": (r"^(5[1-5]|222[1-9]|22[3-9]\d|2[3-6]\d\d|27[01]\d|2720)", 16, 3),
    "American Express": (r"^3[47]", 15, 4),
    "Cabal": (r"^(604|589657)", 16, 3),
    "Diners Club": (r"^(36|38|30[0-5])", 14, 3),
}
RECARGOS = {1: 0.0, 3: 0.08, 6: 0.15, 12: 0.28}  # recargo financiero por cantidad de cuotas
# Tarjetas de prueba que simulan respuestas del banco emisor: número -> (código, mensaje)
RECHAZOS = {
    "4000000000000002": ("05", "Rechazada por el banco emisor"),
    "4000000000009995": ("51", "Fondos insuficientes"),
    "4000000000000069": ("54", "Tarjeta vencida"),
    "4000000000000127": ("N7", "Código de seguridad (CVV) incorrecto"),
}
EMISOR = {"razon": "ULTRA SND S.R.L.", "cuit": "30-00000000-0", "iva": "IVA Responsable Inscripto",
          "domicilio": "Av. Colón 1234, Córdoba, Argentina", "inicio": "01/01/2026"}
PUNTO_VENTA = 1


def solo_digitos(texto):
    return re.sub(r"\D", "", texto or "")


def detectar_marca(numero):
    """Devuelve la marca según el prefijo (BIN) del número, o None."""
    for nombre, (prefijo, _, _) in MARCAS.items():
        if re.match(prefijo, numero):
            return nombre
    return None


def largo_cvv(marca):
    return MARCAS[marca][2] if marca else 3


def luhn(numero):
    """Algoritmo de Luhn: detecta números de tarjeta mal tipeados."""
    total = 0
    for i, d in enumerate(reversed(numero)):
        n = int(d)
        if i % 2:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def vencida(vencimiento):
    """vencimiento en formato MM/AA; vale hasta el último día del mes."""
    mes, anio = int(vencimiento[:2]), 2000 + int(vencimiento[3:])
    hoy = date.today()
    return (anio, mes) < (hoy.year, hoy.month)


def monto_con_recargo(total, cuotas):
    return round(total * (1 + RECARGOS[cuotas]), 2)


def liquidacion(pago):
    """Lo que el comercio recibe: monto - comisión del procesador - IVA de la comisión."""
    tasa = 0.035 if pago.tipo_tarjeta == "credito" else 0.015
    comision = round(pago.monto * tasa, 2)
    iva = round(comision * 0.21, 2)
    return {"bruto": pago.monto, "comision": comision, "iva": iva, "neto": round(pago.monto - comision - iva, 2)}


def emitir_factura(pedido, pago):
    """Crea la Factura B (consumidor final) de un pago aprobado. Los precios incluyen IVA 21%."""
    from models import Factura, db
    siguiente = (db.session.query(db.func.max(Factura.id)).scalar() or 0) + 1
    ahora = datetime.utcnow()
    neto = round(pago.monto / 1.21, 2)
    return Factura(
        numero=f"{PUNTO_VENTA:04d}-{siguiente:08d}", pedido_id=pedido.id, pago_id=pago.id, fecha=ahora,
        cliente_nombre=pedido.usuario.nombre, cliente_email=pedido.usuario.email,
        detalle=f"{pedido.cantidad} × {pedido.producto.nombre}",
        subtotal=pedido.subtotal if pedido.subtotal is not None else pedido.total, descuento=pedido.descuento or 0,
        envio=pedido.envio or 0, domicilio=pedido.domicilio_texto, cupon_codigo=pedido.cupon_codigo,
        recargo=round(pago.monto - pedido.total, 2), neto=neto, iva=round(pago.monto - neto, 2), total=pago.monto,
        cae="".join(secrets.choice("0123456789") for _ in range(14)), cae_vto=(ahora + timedelta(days=10)).date())

def aprobar_pedido(pedido, pago):
    """Pedido pagado: consume el cupón, genera el cupón de regalo y emite la factura. No hace commit.
    Devuelve True si se generó un cupón de regalo."""
    from models import Cupon, db
    from tienda import REGALO_DESDE, REGALO_DIAS, REGALO_MINIMO, REGALO_PORCENTAJE
    pedido.estado = "pagado"
    if pedido.cupon_id:
        cupon = db.session.get(Cupon, pedido.cupon_id)
        if cupon:
            cupon.usos += 1
    regalo = pedido.subtotal - (pedido.descuento or 0) >= REGALO_DESDE
    if regalo:
        db.session.add(Cupon(codigo="GRACIAS-" + secrets.token_hex(4).upper(), tipo="porcentaje", valor=REGALO_PORCENTAJE,
                             minimo=REGALO_MINIMO, vence=date.today() + timedelta(days=REGALO_DIAS), usos_max=1,
                             publico=False, activo=True, usuario_id=pedido.usuario_id, origen="regalo", pedido_origen_id=pedido.id))
    db.session.add(emitir_factura(pedido, pago))
    return regalo