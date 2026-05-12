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
import signal

utente_sta_scrivendo = False
ultimo_input_tempo = 0
MODALITA_TEST = True

if sys.version_info[0] < 3:
    reload(sys)
    sys.setdefaultencoding('utf-8')

import codecs
sys.stdout = codecs.getwriter("utf-8")(sys.stdout)

from utils.text_utils import normalizza_testo_ascii, testo_per_log

from modules.vision_perception import NaoVision
from modules.voice_interaction import NaoVoice
from modules.system_manager import NaoSystem
from modules.hardware_control import NaoBody
from sensi import NaoSenses

from core.memory_manager import carica_memoria, salva_memoria
from core.robot_state import crea_stato_robot, aggiorna_stato_robot

from behaviors import autonomy_supervisor
from behaviors.action_behavior import valida_decisione, esegui_decisione
from behaviors.safety_behavior import gestisci_emergenza, gestisci_ostacoli_durante_cammino
from behaviors.llm_behavior import genera_decisione_anima, analizza_immagine
from behaviors.face_behavior import gestisci_volto_durante_cammino, gestisci_input_nome
from behaviors.condition_manager import esegui_condizione_per_nome, valuta_condizioni_generate
from behaviors.condition_generator import (
    genera_condizione_autonoma,
    valuta_se_generare_condizione,
    estrai_eventi
)

import colorlog

handler = colorlog.StreamHandler()

handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'red,bg_white',
    }
))

root_logger = logging.getLogger()
root_logger.handlers = []
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)
logging.getLogger("WATCHDOG").setLevel(logging.WARNING)
logging.getLogger("behaviors.autonomy_supervisor").setLevel(logging.WARNING)
logging.getLogger("behaviors.condition_generator").setLevel(logging.WARNING)
logging.getLogger("behaviors.safety_behavior").setLevel(logging.WARNING)
logging.getLogger("behaviors.condition_manager").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


IP_ROBOT = "172.16.165.86"
CHIAVE_PRIVATA = os.getenv("OPENAI_API_KEY")

TEMPO_INERZIA_INIZIATIVA = 20
LUNGHEZZA_MAX_RICORDI = 20
VELOCITA_CAMMINO = 0.3

ANGOLO_SGUARDO_NEUTRO = (0.0, -0.15)
ANGOLO_SGUARDO_INIZIATIVA = (0.0, -0.2)
HEARTBEAT_DIR = os.path.join(os.path.dirname(__file__), "runtime")
HEARTBEAT_FILE = os.path.join(HEARTBEAT_DIR, "heartbeat.txt")


def aggiorna_heartbeat():
    try:
        if not os.path.exists(HEARTBEAT_DIR):
            os.makedirs(HEARTBEAT_DIR)

        tmp_file = HEARTBEAT_FILE + ".tmp"

        with open(tmp_file, "w") as f:
            f.write(str(time.time()))

        if os.path.exists(HEARTBEAT_FILE):
            os.remove(HEARTBEAT_FILE)

        os.rename(tmp_file, HEARTBEAT_FILE)

    except Exception:
        pass

messaggio_utente = ""
input_ricevuto = False
STOP_PROGRAMMA = False

ULTIMA_GENERAZIONE_SAFETY_TEMPO = 0
ULTIMO_MONDO_SAFETY_GENERATO = ""
INTERVALLO_GENERAZIONE_SAFETY = 8

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
    "ultimo_messaggio_safety_tempo": 0,
    "volti_salutati": [],
    "in_pattugliamento": False,
    "comando_stop_immediato": False,
    "ultima_curiosita_stop_tempo": 0,
    "ultimo_volto_ignoto_rilevato": False,
    "ultimo_evento_reale_tempo": 0
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
    global utente_sta_scrivendo, ultimo_input_tempo

    while True:
        try:
            utente_sta_scrivendo = True

            t = raw_input()

            utente_sta_scrivendo = False
            ultimo_input_tempo = time.time()

            testo = t.decode("utf-8", "ignore").lower().strip()

            if "stop" in testo or "fermati" in testo or "ferma" in testo:
                stato_runtime["comando_stop_immediato"] = True

            messaggio_utente = testo
            input_ricevuto = True

        except Exception as e:
            utente_sta_scrivendo = False
            logger.debug(u"Errore nella lettura input: {}".format(e))

def _inizializza_robot(corpo, voce, vista, sistema):
    sistema.set_vita_autonoma(False)
    corpo.abilita_motori()
    corpo.vai_in_posa("Stand")
    vista.attiva_inseguimento_volto()
    corpo.guarda(0.0, -0.15)
    time.sleep(0.5)
    logger.info(u"Robot inizializzato")


def _processa_input_utente(mondo, corpo, voce, vista, sistema):
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
            stato_runtime["ultimo_comando_vai_tempo"] = time.time()
            corpo.guarda(*ANGOLO_SGUARDO_NEUTRO)
            corpo.cammina(VELOCITA_CAMMINO, 0.0)
            logger.info(u"Comando vai/cammina ricevuto: avvio pattugliamento")
        
        elif "registra volto" in testo_user or "impara volto" in testo_user:
            stato_runtime["attesa_nome"] = True
            stato_runtime["riprendi_dopo_nome"] = False
            corpo.fermati()
            corpo.guarda(*ANGOLO_SGUARDO_INIZIATIVA)
            voce.parla(u"Va bene, dimmi il nome della persona.")

        elif "stop" in testo_user or "fermati" in testo_user or "ferma" in testo_user:
            stato_runtime["in_pattugliamento"] = False
            corpo.fermati()
            logger.debug(u"Comando stop/fermati ricevuto")

        elif testo_user.startswith("test condizione") or testo_user.startswith("test"):
            nome = testo_user.replace("test condizione", "").replace("test", "").strip()

            decisione = esegui_condizione_per_nome(
                nome,
                mondo,
                stato_runtime
            )

            if decisione:
                esegui_decisione(
                    decisione,
                    corpo,
                    voce,
                    vista,
                    sistema,
                    stato_runtime
                )

            messaggio_utente = ""
            input_ricevuto = False
            return mondo

        messaggio_utente = ""
        input_ricevuto = False

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
            batteria = int(match_bat.group(1))

            # Caso importante: batteria bassa.
            # NON rimuovo l'informazione dal mondo, perché serve al supervisore.
            if batteria <= 25:
                ultima_batteria_letta = batteria
                return mondo

            # Caso normale: batteria stabile/non critica.
            # La rimuovo per non far ragionare NAO sempre sulla batteria.
            if ultima_batteria_letta == -1:
                ultima_batteria_letta = batteria
                mondo = mondo.replace(match_bat.group(0), u"").strip()
            else:
                if batteria == ultima_batteria_letta:
                    mondo = mondo.replace(match_bat.group(0), u"").strip()
                else:
                    ultima_batteria_letta = batteria
                    mondo = mondo.replace(match_bat.group(0), u"").strip()

    mondo = re.sub(r"\s+", " ", mondo).strip()
    return mondo


def _valuta_interazione_reale(mondo):
    testo = mondo.lower()

    return (
        messaggio_utente != "" or
        u"riconosco" in testo or
        u"volto ignoto" in testo or
        u"carezza" in testo or
        u"tocco" in testo or
        u"mano" in testo or
        u"entrambe le mani" in testo or
        u"urto" in testo or
        u"pericolo" in testo or
        u"qualcosa a destra" in testo or
        u"qualcosa a sinistra" in testo or
        u"ostacolo a destra" in testo or
        u"ostacolo a sinistra" in testo
    )

def _mondo_ha_eventi_multipli(mondo):
    """
    Rileva se nel mondo ci sono almeno due eventi sensoriali reali.
    INTERAZIONE_UTENTE e Evento recente da soli NON contano.
    """
    try:
        testo = mondo.lower()
    except:
        return False

    segnali = 0

    if u"riconosco" in testo:
        segnali += 1

    if u"volto ignoto" in testo:
        segnali += 1

    if u"carezza" in testo and u"testa" in testo:
        segnali += 1

    if u"mano sinistra" in testo:
        segnali += 1

    if u"mano destra" in testo:
        segnali += 1

    if u"entrambe le mani" in testo:
        segnali += 1

    if u"vedo qualcosa vicino" in testo or u"qualcosa vicino" in testo:
        segnali += 1

    if u"ostacolo" in testo:
        segnali += 1
    
    if u"ostacolo frontale ai piedi" in testo:
        segnali += 2

    if u"urto tattile" in testo or u"piede sinistro" in testo or u"piede destro" in testo:
        segnali += 1

    if u"pericolo caduta" in testo or u"sollevamento" in testo or u"pavimento mancante" in testo:
        segnali += 1

    # Cammino + un evento fisico = condizione composta utile
    if u"sto camminando" in testo and segnali >= 1:
        segnali += 1

    return segnali >= 2

def _sincronizza_nome_runtime_da_mondo(mondo):
    """
    Evita che NAO continui a ragionare come se stesse parlando con Giulia
    quando nel report attuale c'e' solo un volto ignoto o nessun volto noto.
    """
    try:
        testo = mondo.lower()
    except:
        return

    match = re.search(u"riconosco ([^\\.]+)", mondo, flags=re.IGNORECASE)

    if match:
        nome = match.group(1).strip()
        if nome:
            stato_runtime["ultimo_nome_riconosciuto"] = nome
        return

    if u"vedo un volto ignoto" in testo and u"riconosco" not in testo:
        stato_runtime["ultimo_nome_riconosciuto"] = ""
        stato_runtime["ultimo_volto_noto_tempo"] = 0
        
def _gestisci_iniziativa_robot(corpo, voce):
    logger.info(u"[SOUL] Nessuna condizione rilevata: osservo l'ambiente")

    corpo.imposta_colore_occhi("yellow")
    corpo.guarda(*ANGOLO_SGUARDO_INIZIATIVA)

    time.sleep(1)

    img_b64 = corpo.scatta_foto(
        camera_id=0,
        nome_file="osservazione_autonoma.jpg"
    )

    if img_b64:
        descrizione = analizza_immagine(
            img_b64,
            CHIAVE_PRIVATA,
            contesto="osservazione autonoma ambiente"
        )
    else:
        descrizione = u"non riesco a vedere chiaramente l'ambiente"

    voce.parla(u"Sto osservando l'ambiente.")
    voce.parla(descrizione[:200])

    return (
        u" OSSERVAZIONE_AUTONOMA. "
        u"NESSUNA_CONDIZIONE_ATTIVA. "
        u"VEDO: {}.".format(descrizione)
    )

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

    logger.info(u"Stato: {}".format(testo_per_log(decisione.get("stato_interno", "neutro"))))
    logger.info(u"Obiettivo: {}".format(testo_per_log(decisione.get("obiettivo", ""))))
    logger.info(u"Azioni: {}".format(
        testo_per_log(json.dumps(decisione.get("azioni", []), ensure_ascii=False))
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

def _tenta_generare_condizione_da_evento_safety(mondo, motivo):
    """
    Permette di generare condizioni anche quando un evento fisico viene
    intercettato dalla safety prima del normale flusso decisionale.

    Per evitare spam di generazione:
    - non ritenta la stessa situazione continuamente;
    - applica un cooldown temporale;
    - lascia comunque la safety prioritaria.
    """

    global ULTIMA_GENERAZIONE_SAFETY_TEMPO
    global ULTIMO_MONDO_SAFETY_GENERATO

    try:
        if not CHIAVE_PRIVATA:
            logger.warning(u"[SOUL] Non posso generare condizione da safety: OPENAI_API_KEY assente")
            return

        adesso = time.time()
        mondo_norm = (mondo or "").strip().lower()

        if mondo_norm == ULTIMO_MONDO_SAFETY_GENERATO:
            logger.debug(u"[SOUL] Generazione safety saltata: situazione gia' tentata")
            return

        if adesso - ULTIMA_GENERAZIONE_SAFETY_TEMPO < INTERVALLO_GENERAZIONE_SAFETY:
            logger.debug(u"[SOUL] Generazione safety saltata: cooldown attivo")
            return

        ULTIMA_GENERAZIONE_SAFETY_TEMPO = adesso
        ULTIMO_MONDO_SAFETY_GENERATO = mondo_norm

        decisione_safety = {
            "stato_interno": "sicurezza",
            "obiettivo": motivo,
            "azioni": [
                {
                    "tipo": "fermati"
                },
                {
                    "tipo": "parla",
                    "testo": "Mi fermo per sicurezza."
                }
            ],
            "memoria": []
        }

        if valuta_se_generare_condizione(
            mondo,
            decisione_safety,
            memoria_fisica,
            stato_robot,
            CHIAVE_PRIVATA
        ):
            logger.info(u"[SOUL] Genero condizione autonoma da evento safety: {}".format(
                testo_per_log(motivo)
            ))

            nuova_condizione = genera_condizione_autonoma(
                mondo,
                memoria_fisica,
                stato_robot,
                CHIAVE_PRIVATA
            )

            if nuova_condizione:
                logger.info(u"[SOUL] Nuova condizione autonoma creata da safety: {}".format(
                    nuova_condizione
                ))

    except Exception as e:
        logger.warning(u"[SOUL] Errore generazione condizione da evento safety: {}".format(e))

def _riprendi_cammino_automatico(corpo, ultima_decisione):
    if not stato_runtime.get("in_pattugliamento", False):
        return

    if corpo.sta_camminando():
        return

    if time.time() - stato_runtime.get("ultimo_evento_fisico_gestito_tempo", 0) < 3.0:
        return

    corpo.cammina(VELOCITA_CAMMINO, 0.0)
    logger.debug(u"Cammino automatico ripreso")

def handle_exit(sig, frame):
    print("Soul arrestato pulitamente")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)

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
        sistema.configura_autonomous_life_da_env()
        _inizializza_robot(corpo, voce, vista, sistema)

        thread_input = threading.Thread(target=_thread_input_utente)
        thread_input.daemon = True
        thread_input.start()

        logger.info(u"Sistemi pronti")
        aggiorna_heartbeat()

        voce.parla(u"Sistemi pronti. Ciao {}, io sono NAO.".format(
            memoria_fisica.get("nome_utente", "amico")
        ))

        stato_precedente = ""
        ultima_decisione = {"azioni": []}

        while not STOP_PROGRAMMA:
            aggiorna_heartbeat()
            

            if time.time() - ultimo_input_tempo < 2.0 and not input_ricevuto:
                time.sleep(0.1)
                continue

            if stato_runtime.get("comando_stop_immediato", False):
                logger.warning(u"[SAFETY] Stop immediato richiesto dall'utente")

                stato_runtime["comando_stop_immediato"] = False
                stato_runtime["in_pattugliamento"] = False
                stato_runtime["mantieni_pattugliamento"] = False
                input_ricevuto = False
                messaggio_utente = ""

                corpo.fermati()
                aggiorna_heartbeat()

                # Se lo stop arriva subito dopo un evento reale,
                # non avvio curiosità: mi limito a fermarmi.
                ultimo_evento = stato_runtime.get("ultimo_evento_reale_tempo", 0)
                adesso = time.time()

                if adesso - ultimo_evento < 10:
                    voce.parla(u"Mi fermo.")
                    logger.info(u"[SOUL] Curiosita dopo stop saltata: evento reale recente.")
                    stato_precedente = ""
                    time.sleep(0.1)
                    continue

                adesso = time.time()
                if adesso - stato_runtime.get("ultima_curiosita_stop_tempo", 0) < 60:
                    voce.parla(u"Mi fermo.")
                    stato_precedente = ""
                    time.sleep(0.1)
                    continue

                stato_runtime["ultima_curiosita_stop_tempo"] = adesso

                voce.parla(u"Mi fermo. Ora osservo l'ambiente.")
                aggiorna_heartbeat()

                try:
                    corpo.imposta_colore_occhi("yellow")
                    corpo.guarda(*ANGOLO_SGUARDO_INIZIATIVA)
                    time.sleep(1)

                    img_b64 = corpo.scatta_foto(camera_id=0, nome_file="curiosita_stop.jpg")
                    aggiorna_heartbeat()

                    if img_b64:
                        descrizione = analizza_immagine(
                            img_b64,
                            CHIAVE_PRIVATA,
                            contesto="ambiente dopo stop"
                        )
                        aggiorna_heartbeat()
                    else:
                        descrizione = u"non riesco a vedere chiaramente l'ambiente"

                    voce.parla(u"Ho osservato l'ambiente. Ti descrivo cosa vedo.")
                    voce.parla(descrizione[:180])

                    mondo_curioso = u"REPORT: PRENDI L'INIZIATIVA. SONO FERMO. VEDO: {}.".format(
                        descrizione
                    )

                    decisione_curiosa = _elabora_decisione(
                        mondo_curioso,
                        corpo,
                        voce,
                        vista,
                        sistema
                    )

                    ultima_decisione = decisione_curiosa
                    aggiorna_heartbeat()
                    ultimo_evento_tempo = time.time()

                except Exception as e:
                    logger.warning(u"[SOUL] Curiosita dopo stop fallita: {}".format(e))

                stato_precedente = ""
                time.sleep(0.1)
                continue

            mondo = sensi.ottieni_report_semantico()
            mondo = normalizza_testo_ascii(mondo)
            _sincronizza_nome_runtime_da_mondo(mondo)

            # Filtro anti-falso-positivo: mano sinistra ripetuta da ferma
            if (
                u"Sento un tocco sulla mano sinistra" in mondo and
                not corpo.sta_camminando() and
                not stato_runtime.get("in_pattugliamento", False)
            ):
                adesso = time.time()
                ultimo = stato_runtime.get("ultimo_tocco_mano_sinistra_tempo", 0)

                if adesso - ultimo < 5:
                    logger.info(u"[SOUL] Tocco mano sinistra ignorato: possibile falso positivo.")
                    stato_precedente = mondo
                    time.sleep(0.1)
                    continue

                stato_runtime["ultimo_tocco_mano_sinistra_tempo"] = adesso

            if stato_runtime.get("attesa_nome", False) and input_ricevuto and messaggio_utente:
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
                stato_precedente = ""
                ultimo_evento_tempo = time.time()
                continue

            mondo = _processa_input_utente(mondo, corpo, voce, vista, sistema)

            if STOP_PROGRAMMA:
                break

            if (
                not corpo.sta_camminando() and
                not stato_runtime["in_pattugliamento"] and
                u"URTO" not in mondo and
                (
                    u"Sento una carezza" in mondo or
                    u"Sento un tocco sulla mano" in mondo or
                    u"Vedo qualcosa vicino" in mondo
                )
            ):
                mondo += u" INTERAZIONE_UTENTE."

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
                stato_runtime["ultimo_evento_fisico_gestito_tempo"] = time.time()
                stato_precedente = mondo
                time.sleep(0.2)
                continue

            if gestisci_ostacoli_durante_cammino(mondo, corpo, stato_runtime):
                stato_runtime["ultimo_evento_fisico_gestito_tempo"] = time.time()

                mondo_evento = mondo + u" STO CAMMINANDO."

                stato_runtime["eventi"] = estrai_eventi(mondo_evento, stato_runtime)
                stato_runtime["memoria"] = memoria_fisica
                stato_runtime["stato_robot"] = stato_robot
                stato_runtime["openai_api_key"] = CHIAVE_PRIVATA

                decisione_condizione = valuta_condizioni_generate(mondo_evento, stato_runtime)

                if decisione_condizione:
                    decisione_condizione = valida_decisione(decisione_condizione, mondo_evento)

                    stato_runtime["mantieni_pattugliamento"] = True

                    try:
                        esegui_decisione(
                            decisione_condizione,
                            corpo,
                            voce,
                            vista,
                            sistema,
                            stato_runtime,
                            aggiorna_memoria_callback=aggiorna_memoria_da_decisione
                        )
                        
                    finally:
                        stato_runtime["mantieni_pattugliamento"] = False

                    ultima_decisione = decisione_condizione
                    stato_runtime["in_pattugliamento"] = True
                else:
                    _tenta_generare_condizione_da_evento_safety(
                        mondo_evento,
                        u"ostacolo o urto durante il cammino"
                    )
                
                stato_precedente = mondo_evento
                time.sleep(0.2)
                continue

            mondo = _normalizza_mondo_fermo(mondo, corpo)
            mondo = _processa_batteria(mondo)
            testo_mondo = mondo.lower()

            solo_percezione_spaziale_fermo = (
                not stato_runtime["in_pattugliamento"] and
                not corpo.sta_camminando() and
                "sono fermo" in testo_mondo and
                (
                    "c'e' qualcosa a destra" in testo_mondo or
                    "c'è qualcosa a destra" in testo_mondo or
                    "c'e' qualcosa a sinistra" in testo_mondo or
                    "c'è qualcosa a sinistra" in testo_mondo
                ) and
                "urto" not in testo_mondo and
                "tocco" not in testo_mondo and
                "volto" not in testo_mondo and
                "riconosco" not in testo_mondo
            )

            if solo_percezione_spaziale_fermo:
                stato_precedente = mondo
                time.sleep(0.1)
                continue

            if mondo.strip() in [
                u"REPORT:",
                u"REPORT: SONO FERMO.",
                u"SONO FERMO.",
                u""
            ]:
                stato_precedente = mondo
                time.sleep(0.1)
                continue

            interazione_reale = _valuta_interazione_reale(mondo)

            if interazione_reale:
                ultimo_evento_tempo = time.time()
                stato_runtime["ultimo_evento_reale_tempo"] = time.time()

            else:
                tempo_di_inerzia = time.time() - ultimo_evento_tempo

                if (
                    not corpo.sta_camminando() and
                    messaggio_utente == "" and
                    tempo_di_inerzia > TEMPO_INERZIA_INIZIATIVA
                    and mondo.strip() in [
                        u"REPORT:",
                        u"REPORT: SONO FERMO.",
                        u"SONO FERMO.",
                        u""
                    ]
                ):
                    ultimo_evento = stato_runtime.get("ultimo_evento_reale_tempo", 0)
                    adesso = time.time()

                    if adesso - ultimo_evento < 10:
                        logger.info(u"[SOUL] Iniziativa saltata: evento reale recente.")
                    else:
                        mondo += _gestisci_iniziativa_robot(corpo, voce)
                        ultimo_evento_tempo = time.time()

            mondo = _pulisci_mondo_da_volti_salutati(mondo)
            mondo = re.sub(r"\s+", " ", mondo).strip()
            mondo = _aggiungi_stato_movimento(mondo, corpo)

            # Se vedo solo un volto ignoto, non devo continuare a ragionare come se fosse Giulia.
            _sincronizza_nome_runtime_da_mondo(mondo)

            evento_fisico_sensibile = (
                u"Sento una carezza sulla testa" in mondo or
                u"Sento un tocco sulla mano" in mondo or
                u"URTO" in mondo or
                u"PERICOLO" in mondo or
                u"rischio di cadere" in mondo.lower() or
                u"cadere" in mondo.lower()
            )

            if stato_runtime["in_pattugliamento"] and evento_fisico_sensibile:
                logger.warning(u"[SAFETY] Evento fisico sensibile durante cammino: arresto immediato")

                mondo_evento = mondo

                if u"STO CAMMINANDO" not in mondo_evento:
                    mondo_evento += u" STO CAMMINANDO."

                stato_runtime["in_pattugliamento"] = False
                corpo.fermati()

                # Parla solo se questo evento safety non è già stato gestito nel ciclo precedente
                if mondo_evento != stato_precedente:
                    voce.parla(u"Mi fermo per sicurezza.")

                _tenta_generare_condizione_da_evento_safety(
                    mondo_evento,
                    u"evento fisico sensibile durante il cammino"
                )
                
                stato_precedente = mondo_evento
                time.sleep(0.2)
                continue

            if input_ricevuto and messaggio_utente:
                mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
                messaggio_utente = ""
                input_ricevuto = False

            elif input_ricevuto:
                input_ricevuto = False

            if not stato_runtime["attesa_nome"]:
                mondo_valido = mondo.strip() != "REPORT: SONO FERMO."
                mondo_cambiato = mondo != stato_precedente

                if mondo_cambiato and mondo_valido:
                    logger.info(u"SENSORI: {}".format(testo_per_log(mondo)))

                # EVENTI COMPOSTI:
                # soul.py li riconosce solo per log/debug.
                # La decisione se generare una condizione composta appartiene
                # al supervisore autonomo.
                evento_composto = (
                    mondo_cambiato and
                    mondo_valido and
                    _mondo_ha_eventi_multipli(mondo)
                )

                if evento_composto:
                    safety_recente = (
                        time.time() - stato_runtime.get("ultimo_evento_fisico_gestito_tempo", 0) < 2.5
                    )

                    evento_ancora_safety = (
                        u"URTO" in mondo or
                        u"PERICOLO" in mondo or
                        u"Ostacolo frontale ai piedi" in mondo or
                        u"Piede sinistro premuto" in mondo or
                        u"Piede destro premuto" in mondo
                    )

                    evento_sociale_tattile = (
                        u"Sento una carezza" in mondo or
                        u"Sento un tocco sulla mano" in mondo or
                        u"Sento un tocco su entrambe le mani" in mondo
                    )

                    if safety_recente and evento_ancora_safety and not evento_sociale_tattile:
                        logger.info(u"[SOUL] Evento composto ignorato: safety appena gestita")
                        stato_precedente = mondo
                        time.sleep(0.1)
                        continue

                    logger.info(u"[SOUL] Evento composto rilevato: delego al supervisore autonomo")

                # Gestione volto.
                # Resta dopo il rilevamento dell'evento composto,
                # ma NON deve stare dentro if evento_composto.
                if mondo_cambiato and mondo_valido:
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

                decisione_condizione = None

                if mondo_cambiato and mondo_valido:
                    stato_runtime["eventi"] = estrai_eventi(mondo, stato_runtime)
                    stato_runtime["memoria"] = memoria_fisica
                    stato_runtime["stato_robot"] = stato_robot
                    stato_runtime["openai_api_key"] = CHIAVE_PRIVATA
                    stato_runtime["evento_composto"] = evento_composto

                    salta_autonomia_per_vai = (
                        stato_runtime.get("in_pattugliamento", False) and
                        time.time() - stato_runtime.get("ultimo_comando_vai_tempo", 0) < 2.0
                    )

                    if salta_autonomia_per_vai:
                        logger.info(u"[SOUL] Salto autonomia per avvio pattugliamento appena richiesto")
                    else:
                        decisione_condizione = autonomy_supervisor.gestisci_autonomia(
                            mondo,
                            stato_runtime
                        )

                if decisione_condizione:
                    logger.info(u"[SOUL] Uso decisione del supervisore autonomo")

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
                    ultimo_evento_tempo = time.time()

                if not decisione_condizione and mondo_cambiato and mondo_valido:
                    # Nessuna condizione autonoma applicabile/generata dal supervisore:
                    # uso il normale comportamento LLM, ma NON genero qui nuove condizioni.
                    # La generazione autonoma ordinaria deve rimanere centralizzata in
                    # behaviors/autonomy_supervisor.py, per evitare doppioni e chiamate LLM duplicate.
                    ultima_decisione = _elabora_decisione(
                        mondo,
                        corpo,
                        voce,
                        vista,
                        sistema
                    )

                    ultimo_evento_tempo = time.time()

                    # Se era gia' un evento composto, la generazione e' gia' stata tentata sopra.
                    # Qui generiamo solo condizioni semplici normali.
                    if not evento_composto:
                        if valuta_se_generare_condizione(
                            mondo,
                            ultima_decisione,
                            memoria_fisica,
                            stato_robot,
                            CHIAVE_PRIVATA
                        ):
                            logger.info(u"[SOUL] LLM ha deciso di creare una nuova condizione autonoma")

                            nuova_condizione = genera_condizione_autonoma(
                                mondo,
                                memoria_fisica,
                                stato_robot,
                                CHIAVE_PRIVATA
                            )

                            if nuova_condizione:
                                logger.info(u"[SOUL] Nuova condizione autonoma creata: {}".format(
                                    nuova_condizione
                                ))

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