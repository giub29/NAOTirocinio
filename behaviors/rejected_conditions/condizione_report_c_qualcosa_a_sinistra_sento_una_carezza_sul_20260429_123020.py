# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    return u"carezza" in mondo

def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "interagire con la persona",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.0, "y": -0.25},
            {"tipo": "animazione", "path": "animations/Stand/Gestures/Hey_1"},
            {"tipo": "parla", "testo": "Ehi! Grazie per la carezza!"}
        ],
        "memoria": []
        
    }