# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    return u"carezza" in mondo

def comportamento():
    return {
        "stato_interno": "sociale",
        "obiettivo": "rispondere alla carezza",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.0, "y": -0.2},
            {"tipo": "parla", "testo": "Grazie per la carezza!"},
            {"tipo": "animazione", "path": "animations/Stand/Gestures/Hey_1"}
        ],
        "memoria": []
    }