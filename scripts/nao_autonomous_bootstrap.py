#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import subprocess
import time
import traceback

try:
    from naoqi import ALProxy
except Exception:
    ALProxy = None


BASE_DIR = "/data/home/nao/NAOTirocinio"
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
BOOT_LOG = os.path.join(RUNTIME_DIR, "boot_autonomo.log")
WATCHDOG_REL_PATH = os.path.join("scripts", "autonomous_watchdog.py")
WATCHDOG_PATH = os.path.join(BASE_DIR, WATCHDOG_REL_PATH)
WATCHDOG_LOCK_FILE = os.path.join(RUNTIME_DIR, "watchdog.lock")
PYTHON_CMD = "/usr/bin/python"

ALMEMORY_STATUS_KEY = "AutonomousSystem/Status"
ALMEMORY_BOOT_TIME_KEY = "AutonomousSystem/BootstrapTime"
ALMEMORY_WATCHDOG_PID_KEY = "AutonomousSystem/WatchdogPid"


def assicura_runtime():
    try:
        if not os.path.exists(RUNTIME_DIR):
            os.makedirs(RUNTIME_DIR)
    except Exception:
        pass


def scrivi_log(messaggio):
    try:
        assicura_runtime()
        f = open(BOOT_LOG, "a")
        try:
            f.write("[%s] %s\n" % (
                time.strftime("%Y-%m-%d %H:%M:%S"),
                messaggio
            ))
        finally:
            f.close()
    except Exception:
        pass


def aggiorna_memoria(memory, stato, extra=None):
    try:
        if memory is None:
            return

        memory.insertData(ALMEMORY_STATUS_KEY, stato)
        memory.insertData(ALMEMORY_BOOT_TIME_KEY, time.time())

        if extra:
            for chiave, valore in extra.items():
                memory.insertData(chiave, valore)
    except Exception as e:
        scrivi_log("Errore aggiornamento ALMemory: %s" % str(e))


def connetti_almemory():
    if ALProxy is None:
        scrivi_log("NAOqi non disponibile: continuo senza ALMemory")
        return None

    try:
        return ALProxy("ALMemory", "127.0.0.1", 9559)
    except Exception as e:
        scrivi_log("Errore connessione ALMemory: %s" % str(e))
        return None


def pid_esiste(pid):
    try:
        pid = int(str(pid).strip())
    except Exception:
        return False

    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def pid_da_lock_watchdog():
    try:
        if not os.path.exists(WATCHDOG_LOCK_FILE):
            return None

        f = open(WATCHDOG_LOCK_FILE, "r")
        try:
            valore = f.read().strip()
        finally:
            f.close()

        if valore:
            return valore
    except Exception as e:
        scrivi_log("Errore lettura watchdog.lock: %s" % str(e))

    return None


def watchdog_attivo_da_lock():
    pid_lock = pid_da_lock_watchdog()
    if not pid_lock:
        return False, None

    if pid_esiste(pid_lock):
        return True, pid_lock

    scrivi_log(
        "watchdog.lock presente ma PID non attivo: %s. "
        "Lascio la gestione al watchdog." % pid_lock
    )
    return False, None


def watchdog_attivo_da_ps():
    try:
        processo = subprocess.Popen(
            ["ps", "aux"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output, _ = processo.communicate()

        if not isinstance(output, str):
            try:
                output = output.decode("utf-8", "ignore")
            except Exception:
                output = ""

        for riga in output.splitlines():
            if "autonomous_watchdog.py" not in riga:
                continue
            if "grep" in riga:
                continue
            if "nao_autonomous_bootstrap.py" in riga:
                continue
            return True
    except Exception as e:
        scrivi_log("Errore controllo ps watchdog: %s" % str(e))

    return False


def watchdog_gia_attivo():
    attivo, pid_lock = watchdog_attivo_da_lock()
    if attivo:
        return True, pid_lock

    if watchdog_attivo_da_ps():
        return True, None

    return False, None


def carica_openai_api_key_locale(env):
    if env.get("OPENAI_API_KEY", "").strip():
        return

    percorsi = [
        os.path.join(BASE_DIR, "config", "openai_api_key.txt"),
        os.path.join(BASE_DIR, "openai_api_key.txt")
    ]

    for percorso in percorsi:
        try:
            if not os.path.exists(percorso):
                continue

            f = open(percorso, "r")
            try:
                chiave = f.read().strip()
            finally:
                f.close()

            if chiave:
                env["OPENAI_API_KEY"] = chiave
                scrivi_log("OPENAI_API_KEY caricata da file locale")
                return
        except Exception as e:
            scrivi_log("Errore lettura OPENAI_API_KEY locale: %s" % str(e))


def prepara_env():
    env = os.environ.copy()
    env.setdefault("NAO_IP", "127.0.0.1")
    env.setdefault("NAO_AUTONOMOUS_LIFE", "1")
    env.setdefault("CHOREGRAPHE_BOOT", "1")
    env.setdefault("SKIP_AUTONOMOUS_LIFE_CONFIG", "1")
    carica_openai_api_key_locale(env)
    return env


def avvia_watchdog():
    if not os.path.exists(BASE_DIR):
        return False, "BASE_DIR non trovato: %s" % BASE_DIR, None

    if not os.path.exists(WATCHDOG_PATH):
        return False, "watchdog non trovato: %s" % WATCHDOG_PATH, None

    os.chdir(BASE_DIR)
    assicura_runtime()

    log_file = open(BOOT_LOG, "a")
    env = prepara_env()

    processo = subprocess.Popen(
        [PYTHON_CMD, WATCHDOG_REL_PATH],
        cwd=BASE_DIR,
        env=env,
        stdout=log_file,
        stderr=log_file
    )

    return True, "watchdog avviato pid=%s" % processo.pid, processo.pid


def main():
    assicura_runtime()
    scrivi_log("BOOTSTRAP_STARTED")
    scrivi_log("BASE_DIR=%s" % BASE_DIR)
    scrivi_log("WATCHDOG_PATH=%s" % WATCHDOG_PATH)

    memory = connetti_almemory()
    aggiorna_memoria(memory, "BOOTSTRAP_STARTED")

    try:
        attivo, pid_attivo = watchdog_gia_attivo()
        if attivo:
            messaggio = "watchdog gia' attivo"
            if pid_attivo:
                messaggio += " pid=%s" % pid_attivo

            scrivi_log(messaggio)
            aggiorna_memoria(
                memory,
                "WATCHDOG_STARTED",
                {ALMEMORY_WATCHDOG_PID_KEY: str(pid_attivo or "")}
            )
            return

        aggiorna_memoria(memory, "WATCHDOG_START_REQUESTED")
        scrivi_log("WATCHDOG_START_REQUESTED")

        ok, messaggio, pid = avvia_watchdog()
        scrivi_log(messaggio)

        if ok:
            aggiorna_memoria(
                memory,
                "WATCHDOG_STARTED",
                {ALMEMORY_WATCHDOG_PID_KEY: str(pid or "")}
            )
            scrivi_log("WATCHDOG_STARTED")
            return

        aggiorna_memoria(memory, "WATCHDOG_START_FAILED")
        scrivi_log("WATCHDOG_START_FAILED: %s" % messaggio)

    except Exception as e:
        aggiorna_memoria(memory, "WATCHDOG_START_FAILED")
        scrivi_log("WATCHDOG_START_FAILED: %s" % str(e))
        scrivi_log(traceback.format_exc())


if __name__ == "__main__":
    main()
