# -*- coding: utf-8 -*-


def determina_obiettivo(mondo):
    if u"PERICOLO CADUTA" in mondo:
        return "evitare caduta"

    if u"URTO" in mondo:
        return "gestire urto"

    if u"Ostacolo" in mondo:
        return "evitare ostacolo"

    if u"Riconosco" in mondo:
        return "interagire con persona"

    if u"Vedo un volto ignoto" in mondo:
        return "identificare persona"

    if u"L'utente dice" in mondo:
        return "seguire comando utente"

    return "esplorare"