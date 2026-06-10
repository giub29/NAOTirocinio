# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("informazione_visiva_rilevante", False)


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "osservare il monitor e il codice",
        "azioni": [
            {"tipo": "occhi", "colore": "cyan"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Che interessante codice!"},
            {"tipo": "animazione", "path": "animations/Stand/Gestures/Hey_1"}
        ],
        "memoria": []
    }