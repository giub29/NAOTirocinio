# -*- coding: utf-8 -*-
"""
Comportamenti di gestione dei volti - riconoscimento e apprendimento.
"""
import time
import re
import logging

logger = logging.getLogger(__name__)

TEMPO_STABILITA_VOLTO = 2.0
TEMPO_ATTESA_VOLTO_NOTO = 5.0
TEMPO_SLEEP_RICONOSCIMENTO = 1.5
TEMPO_SLEEP_FOTO = 1.0
LUNGHEZZA_MIN_NOME = 2

MSG_RICONOSCIMENTO = u"Ciao {}, ti ho riconosciuto."
MSG_NO_RICONOSCIMENTO = u"Non ti conosco. Ho scattato una foto. Come ti chiami?"
MSG_CONTINUO = u"Va bene, continuo."
MSG_ATTENDI_NOME = u"Sto aspettando un nome. Scrivi per esempio: nome Giulia."
MSG_NOME_CORTO = u"Il nome è troppo corto. Riprova."
MSG_MEMORIZZATO = u"Ti ho memorizzato, {}!"
MSG_MEMORIA_FALLITA = u"Non sono riuscito a memorizzarti bene."
MSG_ANNULLO = u"Va bene, annullo il riconoscimento e mi fermo."
MSG_NOME_PIACERE = u"Piacere {}."

ANGOLO_SGUARDO_VOLTO = (0.0, -0.45)
ANGOLO_SGUARDO_LEGGERO = (0.0, -0.1)


def _estrai_nome_riconosciuto(mondo):
    match = re.search(u"Riconosco ([^\.]+)\.", mondo)
    return match.group(1) if match else None


def _saluta_volto_conosciuto(nome, corpo, voce, stato_runtime):
    if nome not in stato_runtime["volti_salutati"]:
        corpo.imposta_colore_occhi("green")
        voce.parla(MSG_RICONOSCIMENTO.format(nome))
        stato_runtime["volti_salutati"].append(nome)
        logger.info(u"Volto riconosciuto: {}".format(nome))


def _gestisci_volto_ignoto_durante_movimento(corpo, stato_runtime):
    if corpo.sta_camminando() or stato_runtime["in_pattugliamento"]:
        logger.info(u"Volto ignoto durante movimento, fermo il robot")
        corpo.fermati()
        stato_runtime["in_pattugliamento"] = True
        stato_runtime["riprendi_dopo_nome"] = True
        corpo.guarda(*ANGOLO_SGUARDO_VOLTO)
        time.sleep(TEMPO_SLEEP_RICONOSCIMENTO)
        return True

    return False


def _gestisci_falso_ignoto(stato_runtime):
    if (
        stato_runtime["ultimo_nome_riconosciuto"] != "" and
        time.time() - stato_runtime["ultimo_volto_noto_tempo"] < TEMPO_ATTESA_VOLTO_NOTO
    ):
        logger.debug(u"Falso ignoto, probabilmente ancora {}".format(
            stato_runtime["ultimo_nome_riconosciuto"]
        ))
        return True

    return False


def _attendi_stabilita_volto(stato_runtime):
    if stato_runtime["primo_ignoto_tempo"] == 0:
        stato_runtime["primo_ignoto_tempo"] = time.time()
        logger.debug(u"Volto ignoto rilevato, attendo stabilità")
        return False

    if time.time() - stato_runtime["primo_ignoto_tempo"] < TEMPO_STABILITA_VOLTO:
        logger.debug(u"Volto ignoto ancora instabile")
        return False

    stato_runtime["primo_ignoto_tempo"] = 0
    return True


def _chiedi_nome_volto_ignoto(corpo, voce, stato_runtime):
    corpo.imposta_colore_occhi("red")

    stava_camminando = corpo.sta_camminando() or stato_runtime["in_pattugliamento"]
    stato_runtime["riprendi_dopo_nome"] = stava_camminando

    if stava_camminando:
        stato_runtime["in_pattugliamento"] = False
        corpo.fermati()
        time.sleep(1.0)

    corpo.guarda(*ANGOLO_SGUARDO_VOLTO)
    time.sleep(TEMPO_SLEEP_FOTO)

    corpo.scatta_foto(camera_id=0, nome_file="sconosciuto.jpg")
    voce.parla(MSG_NO_RICONOSCIMENTO)

    logger.info(u"Richiesta del nome per volto ignoto")
    stato_runtime["attesa_nome"] = True


def gestisci_volto_durante_cammino(mondo, corpo, voce, vista, stato_runtime):
    nome = _estrai_nome_riconosciuto(mondo)

    if nome:
        stato_runtime["ultimo_volto_noto_tempo"] = time.time()
        stato_runtime["ultimo_nome_riconosciuto"] = nome

        if stato_runtime["attesa_nome"]:
            stato_runtime["attesa_nome"] = False
            stato_runtime["riprendi_dopo_nome"] = False

        _saluta_volto_conosciuto(nome, corpo, voce, stato_runtime)
        return True

    if u"Vedo un volto ignoto" in mondo:
        if _gestisci_volto_ignoto_durante_movimento(corpo, stato_runtime):
            return True

        if _gestisci_falso_ignoto(stato_runtime):
            return True

        if not _attendi_stabilita_volto(stato_runtime):
            return True

        if stato_runtime["attesa_nome"]:
            return True

        _chiedi_nome_volto_ignoto(corpo, voce, stato_runtime)
        return True

    return False


def _ripresa_cammino(corpo, stato_runtime, velocita_cammino=0.3):
    if stato_runtime["riprendi_dopo_nome"]:
        stato_runtime["riprendi_dopo_nome"] = False
        stato_runtime["in_pattugliamento"] = True
        time.sleep(0.5)
        corpo.cammina(velocita_cammino, 0.0)


def _ferma_riconoscimento(stato_runtime, mantieni_ripresa=False):
    stato_runtime["attesa_nome"] = False

    if not mantieni_ripresa:
        stato_runtime["riprendi_dopo_nome"] = False

    stato_runtime["in_pattugliamento"] = False


def _valida_lunghezza_nome(nome):
    if len(nome) < LUNGHEZZA_MIN_NOME:
        logger.warning(u"Nome troppo corto: '{}'".format(nome))
        return False

    return True


def _estrai_nome_da_input(testo):
    testo_lower = testo.lower()

    if testo_lower.startswith("nome "):
        return testo[5:].strip()

    elif testo_lower.startswith("mi chiamo "):
        return testo[10:].strip()

    else:
        return testo.strip()


def _apprendi_e_registra_volto(nome, corpo, voce, vista, stato_runtime):
    corpo.imposta_colore_occhi("yellow")
    voce.parla(MSG_NOME_PIACERE.format(nome))

    corpo.guarda(*ANGOLO_SGUARDO_LEGGERO)
    time.sleep(1.0)

    riuscito = vista.apprendi_volto(str(nome))

    if riuscito:
        voce.parla(MSG_MEMORIZZATO.format(nome))
        corpo.imposta_colore_occhi("green")
        stato_runtime["volti_salutati"].append(nome)
        logger.info(u"Volto appreso con successo: {}".format(nome))

    else:
        voce.parla(MSG_MEMORIA_FALLITA)
        corpo.imposta_colore_occhi("red")
        logger.warning(u"Fallimento nell'apprendimento del volto: {}".format(nome))

    return riuscito


def gestisci_input_nome(corpo, voce, vista, stato_runtime, messaggio_utente, velocita_cammino=0.3):
    testo = messaggio_utente.strip()
    testo_lower = testo.lower()

    if testo == "":
        voce.parla(MSG_CONTINUO)

        deve_riprendere = stato_runtime["riprendi_dopo_nome"]
        _ferma_riconoscimento(stato_runtime, mantieni_ripresa=deve_riprendere)

        if deve_riprendere:
            _ripresa_cammino(corpo, stato_runtime, velocita_cammino)
        else:
            corpo.fermati()

        return True

    if testo_lower in ["fermati", "stop", "basta", "annulla"]:
        _ferma_riconoscimento(stato_runtime)
        corpo.fermati()
        voce.parla(MSG_ANNULLO)
        logger.info(u"Riconoscimento annullato dall'utente")
        return True

    if testo_lower in ["vai", "cammina", "va", "i"] or "vai" in testo_lower:
        voce.parla(MSG_ATTENDI_NOME)
        return True

    nome = _estrai_nome_da_input(testo)

    if not _valida_lunghezza_nome(nome):
        voce.parla(MSG_NOME_CORTO)
        return True

    _apprendi_e_registra_volto(nome, corpo, voce, vista, stato_runtime)

    deve_riprendere = stato_runtime["riprendi_dopo_nome"]
    _ferma_riconoscimento(stato_runtime, mantieni_ripresa=deve_riprendere)

    if deve_riprendere:
        _ripresa_cammino(corpo, stato_runtime, velocita_cammino)
    else:
        corpo.fermati()

    return True