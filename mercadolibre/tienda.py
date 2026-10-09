"""Envíos por código postal (estimación por zona/distancia) y descuentos de cupones. Lógica pura."""
import re

ALMACEN = "Av. Renault Argentina 2520, Córdoba"
REGALO_DESDE, REGALO_PORCENTAJE, REGALO_MINIMO, REGALO_DIAS = 200000, 5, 50000, 30  # cupón de regalo por compras grandes
BASE, POR_KM, EXTRA_UNIDAD = 3000, 12.0, 0.15  # $ base + $ por km; +15% por cada unidad adicional

# (CP desde, CP hasta, zona, km aproximados por ruta desde el almacén). Valores estimados: se pueden ajustar.
# El primero que coincide gana, por eso van antes los rangos específicos.
ZONAS = [
    (5000, 5016, "Córdoba Capital", 10), (5017, 5299, "Gran Córdoba y Sierras", 60),
    (5300, 5399, "La Rioja", 430), (5400, 5499, "San Juan", 650), (5500, 5699, "Mendoza", 690),
    (5700, 5799, "San Luis", 440), (5800, 5999, "Sur de Córdoba", 200),
    (4000, 4199, "Tucumán", 540), (4200, 4399, "Santiago del Estero", 420), (4400, 4599, "Salta", 900),
    (4600, 4699, "Jujuy", 1000), (4700, 4799, "Catamarca", 480), (4800, 4999, "Noroeste argentino", 800),
    (3000, 3099, "Santa Fe", 340), (3100, 3299, "Entre Ríos", 550), (3300, 3399, "Misiones", 1100),
    (3400, 3499, "Corrientes", 850), (3500, 3799, "Chaco y Formosa", 900), (3800, 3999, "Nordeste argentino", 1000),
    (2000, 2599, "Rosario y sur de Santa Fe", 400), (2600, 2699, "Sur de Santa Fe", 450),
    (2700, 2999, "Norte de Buenos Aires", 600), (1000, 1499, "Ciudad de Buenos Aires", 700),
    (1500, 1999, "Gran Buenos Aires", 720), (6000, 6299, "Oeste de Buenos Aires", 600),
    (6300, 6399, "La Pampa", 650), (6400, 6999, "Centro de Buenos Aires", 650),
    (7000, 7999, "Centro y sur de Buenos Aires", 900), (8000, 8199, "Bahía Blanca", 800),
    (8200, 8399, "Neuquén y sur de La Pampa", 1100), (8400, 8499, "Bariloche y Río Negro", 1500),
    (8500, 8599, "Río Negro", 1100), (9000, 9199, "Chubut", 1600), (9200, 9299, "Chubut (cordillera)", 1800),
    (9410, 9420, "Tierra del Fuego", 3300), (9300, 9499, "Santa Cruz", 2400),
]
PROVINCIAS = ["Buenos Aires", "Ciudad Autónoma de Buenos Aires", "Catamarca", "Chaco", "Chubut", "Córdoba", "Corrientes",
              "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza", "Misiones", "Neuquén", "Río Negro",
              "Salta", "San Juan", "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego", "Tucumán"]


def normalizar_cp(cp):
    """Acepta '5000' o el formato CPA 'X5000ABC'. Devuelve el número de 4 dígitos o None."""
    m = re.match(r"^\s*[A-Za-z]?(\d{4})(?:[A-Za-z]{3})?\s*$", cp or "")
    return int(m.group(1)) if m else None


def estimar_envio(cp, cantidad=1):
    """Costo aproximado de envío desde el almacén hasta el código postal."""
    n = normalizar_cp(cp)
    if n is None or n < 1000:
        return {"ok": False, "error": "Código postal inválido (ej: 5000 o X5000ABC)."}
    zona, km = next(((z, k) for d, h, z, k in ZONAS if d <= n <= h), ("Resto del país", 1200))
    cantidad = max(1, min(int(cantidad or 1), 10))
    costo = int(round((BASE + km * POR_KM) * (1 + EXTRA_UNIDAD * (cantidad - 1)) / 50.0) * 50)
    dias = "1 a 2 días hábiles" if km < 100 else "2 a 4 días hábiles" if km < 500 else "3 a 6 días hábiles" if km < 1000 \
        else "4 a 8 días hábiles" if km < 2000 else "6 a 12 días hábiles"
    return {"ok": True, "cp": n, "zona": zona, "km": km, "costo": costo,
            "costo_fmt": "$" + f"{costo:,}".replace(",", "."), "dias": dias}


def calcular_descuento(cupon, subtotal):
    """Descuento sobre el subtotal de productos (nunca sobre el envío ni mayor al subtotal)."""
    d = subtotal * cupon.valor / 100 if cupon.tipo == "porcentaje" else cupon.valor
    return round(min(d, subtotal), 2)
