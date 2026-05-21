# -*- coding: utf-8 -*-
"""
Memoria generale per eventi sconosciuti.

Scopo:
- non decidere a mano quali oggetti/eventi sono importanti;
- osservare eventi nuovi nel tempo;
- renderli generabili solo se diventano ricorrenti o significativi.
"""

import os
import json
import time

BASE_DIR = os.path.dirname(__file__)
MEMORY_PATH = os.path.join(BASE_DIR, "event_novelty_memory.json")

SOGLIA_OCCORRENZE_GENERAZIONE = 2


def _leggi_memoria():
    if not os.path.exists(MEMORY_PATH):
        return {}

    try:
        with open(MEMORY_PATH, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except Exception:
        return {}


def _scrivi_memoria(memoria):
    try:
        with open(MEMORY_PATH, "wb") as f:
            f.write(json.dumps(
                memoria,
                indent=2,
                ensure_ascii=False,
                sort_keys=True
            ).encode("utf-8"))
    except Exception:
        pass


def registra_evento_sconosciuto(nome_evento, mondo=None):
    """
    Registra un evento sconosciuto osservato.

    Ritorna:
    {
        "evento": nome_evento,
        "visto": numero_occorrenze,
        "generabile": True/False
    }
    """

    memoria = _leggi_memoria()
    adesso = int(time.time())

    if nome_evento not in memoria:
        memoria[nome_evento] = {
            "visto": 0,
            "prima_volta": adesso,
            "ultima_volta": adesso,
            "esempi": [],
            "generato": False
        }

    record = memoria[nome_evento]
    record["visto"] = int(record.get("visto", 0)) + 1
    record["ultima_volta"] = adesso

    esempi = record.get("esempi", [])

    if mondo and mondo not in esempi:
        esempi.append(mondo)

    record["esempi"] = esempi[-3:]

    generabile = (
        record["visto"] >= SOGLIA_OCCORRENZE_GENERAZIONE
        and not record.get("generato", False)
    )

    memoria[nome_evento] = record
    _scrivi_memoria(memoria)

    return {
        "evento": nome_evento,
        "visto": record["visto"],
        "generabile": generabile
    }


def marca_evento_generato(nome_evento):
    memoria = _leggi_memoria()

    if nome_evento in memoria:
        memoria[nome_evento]["generato"] = True
        _scrivi_memoria(memoria)


def stato_evento(nome_evento):
    memoria = _leggi_memoria()
    return memoria.get(nome_evento, {})