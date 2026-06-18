#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import traceback
import os
import sys
import subprocess

try:
    from naoqi import ALProxy
except Exception:
    ALProxy = None

try:
    import urllib2
except Exception:
    urllib2 = None


PC_IP = os.environ.get("PC_IP", "172.16.165.75")
PC_PORT = int(os.environ.get("PC_PORT", "8765"))
MAX_TENTATIVI_PC = int(os.environ.get("BOOTSTRAP_MAX_TENTATIVI_PC", "60"))
PAUSA_TENTATIVI_PC = int(os.environ.get("BOOTSTRAP_PAUSA_TENTATIVI_PC", "5"))
BOOTSTRAP_MODE = os.environ.get("BOOTSTRAP_MODE", "onboard").strip().lower()
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WATCHDOG_PATH = os.path.join(PROJECT_ROOT, "scripts", "autonomous_watchdog.py")
RUNTIME_DIR = os.path.join(PROJECT_ROOT, "runtime")
WATCHDOG_ONBOARD_LOG = os.path.join(RUNTIME_DIR, "watchdog_onboard.log")


def scrivi_log(messaggio):
    try:
        f = open("/home/nao/autonomous_bootstrap.log", "a")
        f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), messaggio))
        f.close()
    except Exception:
        pass


def parla(tts, frase):
    try:
        if tts is not None:
            tts.say(frase)
    except Exception as e:
        scrivi_log("Errore voce: %s" % str(e))


def carica_openai_api_key_locale(env):
    if env.get("OPENAI_API_KEY", "").strip():
        return

    percorsi = [
        os.path.join(PROJECT_ROOT, "config", "openai_api_key.txt"),
        os.path.join(PROJECT_ROOT, "openai_api_key.txt")
    ]

    for percorso in percorsi:
        try:
            if not os.path.exists(percorso):
                continue

            f = open(percorso, "r")
            chiave = f.read().strip()
            f.close()

            if chiave:
                env["OPENAI_API_KEY"] = chiave
                scrivi_log("OPENAI_API_KEY caricata da file locale")
                return

        except Exception as e:
            scrivi_log("Errore lettura OPENAI_API_KEY locale: %s" % str(e))


def prepara_env_onboard():
    env = os.environ.copy()
    env.setdefault("NAO_IP", "127.0.0.1")
    env.setdefault("NAO_AUTONOMOUS_LIFE", "1")
    env.setdefault("CHOREGRAPHE_BOOT", "1")
    env.setdefault("SKIP_AUTONOMOUS_LIFE_CONFIG", "1")
    carica_openai_api_key_locale(env)
    return env


def avvia_watchdog_onboard():
    try:
        if not os.path.exists(WATCHDOG_PATH):
            return False, "watchdog non trovato: %s" % WATCHDOG_PATH

        if not os.path.exists(RUNTIME_DIR):
            os.makedirs(RUNTIME_DIR)

        env = prepara_env_onboard()
        log_file = open(WATCHDOG_ONBOARD_LOG, "a")

        python_cmd = os.environ.get("NAO_PYTHON") or sys.executable or "python"

        processo = subprocess.Popen(
            [python_cmd, WATCHDOG_PATH],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=log_file,
            stderr=log_file
        )

        return True, "watchdog onboard pid=%s" % processo.pid

    except Exception as e:
        scrivi_log(traceback.format_exc())
        return False, str(e)


def chiama_pc(percorso):
    if urllib2 is None:
        return False, "urllib2 non disponibile"

    url = "http://%s:%s%s" % (PC_IP, PC_PORT, percorso)

    try:
        risposta = urllib2.urlopen(url, timeout=10)
        testo = risposta.read()
        return True, testo
    except Exception as e:
        return False, str(e)


def main():
    scrivi_log("BOOTSTRAP AVVIATO")
    scrivi_log("Modalita bootstrap: %s" % BOOTSTRAP_MODE)
    scrivi_log("Project root: %s" % PROJECT_ROOT)
    scrivi_log("Watchdog onboard: %s" % WATCHDOG_PATH)
    scrivi_log("PC fallback target: %s:%s" % (PC_IP, PC_PORT))

    tts = None
    memory = None

    try:
        tts = ALProxy("ALTextToSpeech", "127.0.0.1", 9559)
        memory = ALProxy("ALMemory", "127.0.0.1", 9559)

        memory.insertData("AutonomousSystem/Status", "BOOTSTRAP_STARTED")
        memory.insertData("AutonomousSystem/Command", "")
        memory.insertData("AutonomousSystem/BootstrapCommand", "START")
        memory.insertData("AutonomousSystem/BootstrapTime", time.time())

        parla(tts, "Sistema autonomo in avvio.")
        scrivi_log("ALMemory aggiornata: BootstrapCommand=START")

    except Exception as e:
        scrivi_log("ERRORE inizializzazione NAOqi: %s" % str(e))
        scrivi_log(traceback.format_exc())

    if BOOTSTRAP_MODE in ["onboard", "local", "standalone", "auto", ""]:
        ok_onboard, risposta_onboard = avvia_watchdog_onboard()
        scrivi_log(
            "START WATCHDOG ONBOARD: ok=%s risposta=%s" % (
                ok_onboard,
                risposta_onboard
            )
        )

        if ok_onboard:
            parla(tts, "Sistema autonomo avviato.")
            try:
                if memory is not None:
                    memory.insertData(
                        "AutonomousSystem/Status",
                        "WATCHDOG_ONBOARD_STARTED"
                    )
            except Exception:
                pass
            return

        if BOOTSTRAP_MODE not in ["auto"]:
            parla(tts, "Errore avvio autonomo locale.")
            try:
                if memory is not None:
                    memory.insertData(
                        "AutonomousSystem/Status",
                        "WATCHDOG_ONBOARD_START_FAILED"
                    )
            except Exception:
                pass
            return

        scrivi_log("Fallback PC abilitato dopo errore onboard")

    if BOOTSTRAP_MODE not in ["pc", "remote", "auto"]:
        scrivi_log("Fallback PC disabilitato")
        return

    ok = False
    risposta = ""

    for tentativo in range(1, MAX_TENTATIVI_PC + 1):
        ok, risposta = chiama_pc("/ping")
        scrivi_log(
            "PING PC tentativo %s/%s: ok=%s risposta=%s" % (
                tentativo,
                MAX_TENTATIVI_PC,
                ok,
                risposta
            )
        )

        if ok:
            break

        try:
            if memory is not None:
                memory.insertData("AutonomousSystem/Status", "WAITING_PC")
        except Exception:
            pass

        time.sleep(PAUSA_TENTATIVI_PC)

    if not ok:
        parla(tts, "Supervisore non disponibile.")
        try:
            if memory is not None:
                memory.insertData("AutonomousSystem/Status", "PC_NOT_AVAILABLE")
        except Exception:
            pass
        return

    parla(tts, "Supervisore trovato.")

    ok, risposta = chiama_pc("/start")
    scrivi_log("START PC: ok=%s risposta=%s" % (ok, risposta))

    if ok:
        parla(tts, "Watchdog avviato.")
        try:
            if memory is not None:
                memory.insertData("AutonomousSystem/Status", "WATCHDOG_STARTED")
        except Exception:
            pass
    else:
        parla(tts, "Errore avvio watchdog.")
        try:
            if memory is not None:
                memory.insertData("AutonomousSystem/Status", "WATCHDOG_START_FAILED")
        except Exception:
            pass


main()
