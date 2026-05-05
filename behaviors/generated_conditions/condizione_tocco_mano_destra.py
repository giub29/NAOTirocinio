# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return u"mano destra" in testo


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "interagire con l'utente",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.0, "y": -0.2},
            {"tipo": "parla", "testo": "Ciao! Come posso aiutarti?"},
            {"tipo": "animazione", "path": "animations/Stand/Gestures/Hey_1"}
        ],
        "memoria": []
    }