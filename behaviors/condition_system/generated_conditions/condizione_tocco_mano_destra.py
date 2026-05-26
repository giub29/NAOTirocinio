# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"mano destra" in testo


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "esplorare l'interazione",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": -0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Ciao! Cosa stai facendo?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }