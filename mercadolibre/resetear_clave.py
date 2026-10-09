"""Restablece la contraseña de CUALQUIER cuenta (incluida la de administración) desde la consola.  Uso:  python resetear_clave.py"""
import getpass
import sys

from app import create_app
from models import Usuario, db
from seguridad import puntaje_clave


def main():
    app = create_app()
    with app.app_context():
        u = Usuario.query.filter_by(email=input("Email de la cuenta: ").strip().lower()).first()
        if not u:
            sys.exit("No existe una cuenta con ese email.")
        clave = getpass.getpass("Nueva contraseña: ")
        if getpass.getpass("Repetir contraseña: ") != clave:
            sys.exit("Las contraseñas no coinciden.")
        if u.es_admin and (len(clave) < 12 or puntaje_clave(clave) < 4):
            sys.exit("Para administración: 12+ caracteres con mayúsculas, minúsculas, números y símbolos.")
        if puntaje_clave(clave) < 2:
            sys.exit("Contraseña demasiado débil.")
        u.set_password(clave)  # además cierra las sesiones abiertas de esa cuenta
        db.session.commit()
        print("Contraseña actualizada.")


if __name__ == "__main__":
    main()
