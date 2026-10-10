"""ultra.snd - tienda de auriculares con pagos con tarjeta, 3D Secure, facturas y cobros simulados.

Ejecutar:  python app.py   ->  https://overstuff-veggie-empirical.ngrok-free.dev/
"""
import base64
import os
import secrets
import smtplib
from dotenv import load_dotenv

from mp import crear_preferencia, firma_valida, sincronizar_pago


from email.message import EmailMessage
from datetime import date, datetime, timedelta
from functools import wraps
from time import time

from flask import Flask, Response, abort, jsonify, flash, redirect, render_template, request, session, url_for
from flask_login import (LoginManager, current_user, login_required,
                         login_user, logout_user)
from flask_wtf.csrf import CSRFProtect
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import update
from werkzeug.security import check_password_hash, generate_password_hash

from forms import CambiarClaveForm, DatosForm, CompraForm, CuponForm, EntregaForm, LoginForm, OlvideForm, OtpForm, PagoForm, ProductoForm, RegistroForm, RestablecerForm
from models import Cupon, Factura, Pago, Pedido, Producto, Usuario, db
from pagos import (EMISOR, RECHAZOS, aprobar_pedido, detectar_marca, emitir_factura, liquidacion,
                   monto_con_recargo, solo_digitos)
from seguridad import generar_captcha, puntaje_clave
from tienda import (ALMACEN, REGALO_DESDE, REGALO_DIAS, REGALO_MINIMO, REGALO_PORCENTAJE,
                    calcular_descuento, estimar_envio)

load_dotenv()
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Iniciá sesión para continuar."

SEED = [
    ("punchipun", "Over-ear · ANC", "Cancelación activa de ruido y 60 h de batería.", 30000, 12),
    ("snd.pro", "In-ear · TWS", "Auriculares inalámbricos con estuche de carga rápida.", 8000, 25),
    ("aurricularr", "Gaming · 7.1", "Sonido envolvente 7.1 y micrófono desmontable.", 15000, 8),
    ("ukulele", "Estudio · Cableado", "Respuesta plana para mezcla y masterización.", 20000, 5),
]
MIGRACIONES = {
    "producto": [("imagen", "VARCHAR(120)"), ("tagline", "VARCHAR(160)"), ("destacados", "TEXT"), ("caja", "TEXT"), ("specs", "TEXT")],
    "usuario": [("telefono", "VARCHAR(20)")],
    "cupon": [("usuario_id", "INTEGER"), ("origen", "VARCHAR(12)"), ("pedido_origen_id", "INTEGER")],
    "pedido": [("numero", "VARCHAR(16)"), ("subtotal", "FLOAT"), ("descuento", "FLOAT DEFAULT 0"), ("envio", "FLOAT DEFAULT 0"),
               ("metodo_entrega", "VARCHAR(12)"), ("dom_calle", "VARCHAR(80)"), ("dom_numero", "VARCHAR(10)"),
               ("dom_piso", "VARCHAR(20)"), ("dom_ciudad", "VARCHAR(80)"), ("dom_provincia", "VARCHAR(40)"),
               ("dom_cp", "VARCHAR(10)"), ("telefono", "VARCHAR(20)"), ("cupon_id", "INTEGER"), ("cupon_codigo", "VARCHAR(20)")],
    "factura": [("descuento", "FLOAT DEFAULT 0"), ("envio", "FLOAT DEFAULT 0"), ("domicilio", "VARCHAR(250)"), ("cupon_codigo", "VARCHAR(20)")],
    "pago": [("proveedor", "VARCHAR(12)"), ("mp_payment_id", "VARCHAR(30)")],
}
_ultima_limpieza = 0.0
EXTRA = {  # contenido de ejemplo de cada producto (el admin lo puede editar desde Productos)
    "punchipun": {
        "descripcion": "Los punchipun son auriculares over-ear pensados para desconectarte del mundo. Combinan cancelación activa de ruido, almohadillas de espuma viscoelástica y hasta 60 horas de batería para que los uses en el viaje, en la oficina o en casa sin pensar en cargarlos.",
        "tagline": "Silencio que se escucha.",
        "destacados": "Cancelación activa de ruido|Micrófonos que escuchan el entorno y lo anulan para que solo quedes con tu música.\n60 horas de batería|Una semana de uso diario con una carga; 10 minutos de carga rápida te dan 5 horas.\nModo ambiente|Con un toque oís lo que pasa a tu alrededor sin sacarte los auriculares.",
        "caja": "Auriculares punchipun\nEstuche rígido de viaje\nCable USB-C de carga\nCable de audio de 3,5 mm\nGuía rápida y garantía",
        "specs": "Tipo: Over-ear cerrado\nConectividad: Bluetooth 5.3 o cable\nBatería: hasta 60 h\nCarga: USB-C, 10 min = 5 h\nPeso: 260 g"},
    "snd.pro": {
        "descripcion": "Los snd.pro son auriculares inalámbricos livianos y discretos. Entran firmes en la oreja, suenan con graves profundos y vienen con un estuche que los carga varias veces durante la semana.",
        "tagline": "Todo tu sonido, sin cables.",
        "destacados": "Sonido sin cables|Conexión Bluetooth estable y baja latencia para videos, juegos y llamadas.\nEstuche de carga rápida|El estuche suma hasta 30 horas; 5 minutos de carga = 1 hora de música.\nControles táctiles|Pausá, cambiá de tema o contestá llamadas con un toque.",
        "caja": "Auriculares snd.pro (izquierdo y derecho)\nEstuche de carga\nCable USB-C\nAlmohadillas de silicona S, M y L\nGuía rápida y garantía",
        "specs": "Tipo: In-ear inalámbrico\nConectividad: Bluetooth 5.3\nBatería: 7 h + 23 h con el estuche\nResistencia: IPX4 (salpicaduras)\nPeso: 5 g cada uno"},
    "aurricularr": {
        "descripcion": "Los aurricularr están hechos para jugar horas sin cansarte. Ofrecen sonido envolvente 7.1, micrófono desmontable con cancelación de ruido y almohadillas acolchadas que no aprietan.",
        "tagline": "Escuchá dónde está cada enemigo.",
        "destacados": "Sonido envolvente 7.1|Ubicás pasos y disparos con precisión en cualquier juego.\nMicrófono desmontable|Voz clara en las partidas; lo sacás cuando no lo necesitás.\nLuces RGB|Iluminación personalizable que acompaña tu setup.",
        "caja": "Auriculares aurricularr\nMicrófono desmontable\nCable USB de 2 m\nAdaptador de 3,5 mm\nGuía rápida y garantía",
        "specs": "Tipo: Over-ear gamer\nSonido: 7.1 virtual\nConexión: USB o 3,5 mm\nMicrófono: cardioide, desmontable\nPeso: 320 g"},
    "ukulele": {
        "descripcion": "Los ukulele son auriculares de estudio de respuesta plana. Te muestran la mezcla tal como es, con cable desmontable y una construcción resistente para el uso diario en cabina o en casa.",
        "tagline": "Lo que grabaste, tal como sonó.",
        "destacados": "Respuesta plana|Sin realzar graves ni agudos: ideal para mezclar y masterizar.\nCable desmontable|Cambiás el cable en segundos y no te quedás sin auriculares.\nAlmohadillas de espuma|Cómodos en sesiones largas y aíslan del ruido del estudio.",
        "caja": "Auriculares ukulele\nCable recto de 3 m\nCable espiralado de 1,5 m\nAdaptador de 6,3 mm\nBolsa de transporte\nGuía rápida y garantía",
        "specs": "Tipo: Over-ear cerrado de estudio\nRespuesta: 10 Hz – 30 kHz\nImpedancia: 38 Ω\nConexión: cable 3,5 mm / 6,3 mm\nPeso: 285 g"},
}
_intentos = {}  # limitador de intentos en memoria (para producción: Redis / Flask-Limiter)
_captchas = {}  # captchas vigentes (solo en el servidor): id -> (texto, vencimiento)


def limitado(clave, maximo, ventana):
    """True si la clave ya hizo `maximo` intentos en los últimos `ventana` segundos."""
    ahora = time()
    _intentos[clave] = [t for t in _intentos.get(clave, []) if ahora - t < ventana]
    return len(_intentos[clave]) >= maximo


def registrar_intento(clave):
    _intentos.setdefault(clave, []).append(time())


def url_segura(destino):
    """Evita open redirect: solo rutas internas."""
    return bool(destino) and destino.startswith("/") and not destino.startswith("//") and "\\" not in destino


def nuevo_numero_pedido():
    """Número de pedido único y no secuencial, ej: UL-7K3M-9QX2 (sin caracteres que se confundan)."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        n = "UL-" + "".join(secrets.choice(alfabeto) for _ in range(4)) + "-" + "".join(secrets.choice(alfabeto) for _ in range(4))
        if not Pedido.query.filter_by(numero=n).first():
            return n


def cupones_del_usuario(u, excluir=None):
    """(disponibles, canjeados): cupones vigentes que el cliente aún no usó (generales y personales) y sus pedidos pagados con cupón."""
    usados = {p.cupon_id for p in Pedido.query.filter(Pedido.usuario_id == u.id, Pedido.cupon_id.isnot(None),
                                                      Pedido.estado != "cancelado", Pedido.id != (excluir or 0))}
    candidatos = Cupon.query.filter(db.or_(db.and_(Cupon.publico.is_(True), Cupon.usuario_id.is_(None)), Cupon.usuario_id == u.id)).all()
    disponibles = [c for c in candidatos if c.vigente() and c.id not in usados]
    canjeados = Pedido.query.filter(Pedido.usuario_id == u.id, Pedido.cupon_id.isnot(None),
                                    Pedido.estado.in_(["pagado", "cobrado"])).order_by(Pedido.id.desc()).all()
    return disponibles, canjeados


def reiniciar_sesion():
    """Sesión nueva (anti fijación) conservando el cupón que el visitante activó."""
    cupon = session.get("cupon")
    session.clear()
    if cupon:
        session["cupon"] = cupon


def enviar_correo(destino, asunto, texto):
    """Envía un email por SMTP (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM). Lanza excepción si falla."""
    puerto = int(os.environ.get("SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["Subject"], msg["To"] = asunto, destino
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-responder@ultra.snd"
    msg.set_content(texto)
    clase = smtplib.SMTP_SSL if puerto == 465 else smtplib.SMTP
    with clase(os.environ["SMTP_HOST"], puerto, timeout=15) as s:
        if puerto != 465:
            s.starttls()
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        s.send_message(msg)


def enviar_enlace(destino, enlace):
    """Manda el enlace de recuperación; sin SMTP configurado lo imprime en la consola del servidor."""
    texto = (f"Entrá a este enlace para elegir una contraseña nueva (vence en 30 minutos y sirve una sola vez):\n{enlace}\n\n"
             "Si no lo pediste, ignorá este mensaje.")
    if not os.environ.get("SMTP_HOST"):
        print(f"\n[ultra.snd] SMTP sin configurar: el email NO se envió. Enlace para {destino}:\n{enlace}\n", flush=True)
        return
    try:
        enviar_correo(destino, "ultra.snd: restablecer contraseña", texto)
    except Exception as e:  # el visitante no ve el error; queda en la consola
        print(f"[ultra.snd] No se pudo enviar el email a {destino}: {e}", flush=True)


def nuevo_captcha():
    """Crea un captcha y devuelve {id, img}. La imagen va dentro de la página y el id en un campo oculto del formulario."""
    ahora = time()
    for k in [k for k, (_, v) in _captchas.items() if v < ahora]:
        del _captchas[k]
    if len(_captchas) > 5000:
        _captchas.clear()
    texto, svg = generar_captcha()
    token = secrets.token_urlsafe(12)
    _captchas[token] = (texto, ahora + 600)
    return {"id": token, "img": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()}


def captcha_ok(ingresado):
    """Valida el captcha una sola vez (se consume al comprobarlo), identificado por el campo oculto captcha_id."""
    texto, vence = _captchas.pop(request.form.get("captcha_id", ""), (None, 0))
    return bool(texto) and time() < vence and secrets.compare_digest(texto.encode(), (ingresado or "").strip().upper().encode())


def clave_secreta(carpeta):
    """SECRET_KEY desde variable de entorno o generada una vez y guardada en instance/."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    ruta = os.path.join(carpeta, "secret.key")
    if not os.path.exists(ruta):
        with open(ruta, "w") as f:
            f.write(secrets.token_hex(32))
    with open(ruta) as f:
        return f.read().strip()


def admin_required(f):
    """Permite el acceso solo a administradores."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("admin_login"))
        if not current_user.es_admin:
            abort(404)  # no revela que el panel existe
        return f(*args, **kwargs)
    return wrapper


def pedido_de(id, permitir_admin=False):
    """Obtiene un pedido verificando que pertenezca al usuario (control de acceso)."""
    p = db.get_or_404(Pedido, id)
    if p.usuario_id != current_user.id and not (permitir_admin and current_user.es_admin):
        abort(403)
    return p


def create_app():
    app = Flask(__name__)
    csrf = CSRFProtect(app)
    # La base queda SIEMPRE en instance/ junto a app.py, sin importar desde dónde se ejecute (o en DATABASE_PATH si se define en .env)
    carpeta_bd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
    os.makedirs(carpeta_bd, exist_ok=True)
    ruta_bd = os.path.abspath(os.environ.get("DATABASE_PATH") or os.path.join(carpeta_bd, "ultra_snd_v2.db"))
    os.makedirs(os.path.join(app.static_folder, "img", "productos"), exist_ok=True)
    https = os.environ.get("HTTPS") == "1"
    app.config.update(
        SECRET_KEY=clave_secreta(carpeta_bd),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + ruta_bd.replace("\\", "/"),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=https,
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30), WTF_CSRF_TIME_LIMIT=3600,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024)  # tope de subida: 16 MB
    print(f"[ultra.snd] Base de datos: {ruta_bd}" + ("  <- BASE NUEVA: no existía y se creó vacía" if not os.path.exists(ruta_bd) else ""), flush=True)
    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def cargar_usuario(user_id):
        uid, _, sello = user_id.partition(":")
        u = db.session.get(Usuario, int(uid)) if uid.isdigit() else None
        return u if u and u.get_id() == user_id else None  # sesión inválida si cambió la contraseña

    @app.before_request
    def liberar_reservas():
        """Los pedidos sin pagar se cancelan a la hora y devuelven su stock: el stock mostrado es siempre el realmente disponible."""
        global _ultima_limpieza
        if request.endpoint == "static" or time() - _ultima_limpieza < 60:
            return
        _ultima_limpieza = time()
        limite = datetime.utcnow() - timedelta(minutes=60)
        for p in Pedido.query.filter(Pedido.estado == "pendiente", Pedido.fecha < limite).all():
            if any(pg.estado == "pendiente_mp" for pg in p.pagos):
                continue  # pago en revisión en Mercado Pago: todavía no se libera el stock
            p.estado = "cancelado"
            p.producto.stock += p.cantidad
            for pg in p.pagos:
                if pg.estado == "pendiente_3ds":
                    pg.estado, pg.codigo_respuesta, pg.mensaje, pg.otp_hash = "rechazado", "CA", "Pedido vencido", None
        db.session.commit()

    @app.after_request
    def cabeceras_seguridad(r):
        r.headers["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
                                                "font-src https://fonts.gstatic.com; img-src 'self' data:; "
                                                "frame-ancestors 'none'; form-action 'self' https://*.mercadopago.com https://*.mercadopago.com.ar; base-uri 'self'")
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Referrer-Policy"] = "same-origin"
        r.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if https:
            r.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.endpoint != "static":
            r.headers["Cache-Control"] = "no-store"  # no cachear páginas con datos personales
        return r

    @app.template_filter("money")
    def money(v):
        return "$" + f"{v:,.0f}".replace(",", ".")

    @app.template_filter("money2")
    def money2(v):
        return "$" + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    app.jinja_env.globals.update(ALMACEN=ALMACEN, REGALO_DESDE=REGALO_DESDE, nuevo_captcha=nuevo_captcha)

    @app.template_filter("fecha")
    def fecha(v):  # UTC -> hora de Argentina (UTC-3)
        return (v - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M") if v else "-"

    # ---------- Catálogo ----------
    @app.route("/")
    def index():
        return render_template("index.html", productos=Producto.query.all())

    @app.route("/catalogo")
    def catalogo():
        return render_template("catalogo.html", productos=Producto.query.all())

    @app.route("/producto/<int:id>", methods=["GET", "POST"])
    def producto(id):
        p = db.get_or_404(Producto, id)
        form = CompraForm()
        if form.validate_on_submit():
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            reservadas = db.session.execute(  # descuento atómico: dos clientes no pueden quedarse con la misma última unidad
                update(Producto).where(Producto.id == p.id, Producto.stock >= form.cantidad.data)
                .values(stock=Producto.stock - form.cantidad.data)).rowcount
            if not reservadas:
                db.session.refresh(p)
                flash(f"Solo quedan {p.stock} unidades.", "error")
            else:
                pedido = Pedido(numero=nuevo_numero_pedido(), usuario_id=current_user.id, producto_id=p.id,
                                cantidad=form.cantidad.data, subtotal=p.precio * form.cantidad.data,
                                descuento=0, envio=0, total=p.precio * form.cantidad.data)
                db.session.add(pedido)
                db.session.commit()
                flash("Pedido creado. Elegí cómo querés recibirlo.", "ok")
                return redirect(url_for("entrega", id=pedido.id))
        return render_template("producto.html", p=p, form=form)

    # ---------- Autenticación ----------
    @app.route("/captcha/nuevo")
    def captcha_nuevo():
        clave = f"captcha:{request.remote_addr}"
        if limitado(clave, 60, 60):
            return jsonify(error="Demasiadas solicitudes"), 429
        registrar_intento(clave)
        return jsonify(nuevo_captcha())

    @app.route("/registro", methods=["GET", "POST"])
    def registro():
        form = RegistroForm()
        if form.validate_on_submit():
            clave = f"registro:{request.remote_addr}"
            if limitado(clave, 5, 3600):
                flash("Demasiados registros desde esta conexión. Probá más tarde.", "error")
            elif not captcha_ok(form.captcha.data):
                registrar_intento(clave)
                flash("El código de la imagen es incorrecto.", "error")
            elif Usuario.query.filter_by(email=form.email.data.lower()).first():
                flash("Ese email ya está registrado.", "error")
            else:
                registrar_intento(clave)
                u = Usuario(nombre=form.nombre.data, email=form.email.data.lower(), es_admin=False)  # los admin solo se crean con crear_admin.py
                u.set_password(form.password.data)
                db.session.add(u)
                db.session.commit()
                reiniciar_sesion()
                login_user(u)
                session.permanent = True
                return redirect(url_for("index"))
        return render_template("auth.html", form=form, titulo="Crear cuenta", medidor=True)

    def procesar_login(form, admin):
        """Valida captcha y credenciales. Cada tipo de cuenta ingresa solo por su puerta."""
        clave = f"{'admin' if admin else 'login'}:{request.remote_addr}:{form.email.data.lower()}"
        if limitado(clave, 5, 300):
            flash("Demasiados intentos fallidos. Esperá 5 minutos.", "error")
            return None
        if not captcha_ok(form.captcha.data):
            registrar_intento(clave)
            flash("El código de la imagen es incorrecto.", "error")
            return None
        u = Usuario.query.filter_by(email=form.email.data.lower()).first()
        if u and u.check_password(form.password.data) and bool(u.es_admin) == admin:
            _intentos.pop(clave, None)
            reiniciar_sesion()  # sesión nueva al ingresar (evita fijación de sesión)
            login_user(u)
            session.permanent = True
            return u
        registrar_intento(clave)
        flash("Email o contraseña incorrectos.", "error")
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        form = LoginForm()
        if form.validate_on_submit() and procesar_login(form, admin=False):
            destino = request.args.get("next")
            return redirect(destino if url_segura(destino) else url_for("index"))
        return render_template("auth.html", form=form, titulo="Iniciar sesión")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        form = LoginForm()
        if form.validate_on_submit() and procesar_login(form, admin=True):
            return redirect(url_for("admin_productos"))
        return render_template("auth.html", form=form, titulo="Acceso de administración")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        session.clear()
        return redirect(url_for("index"))

    def firmador():
        return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="reset-clave")

    @app.route("/olvide", methods=["GET", "POST"])
    def olvide():
        form = OlvideForm()
        if form.validate_on_submit():
            clave = f"olvide:{request.remote_addr}"
            if limitado(clave, 5, 3600):
                flash("Demasiados pedidos. Probá más tarde.", "error")
            elif not captcha_ok(form.captcha.data):
                registrar_intento(clave)
                flash("El código de la imagen es incorrecto.", "error")
            else:
                registrar_intento(clave)
                u = Usuario.query.filter_by(email=form.email.data.lower()).first()
                if u and not u.es_admin:  # las cuentas de administración se recuperan por consola
                    token = firmador().dumps({"u": u.id, "s": u.password_hash[-16:]})  # el sello lo vuelve de un solo uso
                    ruta = url_for("restablecer", token=token)
                    if os.environ.get("MODO_DEMO") == "1":  # solo para demos locales: salta el email
                        flash("Modo demo: no se envió ningún email. Elegí tu nueva contraseña acá.", "ok")
                        return redirect(ruta)
                    enviar_enlace(u.email, (os.environ.get("BASE_URL") or request.url_root.rstrip("/")) + ruta)
                flash("Si el email está registrado, te enviamos un enlace para restablecer la contraseña (vence en 30 minutos).", "ok")
                return redirect(url_for("login"))
        return render_template("auth.html", form=form, titulo="Recuperar contraseña")

    @app.route("/restablecer/<token>", methods=["GET", "POST"])
    def restablecer(token):
        try:
            datos = firmador().loads(token, max_age=1800)
        except BadSignature:  # incluye enlaces vencidos
            datos = None
        u = db.session.get(Usuario, datos["u"]) if datos else None
        if not u or u.es_admin or u.password_hash[-16:] != datos["s"]:
            flash("El enlace es inválido, ya se usó o venció. Pedí uno nuevo.", "error")
            return redirect(url_for("olvide"))
        form = RestablecerForm()
        if form.validate_on_submit():
            u.set_password(form.password.data)
            db.session.commit()
            flash("Contraseña actualizada. Ya podés iniciar sesión.", "ok")
            return redirect(url_for("login"))
        return render_template("auth.html", form=form, titulo="Nueva contraseña", medidor=True)

    @app.route("/cuenta", methods=["GET", "POST"])
    @login_required
    def cuenta():
        """Panel de usuario: datos personales y cambio de contraseña (dos formularios, el CSRF lo valida CSRFProtect)."""
        datos = DatosForm(prefix="d", meta={"csrf": False}, obj=current_user)
        clave = CambiarClaveForm(prefix="c", meta={"csrf": False})
        if request.method == "POST" and request.form.get("d-guardar") and datos.validate():
            email = datos.email.data.lower()
            cambia_email = email != current_user.email
            if cambia_email and not current_user.check_password(datos.password_actual.data or ""):
                flash("Para cambiar el email confirmá con tu contraseña actual.", "error")
            elif cambia_email and Usuario.query.filter_by(email=email).first():
                flash("Ese email ya está en uso.", "error")
            else:
                current_user.nombre, current_user.email = datos.nombre.data.strip(), email
                current_user.telefono = (datos.telefono.data or "").strip() or None
                db.session.commit()
                flash("Datos actualizados.", "ok")
                return redirect(url_for("cuenta"))
        elif request.method == "POST" and request.form.get("c-guardar") and clave.validate():
            tope = f"clave:{current_user.id}"
            nueva = clave.password.data
            if limitado(tope, 5, 600):
                flash("Demasiados intentos. Esperá 10 minutos.", "error")
            elif not current_user.check_password(clave.actual.data):
                registrar_intento(tope)
                flash("La contraseña actual es incorrecta.", "error")
            elif nueva == clave.actual.data:
                flash("La nueva contraseña debe ser distinta de la actual.", "error")
            elif current_user.es_admin and (len(nueva) < 12 or puntaje_clave(nueva) < 4):
                flash("Las cuentas de administración requieren 12+ caracteres con mayúsculas, minúsculas, números y símbolos.", "error")
            else:
                u = current_user._get_current_object()
                u.set_password(nueva)
                db.session.commit()
                _intentos.pop(tope, None)
                session.clear()
                login_user(u)  # sesión nueva con el sello actualizado; las demás sesiones quedan cerradas
                session.permanent = True
                flash("Contraseña actualizada. Se cerraron las demás sesiones abiertas.", "ok")
                return redirect(url_for("cuenta"))
        return render_template("cuenta.html", datos=datos, clave=clave)

    # ---------- Pedidos, pagos y facturas ----------
    @app.route("/pedidos")
    @login_required
    def pedidos():
        lista = Pedido.query.filter_by(usuario_id=current_user.id).order_by(Pedido.id.desc()).all()
        return render_template("pedidos.html", pedidos=lista)

    @app.route("/pedido/<int:id>")
    @login_required
    def detalle_pedido(id):
        p = pedido_de(id, permitir_admin=True)
        return render_template("pedido.html", p=p, regalo=Cupon.query.filter_by(pedido_origen_id=p.id).first())

    def rechazar(pago, codigo, mensaje):
        pago.estado, pago.codigo_respuesta, pago.mensaje, pago.otp_hash = "rechazado", codigo, mensaje, None
        db.session.commit()
        session.pop(f"otp_{pago.id}", None)
        flash(f"Pago rechazado: {mensaje} (código {codigo}).", "error")
        return redirect(url_for("pagar", id=pago.pedido_id))

    @app.route("/pedido/<int:id>/pagar", methods=["GET", "POST"])
    @login_required
    def pagar(id):
        pedido = pedido_de(id)
        if pedido.estado != "pendiente":
            flash("Este pedido ya no admite pagos.", "error")
            return redirect(url_for("detalle_pedido", id=id))
        if pedido.metodo_entrega is None:
            return redirect(url_for("entrega", id=id))  # primero se elige la entrega
        form = PagoForm()
        if form.validate_on_submit():
            clave = f"pago:{current_user.id}"
            if limitado(clave, 5, 600):
                flash("Demasiados intentos de pago. Probá de nuevo en 10 minutos.", "error")
                return redirect(url_for("detalle_pedido", id=id))
            registrar_intento(clave)
            numero = solo_digitos(form.numero.data)
            tipo = form.tipo.data
            cuotas = int(form.cuotas.data) if tipo == "credito" else 1
            pago = Pago(pedido_id=pedido.id, marca=detectar_marca(numero), ultimos4=numero[-4:], tipo_tarjeta=tipo,
                        cuotas=cuotas, monto=monto_con_recargo(pedido.total, cuotas), estado="pendiente_3ds",
                        referencia="PAY-" + secrets.token_hex(5).upper())
            db.session.add(pago)
            db.session.flush()
            if numero in RECHAZOS:  # respuesta simulada del banco emisor
                return rechazar(pago, *RECHAZOS[numero])
            otp = f"{secrets.randbelow(10**6):06d}"  # 3D Secure: código de un solo uso
            pago.otp_hash = generate_password_hash(otp)
            pago.otp_expira = datetime.utcnow() + timedelta(minutes=5)
            db.session.commit()
            session[f"otp_{pago.id}"] = otp  # solo para mostrar el "SMS" simulado
            return redirect(url_for("verificar", id=pago.id))
        return render_template("pagar.html", pedido=pedido, form=form)

    @app.route("/pago/<int:id>/verificar", methods=["GET", "POST"])
    @login_required
    def verificar(id):
        pago = db.get_or_404(Pago, id)
        pedido = pago.pedido
        if pedido.usuario_id != current_user.id:
            abort(403)
        if pago.estado != "pendiente_3ds" or pedido.estado != "pendiente":
            return redirect(url_for("detalle_pedido", id=pedido.id))
        if datetime.utcnow() > pago.otp_expira:
            return rechazar(pago, "XV", "Verificación 3D Secure vencida")
        form = OtpForm()
        if form.validate_on_submit():
            if check_password_hash(pago.otp_hash, form.codigo.data):
                pago.estado, pago.codigo_respuesta, pago.mensaje = "aprobado", "00", "Aprobada"
                pago.codigo_autorizacion, pago.otp_hash = secrets.token_hex(3).upper(), None
                if aprobar_pedido(pedido, pago):
                    flash("Por tu compra grande te regalamos un cupón. Lo ves en «Mis cupones».", "ok")
                db.session.commit()
                session.pop(f"otp_{pago.id}", None)
                flash("Pago aprobado. Tu factura ya está disponible.", "ok")
                return redirect(url_for("detalle_pedido", id=pedido.id))
            pago.intentos += 1
            db.session.commit()
            if pago.intentos >= 3:
                return rechazar(pago, "XA", "Demasiados intentos de verificación")
            flash("Código incorrecto.", "error")
        return render_template("verificar.html", pago=pago, form=form, codigo=session.get(f"otp_{pago.id}"))

    @app.route("/pedido/<int:id>/cancelar", methods=["POST"])
    @login_required
    def cancelar(id):
        pedido = pedido_de(id)
        if any(pg.estado == "pendiente_mp" for pg in pedido.pagos):  # hay un pago en revisión en Mercado Pago
            flash("Tenés un pago en revisión en Mercado Pago: no se puede cancelar hasta que se resuelva.", "error")
            return redirect(url_for("detalle_pedido", id=id))
        if pedido.estado == "pendiente":
            pedido.estado = "cancelado"
            pedido.producto.stock += pedido.cantidad  # devuelve el stock
            for pg in pedido.pagos:
                if pg.estado == "pendiente_3ds":
                    pg.estado, pg.codigo_respuesta, pg.mensaje, pg.otp_hash = "rechazado", "CA", "Pedido cancelado", None
            db.session.commit()
            flash("Pedido cancelado.", "ok")
        return redirect(url_for("pedidos"))

    @app.route("/factura/<int:id>")
    @login_required
    def factura(id):
        f = db.get_or_404(Factura, id)
        if f.pedido.usuario_id != current_user.id and not current_user.es_admin:
            abort(403)
        return render_template("factura.html", f=f, e=EMISOR)

    @app.route("/pedido/<int:id>/metodo")
    @login_required
    def metodo_pago(id):
        """Paso previo al pago: el cliente elige entre tarjeta (simulador con 3D Secure) y Mercado Pago."""
        pedido = pedido_de(id)
        if pedido.estado != "pendiente":
            flash("Este pedido ya no admite pagos.", "error")
            return redirect(url_for("detalle_pedido", id=id))
        if pedido.metodo_entrega is None:
            return redirect(url_for("entrega", id=id))
        return render_template("metodo.html", pedido=pedido, en_revision=any(pg.estado == "pendiente_mp" for pg in pedido.pagos))

    @app.route("/pedido/<int:id>/pagar-mp", methods=["POST"])
    @login_required
    def pagar_mp(id):
        pedido = pedido_de(id)
        if pedido.estado != "pendiente":
            flash("Este pedido ya no admite pagos.", "error")
            return redirect(url_for("detalle_pedido", id=id))
        if pedido.metodo_entrega is None:
            return redirect(url_for("entrega", id=id))
        if any(pg.estado == "pendiente_mp" for pg in pedido.pagos):
            flash("Tenés un pago en revisión en Mercado Pago. Te avisamos cuando se acredite.", "ok")
            return redirect(url_for("detalle_pedido", id=id))
        clave = f"pagomp:{current_user.id}"
        if limitado(clave, 10, 600):
            flash("Demasiados intentos. Probá de nuevo en 10 minutos.", "error")
            return redirect(url_for("detalle_pedido", id=id))
        registrar_intento(clave)
        base = os.environ.get("BASE_URL") or request.url_root.rstrip("/")
        try:
            return redirect(crear_preferencia(pedido, base))
        except Exception as e:
            print(f"[ultra.snd] Error con Mercado Pago: {e}", flush=True)
            flash("No pudimos conectar con Mercado Pago. Probá de nuevo.", "error")
            return redirect(url_for("metodo_pago", id=id))

    @app.route("/pedido/<int:id>/mp-retorno")
    @login_required
    def mp_retorno(id):
        """A donde vuelve el cliente desde Mercado Pago. Confirma el pago contra la API (no confía en la URL)."""
        pedido = pedido_de(id)
        pid = request.args.get("payment_id") or request.args.get("collection_id")
        if pid and pid.isdigit():
            try:
                sincronizar_pago(pid)
            except Exception as e:
                print(f"[ultra.snd] No se pudo sincronizar el pago {pid}: {e}", flush=True)
        if pedido.estado == "pagado":
            flash("Pago aprobado. Tu factura ya está disponible.", "ok")
        elif any(pg.estado == "pendiente_mp" for pg in pedido.pagos):
            flash("Tu pago está en revisión. Cuando se acredite, el pedido pasa a pagado.", "ok")
        else:
            flash("El pago no se completó. Podés intentarlo de nuevo.", "error")
            return redirect(url_for("metodo_pago", id=id))
        return redirect(url_for("detalle_pedido", id=id))

   
    @app.route("/webhook/mercadopago", methods=["POST"])
    @csrf.exempt
    def webhook_mp():
        if not firma_valida(request):
            print("[MP] Firma inválida", flush=True)
            return "Firma inválida", 401

        datos = request.get_json(silent=True) or {}

        tipo = request.args.get("type") or datos.get("type")
        pid = request.args.get("data.id") or (datos.get("data") or {}).get("id")

        print(f"[MP] Notificación recibida: tipo={tipo}, id={pid}", flush=True)

        if tipo != "payment" or not pid:
            print("[MP] Notificación sin tipo o ID de pago válido", flush=True)
            return "", 200

        try:
            pago = sincronizar_pago(str(pid))

            if pago is None:
                print(f"[MP] No se pudo sincronizar el pago {pid}", flush=True)

        except Exception as e:
            print(f"[ultra.snd] Error en webhook MP: {e}", flush=True)
            return "", 500

        return "", 200
    
    # ---------- Envío y cupones ----------
    @app.route("/api/envio")
    def api_envio():
        clave = f"envio:{request.remote_addr}"
        if limitado(clave, 30, 60):
            return jsonify(ok=False, error="Demasiadas consultas. Esperá un minuto."), 429
        registrar_intento(clave)
        return jsonify(estimar_envio(request.args.get("cp", ""), request.args.get("cantidad", 1, type=int)))

    @app.route("/cupon/activar", methods=["POST"])
    def activar_cupon():
        clave = f"cupon:{request.remote_addr}"
        codigo = request.form.get("codigo", "").strip().upper()[:20]
        if limitado(clave, 10, 300):
            flash("Demasiados intentos. Probá en unos minutos.", "error")
            return redirect(url_for("cupones"))
        registrar_intento(clave)
        c = Cupon.query.filter_by(codigo=codigo).first()
        if not c or not c.activo or (c.usuario_id and (not current_user.is_authenticated or current_user.id != c.usuario_id)):
            flash("Ese cupón no existe.", "error")
        elif c.vence and c.vence < date.today():
            flash(f"El cupón {c.codigo} venció el {c.vence.strftime('%d/%m/%Y')}.", "error")
        elif c.usos_max is not None and c.usos >= c.usos_max:
            flash(f"El cupón {c.codigo} está agotado.", "error")
        else:
            previo = None
            if current_user.is_authenticated:
                previo = Pedido.query.filter(Pedido.usuario_id == current_user.id, Pedido.cupon_id == c.id,
                                             Pedido.estado.in_(["pagado", "cobrado"])).first()
            if previo:
                flash(f"Ya canjeaste el cupón {c.codigo} en el pedido {previo.codigo}. Cada cupón se usa una sola vez.", "error")
            else:
                session["cupon"] = c.codigo
                flash(f"Cupón {c.codigo} activado ({c.descripcion}). Se aplica al elegir la entrega de tu pedido.", "ok")
        return redirect(url_for("cupones"))

    @app.route("/cupones")
    def cupones():
        """Cupones con su estado para el cliente: disponible, ya usado, vencido o agotado."""
        yo = current_user.id if current_user.is_authenticated else 0
        todos = Cupon.query.filter(Cupon.activo.is_(True), db.or_(db.and_(Cupon.publico.is_(True), Cupon.usuario_id.is_(None)),
                                                                  Cupon.usuario_id == yo)).order_by(Cupon.id).all()
        usados, canjeados = {}, []
        if current_user.is_authenticated:
            for p in Pedido.query.filter(Pedido.usuario_id == yo, Pedido.cupon_id.isnot(None), Pedido.estado != "cancelado").order_by(Pedido.id):
                usados[p.cupon_id] = p
            canjeados = cupones_del_usuario(current_user)[1]

        def estado(c):
            p = usados.get(c.id)
            if p:
                return "usado", f"Ya lo usaste en el pedido {p.codigo}" + ("" if p.estado in ("pagado", "cobrado") else " (pendiente de pago)")
            if c.vence and c.vence < date.today():
                return "vencido", "Vencido"
            if c.usos_max is not None and c.usos >= c.usos_max:
                return "agotado", "Agotado"
            return "disponible", ""

        tarjetas = [(c, *estado(c)) for c in todos]
        return render_template("cupones.html", generales=[t for t in tarjetas if t[0].usuario_id is None],
                               propios=[t for t in tarjetas if t[0].usuario_id is not None], canjeados=canjeados,
                               cupon_activo=session.get("cupon"))

    def cupon_valido(codigo, pedido):
        c = Cupon.query.filter_by(codigo=codigo).first()
        if not c or not c.activo or (c.usuario_id and c.usuario_id != current_user.id):
            return None, "El cupón no existe o no está activo."
        if not c.vigente():
            return None, "El cupón está vencido o agotado."
        if pedido.subtotal < c.minimo:
            minimo = f"${c.minimo:,.0f}".replace(",", ".")
            return None, f"Este cupón se usa en compras de productos desde {minimo}."
        usado = Pedido.query.filter(Pedido.usuario_id == current_user.id, Pedido.cupon_id == c.id,
                                    Pedido.estado != "cancelado", Pedido.id != pedido.id).first()
        if usado:
            return None, "Ya usaste este cupón en otra compra."
        return c, None

    @app.route("/pedido/<int:id>/entrega", methods=["GET", "POST"])
    @login_required
    def entrega(id):
        pedido = pedido_de(id)
        if pedido.estado != "pendiente":
            return redirect(url_for("detalle_pedido", id=id))
        form = EntregaForm(obj=pedido)
        if request.method == "GET":
            form.metodo_entrega.data = pedido.metodo_entrega or "retiro"
            form.cupon_codigo.data = pedido.cupon_codigo or session.get("cupon", "")
            form.telefono.data = form.telefono.data or current_user.telefono
        if form.validate_on_submit():
            codigo = (form.cupon_codigo.data or "").strip().upper()
            cupon, error = cupon_valido(codigo, pedido) if codigo else (None, None)
            if error:
                flash(error, "error")
            else:
                pedido.metodo_entrega = form.metodo_entrega.data
                if pedido.metodo_entrega == "domicilio":
                    pedido.dom_calle, pedido.dom_numero = form.dom_calle.data.strip(), form.dom_numero.data.strip()
                    pedido.dom_piso, pedido.dom_ciudad = (form.dom_piso.data or "").strip(), form.dom_ciudad.data.strip()
                    pedido.dom_provincia, pedido.dom_cp = form.dom_provincia.data, form.dom_cp.data.strip().upper()
                    pedido.telefono = form.telefono.data.strip()
                    pedido.envio = estimar_envio(pedido.dom_cp, pedido.cantidad)["costo"]
                else:  # retiro: no se guarda ninguna dirección
                    pedido.dom_calle = pedido.dom_numero = pedido.dom_piso = pedido.dom_ciudad = None
                    pedido.dom_provincia = pedido.dom_cp = pedido.telefono = None
                    pedido.envio = 0
                pedido.descuento = calcular_descuento(cupon, pedido.subtotal) if cupon else 0
                pedido.cupon_id, pedido.cupon_codigo = (cupon.id, cupon.codigo) if cupon else (None, None)
                pedido.total = round(pedido.subtotal - pedido.descuento + pedido.envio, 2)
                db.session.commit()
                if request.form.get("continuar"):
                    session.pop("cupon", None)
                    return redirect(url_for("metodo_pago", id=id))
                flash("Totales actualizados.", "ok")
        disponibles, canjeados = cupones_del_usuario(current_user, excluir=pedido.id)
        return render_template("entrega.html", form=form, pedido=pedido, disponibles=disponibles, canjeados=canjeados)

    # ---------- Administración ----------
    @app.route("/admin/productos")
    @admin_required
    def admin_productos():
        return render_template("admin_productos.html", productos=Producto.query.all())

    def guardar_imagen(archivo):
        """Guarda la imagen solo si su contenido real es JPG, PNG o WebP (no se confía en la extensión)."""
        cab = archivo.stream.read(12)
        archivo.stream.seek(0)
        if cab[:3] == b"\xff\xd8\xff":
            ext = ".jpg"
        elif cab[:8] == b"\x89PNG\r\n\x1a\n":
            ext = ".png"
        elif cab[:4] == b"RIFF" and cab[8:12] == b"WEBP":
            ext = ".webp"
        else:
            return None
        nombre = secrets.token_hex(8) + ext  # nombre aleatorio: nunca el del cliente
        archivo.save(os.path.join(app.static_folder, "img", "productos", nombre))
        return nombre

    def borrar_imagen(nombre):
        if nombre:
            ruta = os.path.join(app.static_folder, "img", "productos", os.path.basename(nombre))
            if os.path.exists(ruta):
                os.remove(ruta)

    @app.route("/admin/productos/nuevo", methods=["GET", "POST"])
    @app.route("/admin/productos/<int:id>/editar", methods=["GET", "POST"])
    @admin_required
    def producto_form(id=None):
        p = db.get_or_404(Producto, id) if id else None
        form = ProductoForm(obj=p)
        if form.validate_on_submit():
            nueva = None
            archivo = form.imagen.data
            if archivo is not None and getattr(archivo, "filename", ""):
                nueva = guardar_imagen(archivo)
                if not nueva:
                    flash("El archivo no es una imagen JPG, PNG o WebP válida.", "error")
                    return render_template("producto_form.html", form=form, editando=bool(id), p=p)
            p = p or Producto()
            p.nombre, p.categoria, p.descripcion = form.nombre.data, form.categoria.data, form.descripcion.data
            p.precio, p.stock = form.precio.data, form.stock.data
            p.tagline, p.destacados, p.caja, p.specs = form.tagline.data, form.destacados.data, form.caja.data, form.specs.data
            if nueva:
                borrar_imagen(p.imagen)
                p.imagen = nueva
            db.session.add(p)
            db.session.commit()
            flash("Producto guardado.", "ok")
            return redirect(url_for("admin_productos"))
        return render_template("producto_form.html", form=form, editando=bool(id), p=p)

    @app.route("/admin/productos/<int:id>/eliminar", methods=["POST"])
    @admin_required
    def eliminar_producto(id):
        p = db.get_or_404(Producto, id)
        if p.pedidos:
            flash("No se puede eliminar: tiene pedidos asociados.", "error")
        else:
            borrar_imagen(p.imagen)
            db.session.delete(p)
            db.session.commit()
            flash("Producto eliminado.", "ok")
        return redirect(url_for("admin_productos"))

    @app.route("/admin/productos/<int:id>/rapido", methods=["POST"])
    @admin_required
    def producto_rapido(id):
        p = db.get_or_404(Producto, id)
        try:
            precio = float(request.form.get("precio", "").replace(",", "."))
            stock = int(request.form.get("stock", ""))
        except ValueError:
            precio, stock = 0, -1
        if not (1 <= precio <= 100_000_000 and 0 <= stock <= 100_000):
            flash("Precio o stock inválido.", "error")
        else:
            p.precio, p.stock = precio, stock
            db.session.commit()
            flash(f"{p.nombre}: precio y stock actualizados.", "ok")
        return redirect(url_for("admin_productos"))

    @app.route("/admin/cupones")
    @admin_required
    def admin_cupones():
        return render_template("admin_cupones.html", cupones=Cupon.query.order_by(Cupon.id.desc()).all())

    @app.route("/admin/cupones/nuevo", methods=["GET", "POST"])
    @app.route("/admin/cupones/<int:id>/editar", methods=["GET", "POST"])
    @admin_required
    def cupon_form(id=None):
        c = db.get_or_404(Cupon, id) if id else None
        form = CuponForm(obj=c)
        if form.validate_on_submit():
            repetido = Cupon.query.filter_by(codigo=form.codigo.data).first()
            if repetido and (not c or repetido.id != c.id):
                flash("Ya existe un cupón con ese código.", "error")
            else:
                c = c or Cupon()
                c.codigo, c.tipo, c.valor = form.codigo.data, form.tipo.data, form.valor.data
                c.minimo, c.vence, c.usos_max = form.minimo.data or 0, form.vence.data, form.usos_max.data
                c.publico, c.activo = form.publico.data, form.activo.data
                db.session.add(c)
                db.session.commit()
                flash("Cupón guardado.", "ok")
                return redirect(url_for("admin_cupones"))
        return render_template("cupon_form.html", form=form, editando=bool(id))

    @app.route("/admin/cupones/<int:id>/eliminar", methods=["POST"])
    @admin_required
    def eliminar_cupon(id):
        c = db.get_or_404(Cupon, id)
        if c.usos or Pedido.query.filter_by(cupon_id=c.id).first():
            flash("No se puede eliminar un cupón ya usado: desactivalo.", "error")
        else:
            db.session.delete(c)
            db.session.commit()
            flash("Cupón eliminado.", "ok")
        return redirect(url_for("admin_cupones"))

    @app.route("/admin/cobros")
    @admin_required
    def cobros():
        lista = Pedido.query.filter(Pedido.estado.in_(["pagado", "cobrado"])).order_by(Pedido.id.desc()).all()
        return render_template("cobros.html", pedidos=lista, liq=liquidacion)

    @app.route("/admin/pedido/<int:id>/cobrar", methods=["POST"])
    @admin_required
    def cobrar(id):
        pedido = db.get_or_404(Pedido, id)
        if pedido.estado == "pagado":
            pedido.estado, pedido.fecha_cobro = "cobrado", datetime.utcnow()
            db.session.commit()
            flash(f"Liquidación del pedido {pedido.codigo} registrada.", "ok")
        return redirect(url_for("cobros"))

    with app.app_context():
        db.create_all()
        for tabla, columnas in MIGRACIONES.items():  # agrega columnas nuevas a bases creadas con versiones anteriores
            existentes = [c["name"] for c in db.inspect(db.engine).get_columns(tabla)]
            for nombre, tipo in columnas:
                if nombre not in existentes:
                    db.session.execute(db.text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}"))
        db.session.execute(db.text("UPDATE pedido SET subtotal = total WHERE subtotal IS NULL"))
        for p in Pedido.query.filter(Pedido.numero.is_(None)).all():  # los pedidos anteriores reciben su número único
            p.numero = nuevo_numero_pedido()
            db.session.flush()
        db.session.execute(db.text("CREATE UNIQUE INDEX IF NOT EXISTS ux_pedido_numero ON pedido(numero)"))
        db.session.commit()
        if Producto.query.count() == 0:
            for n, c, d, pr, s in SEED:
                db.session.add(Producto(nombre=n, categoria=c, descripcion=d, precio=pr, stock=s))
            db.session.commit()
        for p in Producto.query.all():  # completa la información de los productos que todavía no la tienen
            ex = EXTRA.get(p.nombre)
            if ex and not p.tagline:
                p.tagline, p.destacados, p.caja, p.specs = ex["tagline"], ex["destacados"], ex["caja"], ex["specs"]
                if len(p.descripcion or "") < 80:
                    p.descripcion = ex["descripcion"]
        db.session.commit()
        if Cupon.query.count() == 0:  # cupones de ejemplo (el admin puede editarlos o borrarlos)
            db.session.add(Cupon(codigo="BIENVENIDA10", tipo="porcentaje", valor=10, minimo=50000))
            db.session.add(Cupon(codigo="ULTRA20K", tipo="monto", valor=20000, minimo=150000))
            db.session.commit()
    return app


if __name__ == "__main__":
    create_app().run(debug=False)
