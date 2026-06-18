# -*- coding: utf-8 -*-

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def carica_openai_api_key_locale():
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return

    percorsi = [
        os.path.join(BASE_DIR, "config", "openai_api_key.txt"),
        os.path.join(BASE_DIR, "openai_api_key.txt")
    ]

    for percorso in percorsi:
        try:
            if not os.path.exists(percorso):
                continue

            with open(percorso, "r") as f:
                chiave = f.read().strip()

            if chiave:
                os.environ["OPENAI_API_KEY"] = chiave
                print("OPENAI_API_KEY caricata da file locale.")
                return

        except Exception as e:
            print("Errore lettura OPENAI_API_KEY locale:", e)


os.environ.setdefault("NAO_AUTONOMOUS_LIFE", "1")
os.environ.setdefault("CHOREGRAPHE_BOOT", "1")
os.environ.setdefault("SKIP_AUTONOMOUS_LIFE_CONFIG", "1")
carica_openai_api_key_locale()

# Se gira direttamente su NAO, il robot parla con se stesso
if os.name != "nt":
    os.environ.setdefault("NAO_IP", "127.0.0.1")


WATCHDOG = os.path.join(BASE_DIR, "scripts", "autonomous_watchdog.py")

if not os.path.exists(WATCHDOG):
    print("ERRORE: watchdog non trovato:", WATCHDOG)
    sys.exit(1)

print("Avvio sistema autonomo NAO")
print("Base dir:", BASE_DIR)
print("NAO_IP:", os.environ.get("NAO_IP", "default"))
print("Watchdog:", WATCHDOG)

subprocess.call([sys.executable, WATCHDOG], cwd=BASE_DIR)
