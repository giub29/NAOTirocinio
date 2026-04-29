# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    if u"PRENDI L'INIZIATIVA" in mondo:
        return False

    if u"Sento una carezza" in mondo:
        return False

    if u"Riconosco" in mondo or u"Vedo un volto ignoto" in mondo:
        return False

    return u"C'è qualcosa a sinistra" in mondo and u"SONO FERMO" in mondo


def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "gestire ostacolo sinistro appreso",
        "azioni": [
            {"tipo": "guarda", "x": -0.2, "y": 0.0},
            {"tipo": "occhi", "colore": "yellow"},
            {"tipo": "parla", "testo": "Ho riconosciuto una condizione appresa: qualcosa a sinistra."}
        ],
        "memoria": []
    }