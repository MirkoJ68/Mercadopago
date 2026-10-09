"""Captcha propio (imagen SVG, sin dependencias) y evaluación de contraseñas."""
import random
import re
import secrets

LETRAS = "ACDEFGHKLMNPRTWXY3469"  # solo caracteres que no se confunden entre sí (sin O/0, I/1, S/5, Z/2, B/8, U/V...)
COMUNES = {"12345678", "123456789", "1234567890", "password", "password1", "contraseña", "qwerty123",
           "abc12345", "11111111", "admin123", "iloveyou", "12345678a"}


def generar_captcha():
    """Devuelve (texto, svg): 5 caracteres rotados, con ruido y líneas que cruzan el texto."""
    r = random.SystemRandom()
    texto = "".join(secrets.choice(LETRAS) for _ in range(5))
    colores = ["#7fd0ff", "#f6e3a8", "#ff8a65", "#c58bff", "#ffffff"]
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="180" height="60" viewBox="0 0 180 60"><rect width="180" height="60" fill="#0a0a0f"/>']
    for _ in range(4):
        s.append(f'<line x1="{r.randint(0,180)}" y1="{r.randint(0,60)}" x2="{r.randint(0,180)}" y2="{r.randint(0,60)}" stroke="{r.choice(colores)}" stroke-opacity=".35" stroke-width="1.5"/>')
    for i, ch in enumerate(texto):
        x, y = 16 + i * 32 + r.randint(-2, 2), 41 + r.randint(-4, 4)
        s.append(f'<text x="{x}" y="{y}" font-size="{r.randint(30, 36)}" font-family="monospace" font-weight="700" '
                 f'fill="{r.choice(colores)}" transform="rotate({r.randint(-14, 14)} {x} {y})">{ch}</text>')
    for _ in range(2):
        s.append(f'<path d="M0 {r.randint(10,50)} C{r.randint(40,80)} {r.randint(0,60)} {r.randint(90,140)} {r.randint(0,60)} 180 {r.randint(10,50)}" '
                 f'fill="none" stroke="{r.choice(colores)}" stroke-opacity=".6" stroke-width="2"/>')
    s.append("</svg>")
    return texto, "".join(s)


def puntaje_clave(p):
    """0 (muy débil) a 4 (muy fuerte). Debe coincidir con la función puntaje() de static/js/app.js."""
    if len(p) < 8 or p.lower() in COMUNES or len(set(p)) <= 2:
        return 0
    clases = sum(bool(re.search(x, p)) for x in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    return min(4, 1 + (len(p) >= 12) + (clases >= 3) + (clases == 4 or len(p) >= 16))
