"""Modelos de datos (SQLAlchemy) de ultra.snd."""
from datetime import date, datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from tienda import ALMACEN
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class Usuario(UserMixin, db.Model):
    """Cliente o administrador. Un usuario tiene varios pedidos."""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    es_admin = db.Column(db.Boolean, default=False)
    telefono = db.Column(db.String(20))
    pedidos = db.relationship("Pedido", backref="usuario", lazy=True)

    def get_id(self):
        return f"{self.id}:{self.password_hash[-16:]}"  # cambia al cambiar la contraseña

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


def _lineas(texto):
    return [l.strip() for l in (texto or "").splitlines() if l.strip()]


class Producto(db.Model):
    """Auricular a la venta."""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    categoria = db.Column(db.String(40), nullable=False)
    descripcion = db.Column(db.Text, default="")
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    imagen = db.Column(db.String(120))  # nombre del archivo en static/img/productos/
    tagline = db.Column(db.String(160))  # frase corta de la portada
    destacados = db.Column(db.Text)  # "Título|Texto", una por línea
    caja = db.Column(db.Text)  # contenido de la caja, uno por línea
    specs = db.Column(db.Text)  # "Nombre: valor", una por línea

    @property
    def destacados_lista(self):
        return [tuple(x.strip() for x in (l.split("|", 1) + [""])[:2]) for l in _lineas(self.destacados)]

    @property
    def caja_lista(self):
        return _lineas(self.caja)

    @property
    def specs_lista(self):
        return [tuple(x.strip() for x in (l.split(":", 1) + [""])[:2]) for l in _lineas(self.specs)]
    pedidos = db.relationship("Pedido", backref="producto", lazy=True)


class Pedido(db.Model):
    """Compra de un producto. Estados: pendiente -> pagado -> cobrado (o cancelado)."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(20), default="pendiente")
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cobro = db.Column(db.DateTime)
    numero = db.Column(db.String(16), unique=True)  # identificador público del pedido, ej: UL-7K3M-9QX2
    subtotal = db.Column(db.Float)  # productos, antes de descuento y envío
    descuento = db.Column(db.Float, default=0)
    envio = db.Column(db.Float, default=0)
    metodo_entrega = db.Column(db.String(12))  # None = todavía no eligió; retiro / domicilio
    dom_calle = db.Column(db.String(80))
    dom_numero = db.Column(db.String(10))
    dom_piso = db.Column(db.String(20))
    dom_ciudad = db.Column(db.String(80))
    dom_provincia = db.Column(db.String(40))
    dom_cp = db.Column(db.String(10))
    telefono = db.Column(db.String(20))
    cupon_id = db.Column(db.Integer, db.ForeignKey("cupon.id"))
    cupon_codigo = db.Column(db.String(20))
    pagos = db.relationship("Pago", backref="pedido", lazy=True, order_by="Pago.id")
    factura = db.relationship("Factura", backref="pedido", uselist=False)

    @property
    def codigo(self):
        """Número de pedido que ve el cliente (si un pedido viejo no tiene número, muestra #id)."""
        return self.numero or f"#{self.id}"

    @property
    def domicilio_texto(self):
        """Domicilio de entrega (que también es el de facturación) o el punto de retiro."""
        if self.metodo_entrega == "domicilio":
            piso = f", {self.dom_piso}" if self.dom_piso else ""
            return f"{self.dom_calle} {self.dom_numero}{piso}, {self.dom_ciudad}, {self.dom_provincia} (CP {self.dom_cp})"
        return f"Retiro en almacén: {ALMACEN}" if self.metodo_entrega == "retiro" else "Sin definir"

    @property
    def pago_aprobado(self):
        return next((p for p in self.pagos if p.estado == "aprobado"), None)


def _m(v):
    return "$" + f"{v:,.0f}".replace(",", ".")


class Cupon(db.Model):
    """Cupón de descuento: % o monto fijo, con compra mínima (en productos), vencimiento y tope de usos."""
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    tipo = db.Column(db.String(12), nullable=False)  # porcentaje / monto
    valor = db.Column(db.Float, nullable=False)
    minimo = db.Column(db.Float, default=0)
    vence = db.Column(db.Date)
    usos_max = db.Column(db.Integer)
    usos = db.Column(db.Integer, default=0)
    activo = db.Column(db.Boolean, default=True)
    publico = db.Column(db.Boolean, default=True)  # aparece en la página de cupones
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))  # si tiene dueño, solo ese cliente lo puede usar
    origen = db.Column(db.String(12), default="admin")  # admin / regalo
    pedido_origen_id = db.Column(db.Integer)  # pedido que generó el regalo

    def vigente(self):
        return bool(self.activo) and (self.vence is None or self.vence >= date.today()) \
            and (self.usos_max is None or self.usos < self.usos_max)

    @property
    def valor_texto(self):
        return f"{self.valor:g}%" if self.tipo == "porcentaje" else _m(self.valor)

    @property
    def descripcion(self):
        extra = f" en compras desde {_m(self.minimo)}" if self.minimo else ""
        return f"{self.valor_texto} de descuento{extra}"


class Pago(db.Model):
    """Intento de pago con tarjeta. NUNCA se guarda el número completo, el vencimiento ni el CVV."""
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False)
    marca = db.Column(db.String(30))
    ultimos4 = db.Column(db.String(4))
    tipo_tarjeta = db.Column(db.String(10))  # credito / debito
    cuotas = db.Column(db.Integer, default=1)
    monto = db.Column(db.Float, nullable=False)  # incluye recargo por cuotas
    estado = db.Column(db.String(20), nullable=False)  # pendiente_3ds / aprobado / rechazado
    referencia = db.Column(db.String(20), nullable=False)
    codigo_respuesta = db.Column(db.String(4))
    codigo_autorizacion = db.Column(db.String(8))
    mensaje = db.Column(db.String(120))
    otp_hash = db.Column(db.String(256))
    otp_expira = db.Column(db.DateTime)
    intentos = db.Column(db.Integer, default=0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    proveedor = db.Column(db.String(12), default="simulador")  # simulador / mercadopago
    mp_payment_id = db.Column(db.String(30), index=True)


class Factura(db.Model):
    """Factura B (consumidor final) simulada, emitida al aprobarse el pago."""
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedido.id"), nullable=False)
    pago_id = db.Column(db.Integer, db.ForeignKey("pago.id"), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    cliente_nombre = db.Column(db.String(80))
    cliente_email = db.Column(db.String(120))
    detalle = db.Column(db.String(160))
    subtotal = db.Column(db.Float)
    recargo = db.Column(db.Float, default=0)
    neto = db.Column(db.Float)
    iva = db.Column(db.Float)
    total = db.Column(db.Float)
    cae = db.Column(db.String(14))
    cae_vto = db.Column(db.Date)
    descuento = db.Column(db.Float, default=0)
    envio = db.Column(db.Float, default=0)
    domicilio = db.Column(db.String(250))
    cupon_codigo = db.Column(db.String(20))
