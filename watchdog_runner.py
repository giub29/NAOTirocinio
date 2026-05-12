# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import logging
import signal

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - WATCHDOG - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SOUL_PATH = os.path.join(BASE_DIR, "soul.py")
if not os.path.exists(SOUL_PATH):
    SOUL_PATH = os.path.join(BASE_DIR, "NAOTirocinio", "soul.py")

SOUL_DIR = os.path.dirname(SOUL_PATH)

RUNTIME_DIR = os.path.join(SOUL_DIR, "runtime")
HEARTBEAT_FILE = os.path.join(RUNTIME_DIR, "heartbeat.txt")

TIMEOUT_HEARTBEAT = 60
CONTROLLO_INTERVALLO = 2
MAX_RIAVVII_CONSECUTIVI = 5
PAUSA_RIAVVIO = 3

processo = None
STOP = False


def assicura_runtime():
    if not os.path.exists(RUNTIME_DIR):
        os.makedirs(RUNTIME_DIR)


def reset_heartbeat():
    try:
        assicura_runtime()

        if os.path.exists(HEARTBEAT_FILE):
            os.remove(HEARTBEAT_FILE)

        logger.info("Heartbeat precedente eliminato")

    except Exception as e:
        logger.warning("Errore reset heartbeat: {}".format(e))

def heartbeat_scaduto():
    try:
        if not os.path.exists(HEARTBEAT_FILE):
            logger.debug("Heartbeat non ancora creato da soul.py")
            return False

        with open(HEARTBEAT_FILE, "r") as f:
            valore = f.read().strip()

        if not valore:
            logger.info("Heartbeat vuoto")
            return False

        ultimo = float(valore)
        differenza = time.time() - ultimo

        logger.debug("Heartbeat aggiornato {:.1f} secondi fa".format(differenza))

        return differenza > TIMEOUT_HEARTBEAT

    except Exception as e:
        logger.warning("Errore lettura heartbeat: {}".format(e))
        return True


def avvia_soul():
    logger.warning("Avvio soul.py da {}".format(SOUL_PATH))
    logger.warning("Python usato: {}".format(sys.executable))
    logger.warning("Working directory: {}".format(SOUL_DIR))

    return subprocess.Popen(
        [sys.executable, SOUL_PATH],
        cwd=SOUL_DIR
    )


def termina_processo(p):
    try:
        if p and p.poll() is None:
            logger.warning("Termino soul.py")
            p.terminate()

            time.sleep(3)

            if p.poll() is None:
                logger.warning("Kill forzato di soul.py")
                p.kill()

    except Exception as e:
        logger.error("Errore durante terminazione soul.py: {}".format(e))


def signal_handler(sig, frame):
    global STOP, processo

    logger.info("CTRL+C ricevuto: arresto completo")
    STOP = True

    if processo:
        termina_processo(processo)

    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def main():
    global processo, STOP

    assicura_runtime()
    riavvii = 0

    try:
        while not STOP:
            reset_heartbeat()
            processo = avvia_soul()

            while not STOP:
                time.sleep(CONTROLLO_INTERVALLO)

                if processo.poll() is not None:
                    logger.warning("soul.py terminato/crashato con codice: {}".format(processo.returncode))
                    break

                if heartbeat_scaduto():
                    logger.warning("Heartbeat scaduto: possibile freeze/dead loop")
                    termina_processo(processo)
                    break

            if STOP:
                break

            riavvii += 1
            logger.warning("Riavvio numero {}".format(riavvii))

            if riavvii >= MAX_RIAVVII_CONSECUTIVI:
                logger.error("Troppi riavvii consecutivi. Stop watchdog.")
                break

            time.sleep(PAUSA_RIAVVIO)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt ricevuto")
        STOP = True

        if processo:
            termina_processo(processo)

    finally:
        logger.info("Watchdog terminato")


if __name__ == "__main__":
    main()