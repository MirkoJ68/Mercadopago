# ultra.snd — Tienda de auriculares con simulador de pago/cobro

Aplicación web hecha con **Python + Flask** (TP Instituto Técnico Renault).

## Instalación y ejecución
```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
python crear_admin.py     # crea la cuenta de administrador (única forma de tener una)
python app.py
```
Abrir http://127.0.0.1:5000. La base SQLite y 4 productos de ejemplo se crean solos.

## Guion para la demo en vivo
1. Creá el admin con `python crear_admin.py` e ingresá por `/admin/login` (enlace «Administración» al pie). Los clientes que se registran nunca son admin.
2. Admin → **Productos**: agregar, editar, eliminar y **subir la imagen** (JPG/PNG/WebP, hasta 16 MB).
3. Con un segundo usuario (cliente): elegí un producto → **Comprar ahora** → pedido `pendiente`.
4. **Pagar** con una tarjeta de prueba. El sistema valida (Luhn, vencimiento, CVV), detecta la marca y pide el código **3D Secure** (se muestra como "SMS simulado").
5. Pago aprobado → se emite la **factura B** (imprimible / guardar como PDF) y el pedido queda `pagado`.
6. El admin entra a **Cobros** y ve bruto, comisión, IVA y neto; presiona **Registrar cobro** → `cobrado`.

## Entrega, envío y cupones
- Al comprar, el cliente elige **retiro en el almacén** (Av. Renault Argentina 2520, Córdoba, sin costo) o **envío a domicilio**. Solo con envío se pide la dirección, que también se usa como domicilio de facturación (aparece en la factura).
- El **costo de envío** se estima por código postal (zonas con km aproximados desde el almacén, en `tienda.py`; se ajustan ahí) y se suma al total que se paga con la tarjeta. Se puede consultar antes de comprar en la ficha del producto.
- **Cupones**: % o monto fijo, con compra mínima en productos, vencimiento y tope de usos. Tienen su propia página («Cupones»; ahí cada cliente ve también sus cupones de regalo y los que ya canjeó) y se eligen de la lista o se escriben al elegir la entrega. Las compras de $200.000 o más (en productos, ya con descuento) regalan un cupón personal de 5% (mínimo $50.000, vence en 30 días); se ajusta en `tienda.py`. Cada cliente puede usar un cupón una sola vez.
- El admin gestiona cupones en **Admin cupones** y edita precio y stock directo en la tabla de **Productos**.

## Tarjetas de prueba
| Resultado | Número |
|---|---|
| Aprobada (Visa) | 4111 1111 1111 1111 |
| Aprobada (Mastercard) | 5555 5555 5555 4444 |
| Aprobada (Amex, CVV de 4 dígitos) | 3782 822463 10005 |
| Rechazo del emisor / Fondos insuficientes / Vencida / CVV incorrecto | 4000 0000 0000 0002 / ...9995 / ...0069 / ...0127 |

## Seguridad aplicada
- Admin separado: solo se crea por consola, ingresa por `/admin/login` y `/admin/*` responde 404 a quien no es admin.
- Captcha propio (imagen SVG, un solo uso, vence a los 5 min) en login, registro y acceso admin; medidor de fuerza de contraseña y rechazo de claves débiles/comunes.
- Imágenes subidas: se valida el contenido real del archivo, se renombran al azar y hay tope de 16 MB.
- Panel «Mi cuenta» (datos personales y cambio de contraseña): pide la actual, aplica la misma regla de fuerza (el admin, la estricta) y cierra las demás sesiones abiertas.
- Nueva sesión al ingresar (anti fijación de sesión) y límite de registros por IP.
- Nunca se guarda el número completo, el vencimiento ni el CVV (solo marca y últimos 4 dígitos).
- Validación del número (Luhn), de la marca, del vencimiento y del largo del CVV.
- Verificación 3D Secure: código de 6 dígitos hasheado, vence a los 5 min, máximo 3 intentos.
- Contraseñas hasheadas, mínimo 8 con letras y números; bloqueo tras 5 logins fallidos; límite de intentos de pago.
- Protección CSRF, cookies HttpOnly + SameSite, sesión de 30 min, protección contra open redirect.
- Cabeceras: Content-Security-Policy, X-Frame-Options, nosniff, Referrer-Policy, Cache-Control: no-store.
- Control de acceso: cada cliente solo ve sus pedidos, pagos y facturas; admin protegido.
- `SECRET_KEY` por variable de entorno o generada en `instance/secret.key`. Con HTTPS, usar `HTTPS=1`.

## Contraseña olvidada
- **Clientes:** en el login, «¿Olvidaste tu contraseña?». Se genera un enlace de un solo uso que vence en 30 min. Sin servidor de correo configurado, el enlace se **imprime en la consola** donde corre `python app.py`. Para enviarlo por email real, definir `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` y `BASE_URL`.
- **Cualquier cuenta (incluida la de admin):** `python resetear_clave.py` desde la carpeta del proyecto.

## Cómo se paga
Después de elegir la entrega, el cliente elige **tarjeta** (simulador con 3D Secure) o **Mercado Pago** (Checkout Pro). El pago de Mercado Pago siempre se confirma consultando la API (retorno y webhook), nunca por lo que llega en la URL. Las credenciales van en `.env` (ver `.env.example`).

## Tienda
- **Portada**: explicación de cada auricular y acceso directo a su ficha. **Catálogo**: página aparte. **Ficha**: descripción, qué puede hacer, contenido de la caja y especificaciones (el admin las edita en Productos).
- **Stock único**: el descuento al comprar es atómico y los pedidos sin pagar se cancelan a la hora y devuelven el stock (salvo los que tienen un pago de Mercado Pago en revisión).
- **Email**: probar la configuración con `python probar_correo.py tu@correo.com`.

## Estructura
`app.py` (rutas) · `pagos.py` (tarjetas, recargos, comisiones, facturas) · `models.py` · `forms.py` · `templates/` · `static/`

## Tecnologías
Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Jinja2, SQLite.
> Simulador educativo: no procesa pagos reales ni emite facturas con validez fiscal.

## Imágenes de los productos
Subí fotos desde Admin → Productos (ideal 3840 px de ancho). Fuentes gratuitas: Unsplash, Pexels y Pixabay (revisá la licencia de cada foto). Sin imagen, se muestra el dibujo SVG.
