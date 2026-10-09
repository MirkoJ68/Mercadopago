"""Crea una cuenta de administrador (única forma de tener una).  Uso:  python crear_admin.py"""
import getpass
import re
import sys

from app import create_app
from models import Usuario, db
from seguridad import puntaje_clave


def main():
    app = create_app()
    with app.app_context():
        nombre = input("Nombre: ").strip()
        email = input("Email: ").strip().lower()
        if not nombre or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            sys.exit("Nombre o email inválido.")
        if Usuario.query.filter_by(email=email).first():
            sys.exit("Ya existe un usuario con ese email.")
        clave = getpass.getpass("Contraseña (mín. 12 caracteres con mayúsculas, minúsculas, números y símbolos): ")
        if getpass.getpass("Repetir contraseña: ") != clave:
            sys.exit("Las contraseñas no coinciden.")
        if len(clave) < 12 or puntaje_clave(clave) < 4:
            sys.exit("Contraseña demasiado débil para una cuenta de administración.")
        admin = Usuario(nombre=nombre, email=email, es_admin=True)
        admin.set_password(clave)
        db.session.add(admin)
        db.session.commit()
        print("Administrador creado. Ingresá desde http://127.0.0.1:5000/admin/login")


if __name__ == "__main__":
    main()
