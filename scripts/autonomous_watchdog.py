# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess
import logging
import signal
import errno

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - WATCHDOG - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

SOUL_PATH = os.path.join(BASE_DIR, "soul.py")
SOUL_DIR = BASE_DIR

RUNTIME_DIR = os.path.join(SOUL_DIR, "runtime")
HEARTBEAT_FILE = os.path.join(RUNTIME_DIR, "heartbeat.txt")
SOUL_LOCK_FILE = os.path.join(RUNTIME_DIR, "soul.lock")
WATCHDOG_LOCK_FILE = os.path.join(RUNTIME_DIR, "watchdog.lock")

TIMEOUT_HEARTBEAT = int(os.environ.get("WATCHDOG_TIMEOUT_HEARTBEAT", "180"))
CONTROLLO_INTERVALLO = int(os.environ.get("WATCHDOG_CONTROLLO_INTERVALLO", "3"))
MAX_RIAVVII_CONSECUTIVI = int(
    os.environ.get("WATCHDOG_MAX_RIAVVII_CONSECUTIVI", "0")
)
PAUSA_RIAVVIO_BASE = int(os.environ.get("WATCHDOG_PAUSA_RIAVVIO_BASE", "10"))
PAUSA_RIAVVIO_MAX = int(os.environ.get("WATCHDOG_PAUSA_RIAVVIO_MAX", "60"))

processo = None
STOP = False


def assicura_runtime():
    if not os.path.exists(RUNTIME_DIR):
        os.makedirs(RUNTIME_DIR)


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
    except OSError as e:
        return getattr(e, "errno", None) == errno.EPERM
    except Exception:
        return False


def _leggi_pid_lock_watchdog():
    try:
        with open(WATCHDOG_LOCK_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return ""


def acquisisci_lock_watchdog():
    assicura_runtime()

    try:
        fd = os.open(
            WATCHDOG_LOCK_FILE,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY
        )

        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)

        logger.warning(
            "Lock watchdog acquisito da PID {}".format(os.getpid())
        )

        return True

    except OSError:
        pid_lock = _leggi_pid_lock_watchdog()

        if not pid_esiste(pid_lock):
            try:
                os.remove(WATCHDOG_LOCK_FILE)
                logger.warning(
                    "Lock watchdog orfano rimosso: PID {}".format(
                        pid_lock or "non valido"
                    )
                )
            except Exception as e:
                logger.error(
                    "Errore rimozione lock watchdog orfano: {}".format(e)
                )
                return False

            return acquisisci_lock_watchdog()

        logger.error(
            "Watchdog gia' attivo con PID {}: blocco secondo avvio."
            .format(pid_lock)
        )
        return False

    except Exception as e:
        logger.error(
            "Errore acquisizione lock watchdog: {}".format(e)
        )
        return False


def rilascia_lock_watchdog():
    try:
        if not os.path.exists(WATCHDOG_LOCK_FILE):
            return

        with open(WATCHDOG_LOCK_FILE, "r") as f:
            pid_lock = f.read().strip()

        if pid_lock == str(os.getpid()):
            os.remove(WATCHDOG_LOCK_FILE)
            logger.warning("Lock watchdog rilasciato")
        else:
            logger.warning(
                "Non rimuovo watchdog.lock: appartiene al PID {}".format(
                    pid_lock
                )
            )

    except Exception as e:
        logger.warning(
            "Errore rilascio lock watchdog: {}".format(e)
        )

def reset_runtime():
    try:
        assicura_runtime()

        if os.path.exists(HEARTBEAT_FILE):
            os.remove(HEARTBEAT_FILE)
            logger.info("Heartbeat precedente eliminato")

        if os.path.exists(SOUL_LOCK_FILE):
            os.remove(SOUL_LOCK_FILE)
            logger.warning(
                "soul.lock rimosso prima del riavvio "
                "(era rimasto da un'esecuzione precedente)"
            )

    except Exception as e:
        logger.warning("Errore reset runtime: {}".format(e))

def reset_heartbeat():
    reset_runtime()


def heartbeat_scaduto():
    try:
        if not os.path.exists(HEARTBEAT_FILE):
            logger.debug(
                "Heartbeat non ancora creato da soul.py"
            )
            return False

        with open(HEARTBEAT_FILE, "r") as f:
            valore = f.read().strip()

        if not valore:
            logger.info("Heartbeat vuoto")
            return False

        ultimo = float(valore)
        differenza = time.time() - ultimo

        logger.debug(
            "Heartbeat aggiornato {:.1f} secondi fa".format(
                differenza
            )
        )

        return differenza > TIMEOUT_HEARTBEAT

    except Exception as e:
        logger.warning(
            "Errore lettura heartbeat: {}".format(e)
        )
        return True


def avvia_soul():

    if os.name == "nt":
        python_cmd = r"C:\Python27\python.exe"
    else:
        python_cmd = sys.executable

    logger.warning(
        "Avvio soul.py da {}".format(SOUL_PATH)
    )

    logger.warning(
        "Python usato: {}".format(python_cmd)
    )

    logger.warning(
        "Working directory: {}".format(SOUL_DIR)
    )

    env = os.environ.copy()

    logger.warning(
        "NAO_IP: {}".format(
            env.get("NAO_IP", "default")
        )
    )

    log_path = os.path.join(
        RUNTIME_DIR,
        "soul_onboard.log"
    )

    log_file = open(log_path, "a")

    return subprocess.Popen(
        [python_cmd, SOUL_PATH],
        cwd=SOUL_DIR,
        env=env,
        stdout=log_file,
        stderr=log_file
    )

def termina_processo(p):
    try:
        if p and p.poll() is None:

            logger.warning("Termino soul.py")

            p.terminate()

            time.sleep(3)

            if p.poll() is None:

                logger.warning(
                    "Kill forzato di soul.py"
                )

                p.kill()

    except Exception as e:
        logger.error(
            "Errore durante terminazione soul.py: {}".format(e)
        )


def signal_handler(sig, frame):
    global STOP
    global processo

    logger.info("CTRL+C ricevuto: arresto completo")

    STOP = True

    if processo:
        termina_processo(processo)

    rilascia_lock_watchdog()

    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def main():
    global processo
    global STOP

    assicura_runtime()
    if not acquisisci_lock_watchdog():
        print("[WATCHDOG] Altra istanza già attiva. Uscita.")
        return

    if not os.path.exists(SOUL_PATH):
        logger.error(
            "soul.py non trovato: {}".format(SOUL_PATH)
        )
        rilascia_lock_watchdog()
        return

    riavvii = 0

    try:

        while not STOP:
            reset_runtime()

            processo = avvia_soul()

            while not STOP:

                time.sleep(CONTROLLO_INTERVALLO)

                # processo terminato
                if processo.poll() is not None:

                    logger.warning(
                        "soul.py terminato/crashato "
                        "con codice: {}".format(
                            processo.returncode
                        )
                    )

                    break

                # heartbeat bloccato
                if heartbeat_scaduto():

                    logger.warning(
                        "Heartbeat scaduto: "
                        "possibile freeze/dead loop"
                    )

                    termina_processo(processo)

                    break

            if STOP:
                break

            riavvii += 1

            logger.warning(
                "Riavvio numero {}".format(riavvii)
            )

            if (
                MAX_RIAVVII_CONSECUTIVI > 0
                and riavvii >= MAX_RIAVVII_CONSECUTIVI
            ):

                logger.error(
                    "Troppi riavvii consecutivi. "
                    "Stop watchdog."
                )

                break

            pausa = min(
                PAUSA_RIAVVIO_MAX,
                PAUSA_RIAVVIO_BASE * riavvii
            )

            logger.warning(
                "Attendo {} secondi prima del prossimo riavvio".format(
                    pausa
                )
            )

            time.sleep(pausa)
            
    except KeyboardInterrupt:

        logger.info("KeyboardInterrupt ricevuto")

        STOP = True

        if processo:
            termina_processo(processo)

    finally:

        rilascia_lock_watchdog()
        logger.info("Watchdog terminato")


if __name__ == "__main__":
    main()
