# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("mano_sinistra", False)


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "esplorare l'interazione",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Ciao! Come posso aiutarti?"},
            {"tipo": "animazione", "path": "animations/Stand/Gestures/Hey_1"}
        ],
        "memoria": []
    }