# -*- coding: utf-8 -*-

def crea_stato_agentico(mondo, stato_runtime=None):
    if stato_runtime is None:
        stato_runtime = {}

    return {
        "mondo": mondo,
        "stato_runtime": stato_runtime,
        "firma": None,
        "decisione": None,
        "motivo": None,
        "errore": None,
        "step": []
    }