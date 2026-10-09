"""Formularios Flask-WTF."""
import re
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (BooleanField, DateField, FloatField, IntegerField, PasswordField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                NumberRange, Optional, Regexp, ValidationError)

from seguridad import puntaje_clave
from tienda import PROVINCIAS, normalizar_cp
from pagos import MARCAS, detectar_marca, largo_cvv, luhn, solo_digitos, vencida


CAPTCHA = lambda: StringField("Código de la imagen", validators=[DataRequired(), Length(max=8)], render_kw={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"})


class RegistroForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=8, max=128)], render_kw={"autocomplete": "new-password", "data-medidor": "1"})
    confirmar = PasswordField("Repetir contraseña", validators=[EqualTo("password", "Las contraseñas no coinciden")])
    captcha = CAPTCHA()
    submit = SubmitField("Crear cuenta")

    def validate_password(self, field):
        if puntaje_clave(field.data) < 2:
            raise ValidationError("Contraseña demasiado débil: usá 8+ caracteres con mayúsculas, minúsculas, números o símbolos, y evitá claves comunes")


class DatosForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    telefono = StringField("Teléfono (se completa solo cuando pedís un envío)", validators=[Optional(), Regexp(r"^[0-9+()\s-]{8,20}$", message="Teléfono inválido")],
                           render_kw={"autocomplete": "tel"})
    password_actual = PasswordField("Contraseña actual (solo si cambiás el email)", validators=[Optional()], render_kw={"autocomplete": "current-password"})


class OlvideForm(FlaskForm):
    email = StringField("Email de tu cuenta", validators=[DataRequired(), Email()])
    captcha = CAPTCHA()
    submit = SubmitField("Enviar enlace")


class RestablecerForm(FlaskForm):
    password = PasswordField("Nueva contraseña", validators=[DataRequired(), Length(min=8, max=128)], render_kw={"autocomplete": "new-password", "data-medidor": "1"})
    confirmar = PasswordField("Repetir nueva contraseña", validators=[EqualTo("password", "Las contraseñas no coinciden")])
    submit = SubmitField("Guardar contraseña")

    def validate_password(self, field):
        if puntaje_clave(field.data) < 2:
            raise ValidationError("Contraseña demasiado débil: usá 8+ caracteres con mayúsculas, minúsculas, números o símbolos, y evitá claves comunes")


class CambiarClaveForm(FlaskForm):
    actual = PasswordField("Contraseña actual", validators=[DataRequired()], render_kw={"autocomplete": "current-password"})
    password = PasswordField("Nueva contraseña", validators=[DataRequired(), Length(min=8, max=128)], render_kw={"autocomplete": "new-password", "data-medidor": "1"})
    confirmar = PasswordField("Repetir nueva contraseña", validators=[EqualTo("password", "Las contraseñas no coinciden")])
    submit = SubmitField("Cambiar contraseña")

    def validate_password(self, field):
        if puntaje_clave(field.data) < 2:
            raise ValidationError("Contraseña demasiado débil: usá 8+ caracteres con mayúsculas, minúsculas, números o símbolos, y evitá claves comunes")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    captcha = CAPTCHA()
    submit = SubmitField("Iniciar sesión")


class ProductoForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    categoria = StringField("Categoría (ej: Over-ear, In-ear, Gaming, Estudio)", validators=[DataRequired(), Length(max=40)])
    descripcion = TextAreaField("Descripción")
    tagline = StringField("Frase corta para la portada", validators=[Optional(), Length(max=160)])
    destacados = TextAreaField("Qué puede hacer (una por línea, con el formato Título|Texto)", validators=[Optional(), Length(max=1500)])
    caja = TextAreaField("Contenido de la caja (uno por línea)", validators=[Optional(), Length(max=800)])
    specs = TextAreaField("Especificaciones (una por línea, con el formato Nombre: valor)", validators=[Optional(), Length(max=1000)])
    precio = FloatField("Precio (IVA incluido)", validators=[DataRequired(), NumberRange(min=1)])
    stock = IntegerField("Stock", validators=[NumberRange(min=0)])
    imagen = FileField("Imagen (JPG, PNG o WebP, hasta 16 MB; ideal 3840 px de ancho)", validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Solo JPG, PNG o WebP")])
    submit = SubmitField("Guardar producto")


class CompraForm(FlaskForm):
    cantidad = IntegerField("Cantidad", default=1, validators=[DataRequired(), NumberRange(min=1, max=10)])
    submit = SubmitField("Comprar ahora")


class PagoForm(FlaskForm):
    """Datos de tarjeta. Se validan (Luhn, marca, vencimiento, CVV) pero no se almacenan."""
    titular = StringField("Titular (como figura en la tarjeta)", validators=[DataRequired(), Length(max=60)],
                          render_kw={"autocomplete": "cc-name"})
    numero = StringField("Número de tarjeta", validators=[DataRequired(), Length(max=23)],
                         render_kw={"autocomplete": "cc-number", "inputmode": "numeric", "id": "numero"})
    vencimiento = StringField("Vencimiento (MM/AA)", validators=[DataRequired(), Regexp(r"^(0[1-9]|1[0-2])/\d{2}$", message="Formato MM/AA")],
                              render_kw={"autocomplete": "cc-exp", "placeholder": "MM/AA"})
    cvv = PasswordField("Código de seguridad (CVV)", validators=[DataRequired(), Regexp(r"^\d{3,4}$", message="Solo números")],
                        render_kw={"autocomplete": "off", "inputmode": "numeric"})
    tipo = SelectField("Tipo de tarjeta", choices=[("credito", "Crédito"), ("debito", "Débito")])
    cuotas = SelectField("Cuotas (solo crédito)", choices=[("1", "1 pago (sin recargo)"), ("3", "3 cuotas (+8%)"),
                                                           ("6", "6 cuotas (+15%)"), ("12", "12 cuotas (+28%)")])
    submit = SubmitField("Continuar")

    def validate_numero(self, field):
        n = solo_digitos(field.data)
        marca = detectar_marca(n)
        if not marca or len(n) != MARCAS[marca][1] or not luhn(n):
            raise ValidationError("Número de tarjeta inválido")

    def validate_vencimiento(self, field):
        if re.match(r"^(0[1-9]|1[0-2])/\d{2}$", field.data or "") and vencida(field.data):
            raise ValidationError("La tarjeta está vencida")

    def validate_cvv(self, field):
        esperado = largo_cvv(detectar_marca(solo_digitos(self.numero.data)))
        if len(field.data or "") != esperado:
            raise ValidationError(f"El CVV debe tener {esperado} dígitos")


class EntregaForm(FlaskForm):
    """Entrega del pedido. La dirección solo se pide (y se usa también para facturar) si elige envío a domicilio."""
    metodo_entrega = SelectField("¿Cómo querés recibirlo?", choices=[
        ("retiro", "Retiro en el almacén (sin costo)"), ("domicilio", "Envío a domicilio (se paga junto con el producto)")])
    dom_calle = StringField("Calle", validators=[Optional(), Length(max=80)], render_kw={"autocomplete": "address-line1"})
    dom_numero = StringField("Número", validators=[Optional(), Length(max=10)])
    dom_piso = StringField("Piso / Depto (opcional)", validators=[Optional(), Length(max=20)])
    dom_ciudad = StringField("Ciudad / Localidad", validators=[Optional(), Length(max=80)], render_kw={"autocomplete": "address-level2"})
    dom_provincia = SelectField("Provincia", choices=[("", "Elegí una provincia")] + [(p, p) for p in PROVINCIAS])
    dom_cp = StringField("Código postal", validators=[Optional(), Length(max=10)],
                         render_kw={"autocomplete": "postal-code", "data-envio-cp": "1", "inputmode": "text"})
    telefono = StringField("Teléfono de contacto", validators=[Optional(), Regexp(r"^[0-9+()\s-]{8,20}$", message="Teléfono inválido")],
                           render_kw={"autocomplete": "tel"})
    cupon_codigo = StringField("Cupón de descuento (elegí uno de tus cupones o escribí un código)", validators=[Optional(), Length(max=20)],
                               render_kw={"autocomplete": "off", "list": "lista-cupones"})

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if self.metodo_entrega.data == "domicilio":
            for campo in (self.dom_calle, self.dom_numero, self.dom_ciudad, self.dom_provincia, self.dom_cp, self.telefono):
                if not (campo.data or "").strip():
                    campo.errors = list(campo.errors) + ["Obligatorio para el envío a domicilio"]
                    ok = False
            if (self.dom_cp.data or "").strip() and normalizar_cp(self.dom_cp.data) is None:
                self.dom_cp.errors = list(self.dom_cp.errors) + ["Código postal inválido (ej: 5000 o X5000ABC)"]
                ok = False
        return ok


class CuponForm(FlaskForm):
    codigo = StringField("Código", validators=[DataRequired(), Regexp(r"^[A-Za-z0-9_-]{3,20}$", message="3 a 20 letras, números, - o _")],
                         filters=[lambda v: v.strip().upper() if v else v])
    tipo = SelectField("Tipo de descuento", choices=[("porcentaje", "Porcentaje (%)"), ("monto", "Monto fijo ($)")])
    valor = FloatField("Valor del descuento", validators=[DataRequired(), NumberRange(min=1)])
    minimo = FloatField("Compra mínima en productos ($; 0 = sin mínimo)", default=0, validators=[Optional(), NumberRange(min=0)])
    vence = DateField("Vence el (opcional)", validators=[Optional()])
    usos_max = IntegerField("Usos máximos en total (opcional)", validators=[Optional(), NumberRange(min=1)])
    publico = BooleanField("Mostrar en el apartado de cupones de la página principal", default=True)
    activo = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar cupón")

    def validate_valor(self, field):
        if self.tipo.data == "porcentaje" and field.data > 100:
            raise ValidationError("El porcentaje no puede superar 100")


class OtpForm(FlaskForm):
    codigo = StringField("Código de verificación", validators=[DataRequired(), Regexp(r"^\d{6}$", message="Son 6 dígitos")],
                         render_kw={"autocomplete": "one-time-code", "inputmode": "numeric"})
    submit = SubmitField("Confirmar pago")
