# -*- coding: utf-8 -*-
import os
import json


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FILE_MEMORIA = os.path.join(DATA_DIR, "memoria.json")


def _assicura_cartella_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def carica_memoria():
    try:
        _assicura_cartella_data()

        with open(FILE_MEMORIA, "r") as f:
            return json.load(f)

    except:
        return {
            "nome_utente": "Sconosciuto",
            "fatti_importanti": {"batteria": 100},
            "ricordi_recenti": []
        }


def salva_memoria(dati):
    try:
        _assicura_cartella_data()

        with open(FILE_MEMORIA, "w") as f:
            json.dump(dati, f, indent=4)

        return True

    except:
        return False