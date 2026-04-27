# -*- coding: utf-8 -*-
import re
from core.goal_manager import determina_obiettivo


def crea_stato_robot():
    return {
        "modalita": "idle",
        "umore": "neutro",
        "energia": 100,
        "sta_camminando": False,
        "persona_attuale": None,
        "ultimo_evento": "",
        "livello_allerta": 0,
        "obiettivo_corrente": "esplorare"
    }


def aggiorna_stato_robot(stato_robot, mondo, corpo, in_pattugliamento, ultimo_nome_riconosciuto):
    stato_robot["sta_camminando"] = corpo.sta_camminando() or in_pattugliamento

    if stato_robot["sta_camminando"]:
        stato_robot["modalita"] = "esplorazione"
    else:
        stato_robot["modalita"] = "osservazione"

    match_bat = re.search(ur'La mia batteria.*?(\d+)%', mondo)
    if match_bat:
        stato_robot["energia"] = int(match_bat.group(1))

    if u"PERICOLO CADUTA" in mondo:
        stato_robot["umore"] = "allerta"
        stato_robot["livello_allerta"] = 3
        stato_robot["ultimo_evento"] = "pericolo caduta"

    elif u"URTO" in mondo:
        stato_robot["umore"] = "allerta"
        stato_robot["livello_allerta"] = 2
        stato_robot["ultimo_evento"] = "urto rilevato"

    elif u"Ostacolo" in mondo or u"Vedo qualcosa" in mondo or u"C'è qualcosa" in mondo:
        stato_robot["umore"] = "prudente"
        stato_robot["livello_allerta"] = 1
        stato_robot["ultimo_evento"] = "ostacolo rilevato"

    elif u"Riconosco" in mondo:
        stato_robot["umore"] = "sociale"
        stato_robot["livello_allerta"] = 0
        stato_robot["persona_attuale"] = ultimo_nome_riconosciuto
        stato_robot["ultimo_evento"] = "persona riconosciuta"

    elif u"Vedo un volto ignoto" in mondo:
        stato_robot["umore"] = "curioso"
        stato_robot["livello_allerta"] = 0
        stato_robot["ultimo_evento"] = "volto ignoto"

    else:
        stato_robot["umore"] = "neutro"
        stato_robot["livello_allerta"] = 0

    stato_robot["obiettivo_corrente"] = determina_obiettivo(mondo)

    return stato_robot