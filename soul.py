# -*- coding: utf-8 -*-
import json
import time
import threading
import os
import re

from hardware_control import NaoBody
from sensi import NaoSenses
from voice_interaction import NaoVoice
from vision_perception import NaoVision
from system_manager import NaoSystem

from core.memory_manager import carica_memoria, salva_memoria
from core.robot_state import crea_stato_robot, aggiorna_stato_robot

from behaviors.action_behavior import valida_decisione, esegui_decisione
from behaviors.safety_behavior import gestisci_emergenza, gestisci_ostacoli_durante_cammino
from behaviors.llm_behavior import genera_decisione_anima, analizza_immagine


IP_ROBOT = "172.16.165.86"
CHIAVE_PRIVATA = os.getenv("OPENAI_API_KEY", "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")

messaggio_utente = ""
input_ricevuto = False

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


def aggiorna_memoria_da_decisione(decisione):
    global memoria_fisica

    elementi = decisione.get("memoria", [])

    if not isinstance(elementi, list):
        return

    if "ricordi_recenti" not in memoria_fisica:
        memoria_fisica["ricordi_recenti"] = []

    if "fatti_importanti" not in memoria_fisica:
        memoria_fisica["fatti_importanti"] = {}

    for item in elementi:
        try:
            tipo = item.get("tipo", "ricordo")

            if tipo == "fatto_utente":
                chiave = item.get("chiave", "")
                valore = item.get("valore", "")

                if chiave and valore:
                    memoria_fisica["fatti_importanti"][chiave] = valore

            else:
                memoria_fisica["ricordi_recenti"].append({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "contenuto": item.get("contenuto", str(item))
                })

        except:
            pass

    memoria_fisica["ricordi_recenti"] = memoria_fisica["ricordi_recenti"][-20:]
    salva_memoria(memoria_fisica)


def gestisci_volto_durante_cammino(mondo, corpo, voce, vista):
    match = re.search(ur"Riconosco ([^\.]+)\.", mondo)

    if match:
        nome = match.group(1)

        stato_runtime["ultimo_volto_noto_tempo"] = time.time()
        stato_runtime["ultimo_nome_riconosciuto"] = nome

        if stato_runtime["attesa_nome"]:
            stato_runtime["attesa_nome"] = False
            stato_runtime["riprendi_dopo_nome"] = False

        if nome not in stato_runtime["volti_salutati"]:
            corpo.imposta_colore_occhi("green")
            voce.parla(u"Ciao {}, ti ho riconosciuto.".format(nome))
            stato_runtime["volti_salutati"].append(nome)

        return True

    if u"Vedo un volto ignoto" in mondo:

        if corpo.sta_camminando() or stato_runtime["in_pattugliamento"]:
            print(u"[VOLTO]: ignoto durante cammino, mi fermo per verificare.")
            corpo.fermati()
            stato_runtime["in_pattugliamento"] = True
            stato_runtime["riprendi_dopo_nome"] = True
            corpo.guarda(0.0, -0.45)
            time.sleep(1.5)

            return True

        if (
            stato_runtime["ultimo_nome_riconosciuto"] != "" and
            time.time() - stato_runtime["ultimo_volto_noto_tempo"] < 5
        ):
            print(u"[VOLTO]: ignoro falso ignoto, probabilmente è ancora {}".format(
                stato_runtime["ultimo_nome_riconosciuto"]
            ))
            return True

        if stato_runtime["primo_ignoto_tempo"] == 0:
            stato_runtime["primo_ignoto_tempo"] = time.time()
            print(u"[VOLTO]: volto ignoto rilevato, attendo stabilità...")
            return True

        if time.time() - stato_runtime["primo_ignoto_tempo"] < 2.0:
            print(u"[VOLTO]: volto ignoto ancora instabile...")
            return True

        stato_runtime["primo_ignoto_tempo"] = 0

        if stato_runtime["attesa_nome"]:
            return True

        corpo.imposta_colore_occhi("red")

        stava_camminando = corpo.sta_camminando() or stato_runtime["in_pattugliamento"]
        stato_runtime["riprendi_dopo_nome"] = stava_camminando

        if stava_camminando:
            stato_runtime["in_pattugliamento"] = False
            corpo.fermati()
            time.sleep(1.0)

        corpo.guarda(0.0, -0.45)
        time.sleep(1.0)

        corpo.scatta_foto(camera_id=0, nome_file="sconosciuto.jpg")

        voce.parla(u"Non ti conosco. Ho scattato una foto. Come ti chiami?")
        print(u"\n--- INSERISCI IL NOME E PREMI INVIO ---")

        stato_runtime["attesa_nome"] = True

        return True

    return False


def gestisci_input_nome(corpo, voce, vista):
    global messaggio_utente, input_ricevuto

    testo = messaggio_utente.strip()
    testo_lower = testo.lower()
    input_ricevuto = False

    if testo == "":
        voce.parla(u"Va bene, continuo.")

        stato_runtime["attesa_nome"] = False
        messaggio_utente = ""

        if stato_runtime["riprendi_dopo_nome"]:
            stato_runtime["riprendi_dopo_nome"] = False
            stato_runtime["in_pattugliamento"] = True
            time.sleep(0.5)
            corpo.cammina(0.3, 0.0)
        else:
            stato_runtime["riprendi_dopo_nome"] = False
            stato_runtime["in_pattugliamento"] = False
            corpo.fermati()

        return True

    if testo_lower in ["fermati", "stop", "basta", "annulla"]:
        stato_runtime["attesa_nome"] = False
        stato_runtime["riprendi_dopo_nome"] = False
        stato_runtime["in_pattugliamento"] = False
        messaggio_utente = ""

        corpo.fermati()
        voce.parla(u"Va bene, annullo il riconoscimento e mi fermo.")

        return True

    if testo_lower in ["vai", "cammina", "va", "i"] or "vai" in testo_lower:
        voce.parla(u"Sto aspettando un nome. Scrivi per esempio: nome Giulia.")
        messaggio_utente = ""
        return True

    nome = ""

    if testo_lower.startswith("nome "):
        nome = testo[5:].strip()
    elif testo_lower.startswith("mi chiamo "):
        nome = testo[10:].strip()
    else:
        nome = testo.strip()

    if len(nome) < 2:
        voce.parla(u"Il nome è troppo corto. Riprova.")
        messaggio_utente = ""
        return True

    corpo.imposta_colore_occhi("yellow")
    voce.parla(u"Piacere {}.".format(nome))

    corpo.guarda(0.0, -0.1)
    time.sleep(1.0)

    riuscito = vista.apprendi_volto(str(nome))

    if riuscito:
        voce.parla(u"Ti ho memorizzato, {}!".format(nome))
        corpo.imposta_colore_occhi("green")
        stato_runtime["volti_salutati"].append(nome)
    else:
        voce.parla(u"Non sono riuscito a memorizzarti bene.")
        corpo.imposta_colore_occhi("red")

    stato_runtime["attesa_nome"] = False
    messaggio_utente = ""

    if stato_runtime["riprendi_dopo_nome"]:
        stato_runtime["riprendi_dopo_nome"] = False
        stato_runtime["in_pattugliamento"] = True
        time.sleep(0.5)
        corpo.cammina(0.3, 0.0)
    else:
        stato_runtime["riprendi_dopo_nome"] = False
        stato_runtime["in_pattugliamento"] = False
        corpo.fermati()

    return True


def main():
    global messaggio_utente, input_ricevuto
    global memoria_fisica, ultima_batteria_letta
    global stato_robot

    ultimo_evento_tempo = time.time()
    memoria_fisica = carica_memoria()
    corpo = None

    try:
        corpo = NaoBody(IP_ROBOT)
        sensi = NaoSenses(IP_ROBOT)
        voce = NaoVoice(IP_ROBOT)
        vista = NaoVision(IP_ROBOT)
        sistema = NaoSystem(IP_ROBOT)

        sistema.set_vita_autonoma(False)
        corpo.abilita_motori()
        corpo.vai_in_posa("Stand")
        vista.attiva_inseguimento_volto()

        def loop_input():
            global messaggio_utente, input_ricevuto

            while True:
                try:
                    t = raw_input()
                    messaggio_utente = t.decode('utf-8', 'ignore')
                    input_ricevuto = True

                except Exception:
                    pass

        threading.Thread(target=loop_input).start()

        print(u"--- ANIMA JSON SICURA PRONTA ---")
        voce.parla(u"Sistemi pronti. Ciao {}, io sono NAO.".format(
            memoria_fisica.get("nome_utente", "amico")
        ))

        stato_precedente = ""
        ultima_decisione = {"azioni": []}

        while True:
            mondo = sensi.ottieni_report_semantico()

            stato_robot = aggiorna_stato_robot(
                stato_robot,
                mondo,
                corpo,
                stato_runtime["in_pattugliamento"],
                stato_runtime["ultimo_nome_riconosciuto"]
            )

            if DEBUG_STATO:
                print(u"[STATO ROBOT]: " + json.dumps(stato_robot, ensure_ascii=False))
                print(u"[OBIETTIVO]: " + stato_robot.get("obiettivo_corrente", "nessuno"))

            if gestisci_emergenza(mondo, corpo, voce, stato_runtime):
                continue

            if gestisci_ostacoli_durante_cammino(mondo, corpo, stato_runtime):
                continue

            if stato_runtime["attesa_nome"] and input_ricevuto:
                gestisci_input_nome(corpo, voce, vista)
                continue

            if input_ricevuto and messaggio_utente:
                testo_user = messaggio_utente.lower()

                if "vai" in testo_user or "cammina" in testo_user:
                    stato_runtime["in_pattugliamento"] = True
                    corpo.guarda(0.0, -0.35)

                elif "stop" in testo_user or "fermati" in testo_user:
                    stato_runtime["in_pattugliamento"] = False
                    corpo.fermati()

            if not corpo.sta_camminando() and not stato_runtime["in_pattugliamento"]:
                mondo = mondo.replace(u"Ostacolo frontale molto vicino", u"Vedo qualcosa vicino")
                mondo = mondo.replace(u"Ostacolo a sinistra", u"C'è qualcosa a sinistra")
                mondo = mondo.replace(u"Ostacolo a destra", u"C'è qualcosa a destra")

            if "batteria" in mondo:
                match_bat = re.search(ur'La mia batteria.*?(\d+)%[.]?', mondo)

                if match_bat:
                    if ultima_batteria_letta == -1:
                        ultima_batteria_letta = int(match_bat.group(1))
                    else:
                        mondo = mondo.replace(match_bat.group(0), u"").strip()

            interazione_reale = (
                messaggio_utente != "" or
                u"Riconosco" in mondo or
                u"Vedo un volto ignoto" in mondo or
                u"carezza" in mondo or
                u"URTO" in mondo or
                u"PERICOLO" in mondo
            )

            if interazione_reale:
                ultimo_evento_tempo = time.time()

            else:
                tempo_di_inerzia = time.time() - ultimo_evento_tempo

                if not corpo.sta_camminando() and messaggio_utente == "" and tempo_di_inerzia > 30:
                    print(u"\n[INIZIATIVA]: NAO analizza la scena...")

                    corpo.imposta_colore_occhi("yellow")
                    corpo.guarda(0.0, -0.2)
                    time.sleep(1)

                    img_b64 = corpo.scatta_foto(camera_id=0, nome_file="curiosita.jpg")
                    desc = analizza_immagine(img_b64, CHIAVE_PRIVATA, contesto="stanza") if img_b64 else "una stanza tranquilla"

                    mondo += u" PRENDI L'INIZIATIVA. Vedi: {}. Usa la memoria e chiedi 'Cosa faresti tu?'.".format(desc)
                    ultimo_evento_tempo = time.time()

            for nome in stato_runtime["volti_salutati"]:
                mondo = re.sub(ur"Riconosco {}\.".format(nome), u"", mondo, flags=re.IGNORECASE)

            mondo = re.sub(r'\s+', ' ', mondo).strip()

            if corpo.sta_camminando() or stato_runtime["in_pattugliamento"]:
                mondo += u" STO CAMMINANDO."
            else:
                mondo += u" SONO FERMO."

            if input_ricevuto and messaggio_utente:
                mondo += u" L'utente dice: '{}'.".format(messaggio_utente)
                messaggio_utente = ""
                input_ricevuto = False
            elif input_ricevuto:
                input_ricevuto = False

            if not stato_runtime["attesa_nome"]:
                if mondo != stato_precedente and mondo.strip() != "REPORT: SONO FERMO.":
                    print(u"\n[SENSORI]: " + mondo)

                    if gestisci_volto_durante_cammino(mondo, corpo, voce, vista):
                        stato_precedente = mondo
                        time.sleep(0.1)
                        continue

                    decisione = genera_decisione_anima(
                        mondo,
                        memoria_fisica,
                        stato_robot,
                        CHIAVE_PRIVATA
                    )

                    decisione = valida_decisione(decisione, mondo)
                    ultima_decisione = decisione

                    ultimo_evento_tempo = time.time()

                    print(u"[STATO]: " + unicode(decisione.get("stato_interno", "neutro")))
                    print(u"[OBIETTIVO]: " + unicode(decisione.get("obiettivo", "")))
                    print(u"[AZIONI]: " + json.dumps(decisione.get("azioni", []), ensure_ascii=False))

                    esegui_decisione(
                        decisione,
                        corpo,
                        voce,
                        vista,
                        sistema,
                        stato_runtime,
                        aggiorna_memoria_callback=aggiorna_memoria_da_decisione
                    )

            if stato_runtime["in_pattugliamento"] and not corpo.sta_camminando():
                azioni_testo = json.dumps(ultima_decisione.get("azioni", []))

                if "cammina" not in azioni_testo and "gira" not in azioni_testo and "fermati" not in azioni_testo:
                    corpo.cammina(0.3, 0.0)

            stato_precedente = mondo
            time.sleep(0.1)

    except KeyboardInterrupt:
        pass

    finally:
        if corpo:
            corpo.fermati()
            corpo.disabilita_motori()


if __name__ == "__main__":
    main()