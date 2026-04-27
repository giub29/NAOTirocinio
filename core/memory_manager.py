# -*- coding: utf-8 -*-
import json


def carica_memoria():
    try:
        with open('memoria.json', 'r') as f:
            return json.load(f)
    except:
        return {
            "nome_utente": "Sconosciuto",
            "fatti_importanti": {"batteria": 100},
            "ricordi_recenti": []
        }


def salva_memoria(dati):
    try:
        with open('memoria.json', 'w') as f:
            json.dump(dati, f, indent=4)
        return True
    except:
        return False