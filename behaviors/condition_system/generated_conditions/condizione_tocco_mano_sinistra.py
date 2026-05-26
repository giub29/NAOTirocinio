# -*- coding: utf-8 -*-

def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("mano_sinistra", False)


def comportamento():
    return {
        "stato_interno": "curioso",
        "obiettivo": "rispondere al tocco",
        "azioni": [
            {"tipo": "occhi", "colore": "green"},
            {"tipo": "guarda", "x": 0.5, "y": -0.2},
            {"tipo": "parla", "testo": "Ho sentito un tocco sulla mano sinistra."}
        ],
        "memoria": []
    }