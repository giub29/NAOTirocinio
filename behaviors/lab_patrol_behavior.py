# -*- coding: utf-8 -*-

import time
import logging

logger = logging.getLogger(__name__)

COOLDOWN_SCHIVATA = 1.5
MAX_TENTATIVI_BLOCCO = 3


def gestisci_navigazione_laboratorio(mondo, corpo, voce, vista, stato_runtime):
    """
    Gestisce la navigazione autonoma del laboratorio.

    Obiettivo:
    - continuare il pattugliamento;
    - schivare ostacoli invece di fermarsi subito;
    - fermarsi solo se il robot è bloccato o in pericolo reale.
    """

    eventi = stato_runtime.get("eventi", {})
    evento = stato_runtime.get("evento_strutturato", {})

    if not stato_runtime.get("in_pattugliamento", False):
        return False

    adesso = time.time()
    ultimo = stato_runtime.get("ultimo_tentativo_schivata_tempo", 0)

    if adesso - ultimo < COOLDOWN_SCHIVATA:
        return False

    tipo = evento.get("tipo", "")
    direzione = evento.get("direzione", "")
    categoria = evento.get("categoria", "")
    gravita = evento.get("gravita", "bassa")

    if categoria == "safety" and gravita == "alta":
        tentativi = stato_runtime.get("tentativi_blocco", 0) + 1
        stato_runtime["tentativi_blocco"] = tentativi

        if tentativi >= MAX_TENTATIVI_BLOCCO:
            corpo.fermati()
            corpo.imposta_colore_occhi("red")
            voce.parla(u"Non trovo una strada libera. Mi fermo.")
            stato_runtime["in_pattugliamento"] = False
            logger.warning(u"[LAB] Robot bloccato: arresto dopo troppi tentativi")
            return True

        corpo.fermati()
        time.sleep(0.2)
        corpo.cammina(-0.08, 0.0)
        time.sleep(0.6)
        corpo.cammina(0.12, 0.18)
        corpo.imposta_colore_occhi("yellow")
        voce.parla(u"Ho sentito un contatto. Provo a liberare la strada.")
        stato_runtime["ultimo_tentativo_schivata_tempo"] = adesso
        return True

    if tipo == "ostacolo":
        stato_runtime["tentativi_blocco"] = 0

        corpo.imposta_colore_occhi("yellow")

        if direzione == "destra":
            corpo.guarda(0.4, -0.25)
            corpo.cammina(0.16, 0.12)
            voce.parla(u"Schivo l'ostacolo a destra.")
            stato_runtime["ultimo_tentativo_schivata_tempo"] = adesso
            return True

        if direzione == "sinistra":
            corpo.guarda(-0.4, -0.25)
            corpo.cammina(0.16, -0.12)
            voce.parla(u"Schivo l'ostacolo a sinistra.")
            stato_runtime["ultimo_tentativo_schivata_tempo"] = adesso
            return True

        if direzione == "frontale":
            corpo.guarda(0.0, -0.25)
            corpo.cammina(0.12, 0.18)
            voce.parla(u"Schivo l'ostacolo davanti.")
            stato_runtime["ultimo_tentativo_schivata_tempo"] = adesso
            return True

    return False