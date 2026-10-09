"""Prueba la configuración de email del archivo .env.  Uso:  python probar_correo.py tu@correo.com"""
import os
import sys

from app import enviar_correo  # al importar app se carga el .env


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python probar_correo.py tu@correo.com")
    if not os.environ.get("SMTP_HOST"):
        sys.exit("Falta SMTP_HOST: copiá .env.example como .env y completalo.")
    try:
        enviar_correo(sys.argv[1], "Prueba de ultra.snd", "Si estás leyendo esto, el envío de emails funciona.")
        print("Email enviado. Revisá la bandeja de entrada (y spam).")
    except Exception as e:
        sys.exit(f"No se pudo enviar: {e}")


if __name__ == "__main__":
    main()
