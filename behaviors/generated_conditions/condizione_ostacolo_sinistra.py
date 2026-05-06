# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("ostacolo_sinistra", False)


def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "osservare l'oggetto a sinistra",
        "azioni": [
            {"tipo": "occhi", "colore": "yellow"},
            {"tipo": "guarda", "x": -0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Cosa c'è a sinistra?"}
        ],
        "memoria": []
    }