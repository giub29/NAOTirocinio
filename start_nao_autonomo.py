# -*- coding: utf-8 -*-

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ.setdefault("NAO_AUTONOMOUS_LIFE", "1")
os.environ.setdefault("CHOREGRAPHE_BOOT", "1")

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