# -*- coding: utf-8 -*-

import time
import traceback

try:
    from naoqi import ALProxy
except Exception:
    ALProxy = None

try:
    import urllib2
except Exception:
    urllib2 = None


PC_IP = "172.16.165.75"
PC_PORT = 8765


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

    tts = None
    memory = None

    try:
        tts = ALProxy("ALTextToSpeech", "127.0.0.1", 9559)
        memory = ALProxy("ALMemory", "127.0.0.1", 9559)

        memory.insertData("AutonomousSystem/Status", "BOOTSTRAP_STARTED")
        memory.insertData("AutonomousSystem/Command", "START")
        memory.insertData("AutonomousSystem/BootstrapTime", time.time())

        parla(tts, "Sistema autonomo in avvio.")
        scrivi_log("ALMemory aggiornata: Command=START")

    except Exception as e:
        scrivi_log("ERRORE inizializzazione NAOqi: %s" % str(e))
        scrivi_log(traceback.format_exc())

    ok, risposta = chiama_pc("/ping")
    scrivi_log("PING PC: ok=%s risposta=%s" % (ok, risposta))

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