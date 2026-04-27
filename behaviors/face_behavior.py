# -*- coding: utf-8 -*-
import time
import re


def gestisci_volto_durante_cammino(mondo, corpo, voce, vista, stato_runtime):
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


def gestisci_input_nome(corpo, voce, vista, stato_runtime, messaggio_utente):
    testo = messaggio_utente.strip()
    testo_lower = testo.lower()

    if testo == "":
        voce.parla(u"Va bene, continuo.")

        stato_runtime["attesa_nome"] = False

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

        corpo.fermati()
        voce.parla(u"Va bene, annullo il riconoscimento e mi fermo.")

        return True

    if testo_lower in ["vai", "cammina", "va", "i"] or "vai" in testo_lower:
        voce.parla(u"Sto aspettando un nome. Scrivi per esempio: nome Giulia.")
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