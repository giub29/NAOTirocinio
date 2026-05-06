# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("entrambe_mani", False) or (eventi.get("mano_sinistra", False) and eventi.get("mano_destra", False))


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "esplorare la fonte del tocco",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.0, "y": -0.2},
            {"tipo": "parla", "testo": "Chi sei?"},
            {"tipo": "fermati"}
        ],
        "memoria": []
    }