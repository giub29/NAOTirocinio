# -*- coding: utf-8 -*-
"""
NAO Robot Soul - Sistema di controllo principale del robot NAO.
"""

import json
import time
import threading
import os 
import re
import logging
import sys

if sys.version_info[0] < 3:
    reload(sys)
    sys.setdefaultencoding('utf-8')

from modules.vision_perception import NaoVision
from modules.voice_interaction import NaoVoice
from modules.system_manager import NaoSystem
from modules.hardware_control import NaoBody
from sensi import NaoSenses

from core.memory_manager import carica_memoria, salva_memoria
from core.robot_state import crea_stato_robot, aggiorna_stato_robot

from behaviors.action_behavior import valida_decisione, esegui_decisione
from behaviors.safety_behavior import gestisci_emergenza, gestisci_ostacoli_durante_cammino
from behaviors.llm_behavior import genera_decisione_anima, analizza_immagine
from behaviors.face_behavior import gestisci_volto_durante_cammino, gestisci_input_nome
from behaviors.condition_manager import valuta_condizioni_generate

from behaviors.adaptive_behavior import (
    nessuna_condizione_nota,
    gestisci_comportamento_adattivo
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


IP_ROBOT = "172.16.165.86"
CHIAVE_PRIVATA = os.getenv("OPENAI_API_KEY")

TEMPO_INERZIA_INIZIATIVA = 30
LUNGHEZZA_MAX_RICORDI = 20
VELOCITA_CAMMINO = 0.3

ANGOLO_SGUARDO_NEUTRO = (0.0, -0.35)
ANGOLO_SGUARDO_INIZIATIVA = (0.0, -0.2)
HEARTBEAT_DIR = os.path.join(os.path.dirname(__file__), "runtime")
HEARTBEAT_FILE = os.path.join(HEARTBEAT_DIR, "heartbeat.txt")


def aggiorna_heartbeat():
    try:
        if not os.path.exists(HEARTBEAT_DIR):
            os.makedirs(HEARTBEAT_DIR)

        with open(HEARTBEAT_FILE, "w") as f:
            f.write(str(time.time()))

    except Exception:
        pass

messaggio_utente = ""
input_ricevuto = False
STOP_PROGRAMMA = False

memoria_fisica = {}
ultima_batteria_letta = -1

stato_robot = crea_stato_robot()
DEBUG_STATO = False

stato_runtime = {
    "attesa_nome": False,
    "riprendi_dopo_nome": False,
    "primo_ignoto_tempo": 0,
    "ultimo_volto_noto_tempo": 0,
    "ultimo_nome_riconosciuto": "",
    "volti_salutati": [],
    "in_pattugliamento": False
}


def _estrai_ricordi_dalla_decisione(elementi):
    ricordi = []
    fatti = {}

    for item in elementi:
        try:
            tipo = item.get("tipo", "ricordo")

            if tipo == "fatto_utente":
                chiave = item.get("chiave", "")
                valore = item.get("valore", "")

                if chiave and valore:
                    fatti[chiave] = valore

            else:
                ricordi.append({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "contenuto": item.get("contenuto", str(item))
                })

        except Exception as e:
            logger.warning(u"Errore nell'estrazione elemento memoria: {}".format(e))

    return ricordi, fatti


def aggiorna_memoria_da_decisione(decisione):
    global memoria_fisica

    elementi = decisione.get("memoria", [])

    if not isinstance(elementi, list):
        logger.warning(u"Elementi memoria non è una lista")
        return

    if "ricordi_recenti" not in memoria_fisica:
        memoria_fisica["ricordi_recenti"] = []

    if "fatti_importanti" not in memoria_fisica:
        memoria_fisica["fatti_importanti"] = {}

    ricordi, fatti = _estrai_ricordi_dalla_decisione(elementi)

    memoria_fisica["ricordi_recenti"].extend(ricordi)
    memoria_fisica["ricordi_recenti"] = memoria_fisica["ricordi_recenti"][-LUNGHEZZA_MAX_RICORDI:]

    memoria_fisica["fatti_importanti"].update(fatti)

    salva_memoria(memoria_fisica)

    logger.debug(u"Memoria aggiornata: {} ricordi, {} fatti".format(
        len(ricordi),
        len(fatti)
    ))


def _thread_input_utente():
    global messaggio_utente, input_ricevuto

    while True:
        try:
            t = raw_input()
            messaggio_utente = t.decode("utf-8", "ignore")
            input_ricevuto = True

        except Exception as e:
            logger.debug(u"Errore nella lettura input: {}".format(e))


def _inizializza_robot(corpo, voce, vista, sistema):
    sistema.set_vita_autonoma(False)
    corpo.abilita_motori()
    corpo.vai_in_posa("Stand")
    vista.attiva_inseguimento_volto()
    logger.info(u"Robot inizializzato")


def _processa_input_utente(mondo, corpo, voce):
    global input_ricevuto, messaggio_utente, STOP_PROGRAMMA

    if input_ricevuto and messaggio_utente:
        testo_user = messaggio_utente.lower().strip()

        if "spegni" in testo_user or "chiudi" in testo_user or "esci" in testo_user:
            stato_runtime["in_pattugliamento"] = False
            corpo.fermati()
            voce.parla(u"Mi sto spegnendo. A presto.")
            STOP_PROGRAMMA = True
            logger.info(u"Spegnimento richiesto dall'utente")

        elif "vai" in testo_user or "cammina" in testo_user:
            stato_runtime["in_pattugliamento"] = True
            corpo.guarda(*ANGOLO_SGUARDO_NEUTRO)
            logger.debug(u"Comando vai/cammina ricevuto")

        elif "stop" in testo_user or "fermati" in testo_user:
            stato_runtime["in_pattugliamento"] = False
            corpo.fermati()
            logger.debug(u"Comando stop/fermati ricevuto")

    return mondo


def _normalizza_mondo_fermo(mondo, corpo):
    if not corpo.sta_camminando() and not stato_runtime["in_pattugliamento"]:
        mondo = mondo.replace(u"Ostacolo frontale molto vicino", u"Vedo qualcosa vicino")
        mondo = mondo.replace(u"Ostacolo a sinistra", u"C'è qualcosa a sinistra")
        mondo = mondo.replace(u"Ostacolo a destra", u"C'è qualcosa a destra")

    return mondo


def _processa_batteria(mondo):
    global ultima_batteria_letta

    if u"batteria" in mondo:
        match_bat = re.search(u"La mia batteria.*?(\\d+)%[.]?", mondo)

        if match_bat:
            if ultima_batteria_letta == -1:
                ultima_batteria_letta = int(match_bat.group(1))
            else:
                mondo = mondo.replace(match_bat.group(0), u"").strip()

    return mondo


def _valuta_interazione_reale(mondo):
    return (
        messaggio_utente != "" or
        u"Riconosco" in mondo or
        u"Vedo un volto ignoto" in mondo or
        u"carezza" in mondo or
        u"URTO" in mondo or
        u"PERICOLO" in mondo
    )


def _gestisci_iniziativa_robot(corpo):
    logger.info(u"Robot prende l'iniziativa")

    corpo.imposta_colore_occhi("yellow")
    corpo.guarda(*ANGOLO_SGUARDO_INIZIATIVA)
    time.sleep(1)

    img_b64 = corpo.scatta_foto(camera_id=0, nome_file="curiosita.jpg")

    if img_b64:
        desc = analizza_immagine(img_b64, CHIAVE_PRIVATA, contesto="stanza")
    else:
        desc = u"una stanza tranquilla"

    return u" PRENDI L'INIZIATIVA. Vedi: {}. Usa la memoria e chiedi 'Cosa faresti tu?'.".format(desc)


def _pulisci_mondo_da_volti_salutati(mondo):
    for nome in stato_runtime["volti_salutati"]:
        pattern = u"Riconosco {}\\.".format(re.escape(nome))
        mondo = re.sub(pattern, u"", mondo, flags=re.IGNORECASE)

    return mondo


def _aggiungi_stato_movimento(mondo, corpo):
    if corpo.sta_camminando() or stato_runtime["in_pattugliamento"]:
        return mondo + u" STO CAMMINANDO."

    return mondo + u" SONO FERMO."


def _elabora_decisione(mondo, corpo, voce, vista, sistema):
    decisione = genera_decisione_anima(
        mondo,
        memoria_fisica,
        stato_robot,
        CHIAVE_PRIVATA
    )

    decisione = valida_decisione(decisione, mondo)

    logger.info(u"Stato: {}".format(decisione.get("stato_interno", "neutro")))
    logger.info(u"Obiettivo: {}".format(decisione.get("obiettivo", "")))
    logger.info(u"Azioni: {}".format(
        json.dumps(decisione.get("azioni", []), ensure_ascii=False)
    ))

    esegui_decisione(
        decisione,
        corpo,
        voce,
        vista,
        sistema,
        stato_runtime,
        aggiorna_memoria_callback=aggiorna_memoria_da_decisione
    )

    return decisione


def _riprendi_cammino_automatico(corpo, ultima_decisione):
    if stato_runtime["in_pattugliamento"] and not corpo.sta_camminando():
        azioni_testo = json.dumps(ultima_decisione.get("azioni", []))

        if (
            "cammina" not in azioni_testo and
            "gira" not in azioni_testo and
            "fermati" not in azioni_testo
        ):
            corpo.cammina(VELOCITA_CAMMINO, 0.0)
            logger.debug(u"Cammino automatico ripreso")


def main():
    global messaggio_utente, input_ricevuto, STOP_PROGRAMMA
    global memoria_fisica, stato_robot

    ultimo_evento_tempo = time.time()
    memoria_fisica = carica_memoria()
    corpo = None

    try:
        logger.info(u"Connessione al robot: {}".format(IP_ROBOT))

        corpo = NaoBody(IP_ROBOT)
        sensi = NaoSenses(IP_ROBOT)
        voce = NaoVoice(IP_ROBOT)
        vista = NaoVision(IP_ROBOT)
        sistema = NaoSystem(IP_ROBOT)

        _inizializza_robot(corpo, voce, vista, sistema)

        thread_input = threading.Thread(target=_thread_input_utente)
        thread_input.daemon = True
        thread_input.start()

        logger.info(u"Sistemi pronti")

        voce.parla(u"Sistemi pronti. Ciao {}, io sono NAO.".format(
            memoria_fisica.get("nome_utente", "amico")
        ))

        stato_precedente = ""
        ultima_decisione = {"azioni": []}

        while not STOP_PROGRAMMA:
            aggiorna_heartbeat()
            
            mondo = sensi.ottieni_report_semantico()

            stato_robot = aggiorna_stato_robot(
                stato_robot,
                mondo,
                corpo,
                stato_runtime["in_pattugliamento"],
                stato_runtime["ultimo_nome_riconosciuto"]
            )

            if DEBUG_STATO:
                logger.debug(u"STATO ROBOT: {}".format(
                    json.dumps(stato_robot, ensure_ascii=False)
                ))
                logger.debug(u"OBIETTIVO: {}".format(
                    stato_robot.get("obiettivo_corrente", "nessuno")
                ))

            if gestisci_emergenza(mondo, corpo, voce, stato_runtime):
                continue

            if gestisci_ostacoli_durante_cammino(mondo, corpo, stato_runtime):
                continue

            if stato_runtime["attesa_nome"] and input_ricevuto:
                gestisci_input_nome(
                    corpo,
                    voce,
                    vista,
                    stato_runtime,
                    messaggio_utente,
                    VELOCITA_CAMMINO
                )

                messaggio_utente = ""
                input_ricevuto = False
                continue

            _processa_input_utente(mondo, corpo, voce)

            if STOP_PROGRAMMA:
                break

            mondo = _normalizza_mondo_fermo(mondo, corpo)
            mondo = _processa_batteria(mondo)

            interazione_reale = _valuta_interazione_reale(mondo)

            if interazione_reale:
                ultimo_evento_tempo = time.time()

            else:
                tempo_di_inerzia = time.time() - ultimo_evento_tempo

                if (
                    not corpo.sta_camminando() and
                    messaggio_utente == "" and
                    tempo_di_inerzia > TEMPO_INERZIA_INIZIATIVA
                ):
                    mondo += _gestisci_iniziativa_robot(corpo)
                    ultimo_evento_tempo = time.time()

            mondo = _pulisci_mondo_da_volti_salutati(mondo)
            mondo = re.sub(r"\s+", " ", mondo).strip()
            mondo = _aggiungi_stato_movimento(mondo, corpo)

            if input_ricevuto and messaggio_utente:
                mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
                messaggio_utente = ""
                input_ricevuto = False

            elif input_ricevuto:
                input_ricevuto = False

            if not stato_runtime["attesa_nome"]:
                if mondo != stato_precedente and mondo.strip() != "REPORT: SONO FERMO.":
                    logger.info(u"SENSORI: {}".format(mondo))

                    if gestisci_volto_durante_cammino(
                        mondo,
                        corpo,
                        voce,
                        vista,
                        stato_runtime
                    ):
                        stato_precedente = mondo
                        time.sleep(0.1)
                        continue

                    decisione_condizione = valuta_condizioni_generate(mondo, stato_runtime)

                    if decisione_condizione:
                        logger.info(u"[SOUL] Uso condizione Python generata/caricata")

                        decisione_condizione = valida_decisione(decisione_condizione, mondo)

                        esegui_decisione(
                            decisione_condizione,
                            corpo,
                            voce,
                            vista,
                            sistema,
                            stato_runtime,
                            aggiorna_memoria_callback=aggiorna_memoria_da_decisione
                        )

                        ultima_decisione = decisione_condizione

                    else:
                        ultima_decisione = _elabora_decisione(
                            mondo,
                            corpo,
                            voce,
                            vista,
                            sistema
                        )

                        if nessuna_condizione_nota(mondo, ultima_decisione):
                            logger.info(u"[SOUL] Attivo comportamento adattivo")

                            decisione_adattiva = gestisci_comportamento_adattivo(
                                mondo,
                                memoria_fisica,
                                stato_robot,
                                CHIAVE_PRIVATA
                            )

                            decisione_adattiva = valida_decisione(decisione_adattiva, mondo)

                            esegui_decisione(
                                decisione_adattiva,
                                corpo,
                                voce,
                                vista,
                                sistema,
                                stato_runtime,
                                aggiorna_memoria_callback=aggiorna_memoria_da_decisione
                            )

                            ultima_decisione = decisione_adattiva

                    ultimo_evento_tempo = time.time()

            _riprendi_cammino_automatico(corpo, ultima_decisione)

            stato_precedente = mondo
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info(u"Arresto richiesto dall'utente")

    except Exception as e:
        logger.error(u"Errore nel ciclo principale: {}".format(e), exc_info=True)

    finally:
        logger.info(u"Pulizia risorse...")

        if corpo:
            corpo.fermati()
            corpo.disabilita_motori()

        logger.info(u"Sistema spento correttamente")


if __name__ == "__main__":
    main()