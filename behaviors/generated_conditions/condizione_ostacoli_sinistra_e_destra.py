# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("ostacolo_sinistra", False) and eventi.get("ostacolo_destra", False)


def comportamento():
    return {
        "stato_interno": "prudente",
        "obiettivo": "osservare l'ambiente circostante",
        "azioni": [
            {"tipo": "occhi", "colore": "yellow"},
            {"tipo": "guarda", "x": -0.5, "y": -0.2},
            {"tipo": "parla", "testo": "C'è qualcosa qui intorno."},
            {"tipo": "guarda", "x": 0.5, "y": -0.2}
        ],
        "memoria": []
    }