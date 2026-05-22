# -*- coding: utf-8 -*-
"""
Memoria delle condizioni autonome generate da NAO.

Questo modulo crea e aggiorna file .meta.json separati dal codice Python
delle condizioni. I metadati vengono salvati in condition_metadata/
per mantenere distinta la memoria semantica dal codice eseguibile.
"""

import os
import json
import time
import codecs
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
METADATA_DIR = os.path.join(BASE_DIR, "condition_metadata")
REJECTED_METADATA_DIR = os.path.join(BASE_DIR, "rejected_metadata")
GENERATED_DIR = os.path.join(BASE_DIR, "generated_conditions")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected_conditions")


def _assicura_cartelle():
    for cartella in [
        GENERATED_DIR,
        REJECTED_DIR,
        METADATA_DIR,
        REJECTED_METADATA_DIR
    ]:
        if not os.path.exists(cartella):
            os.makedirs(cartella)


def _meta_path(nome_condizione, cartella=None):
    """
    Ritorna il path del file metadati per una condizione.

    nome_condizione può essere:
    - condizione_ostacolo_destra
    - condizione_ostacolo_destra.py
    """

    _assicura_cartelle()

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    if cartella is None:
        cartella = METADATA_DIR

    return os.path.join(cartella, nome_condizione + ".meta.json")


def _adesso():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _leggi_json(path_file):
    if not os.path.exists(path_file):
        return None

    try:
        with codecs.open(path_file, "r", "utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(u"[COND_MEMORY] Errore lettura metadati {}: {}".format(
            path_file,
            e
        ))
        return None


def _scrivi_json(path_file, dati):
    try:
        with codecs.open(path_file, "w", "utf-8") as f:
            json.dump(
                dati,
                f,
                ensure_ascii=False,
                indent=2,
                sort_keys=True
            )
        return True

    except Exception as e:
        logger.warning(u"[COND_MEMORY] Errore scrittura metadati {}: {}".format(
            path_file,
            e
        ))
        return False


def crea_metadati_base(nome_condizione, mondo, eventi, stato_robot=None, origine="autogenerata"):
    """
    Crea la struttura standard dei metadati per una condizione autonoma.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    if eventi is None:
        eventi = {}

    if stato_robot is None:
        stato_robot = {}

    eventi_attivi = []

    try:
        for chiave, valore in eventi.items():
            if valore is True:
                eventi_attivi.append(chiave)
    except Exception:
        eventi_attivi = []

    metadati = {
        "nome": nome_condizione,
        "file_python": nome_condizione + ".py",
        "origine": origine,
        "stato": "promossa",

        "creata_il": _adesso(),
        "aggiornata_il": _adesso(),

        "mondo_origine": mondo,
        "eventi_attivi_origine": eventi_attivi,
        "eventi_completi_origine": eventi,

        "stato_robot_origine": stato_robot,

        "statistiche": {
            "attivazioni": 0,
            "errori_runtime": 0,
            "rifiuti": 0,
            "ultima_attivazione": "",
            "ultimo_errore": ""
        },

        "validazione": {
            "struttura": "ok",
            "modulo": "ok",
            "semantica": "ok"
        },

        "riparazione": {
            "tentativi": 0,
            "successi": 0,
            "fallimenti": 0,
            "ultimo_esito": "",
            "ultimo_motivo": ""
        },

        "note": [
            "Condizione generata autonomamente da NAO.",
            "Il file Python contiene la logica eseguibile.",
            "Questo JSON contiene la memoria e la tracciabilità della condizione."
        ]
    }

    return metadati


def salva_metadati_condizione(nome_condizione, mondo, eventi, stato_robot=None, origine="autogenerata"):
    """
    Salva il file .meta.json accanto alla condizione generata.
    """

    _assicura_cartelle()

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)

    metadati = crea_metadati_base(
        nome_condizione,
        mondo,
        eventi,
        stato_robot,
        origine
    )

    ok = _scrivi_json(path_file, metadati)

    if ok:
        logger.info(u"[COND_MEMORY] Metadati creati per {}".format(nome_condizione))

    return ok


def leggi_metadati_condizione(nome_condizione):
    """
    Legge i metadati di una condizione generata.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    return _leggi_json(path_file)


def aggiorna_metadati_condizione(nome_condizione, aggiornamenti):
    """
    Aggiorna parzialmente i metadati di una condizione.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)

    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "attiva",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            },
            "note": []
        }

    for chiave, valore in aggiornamenti.items():
        dati[chiave] = valore

    dati["aggiornata_il"] = _adesso()

    return _scrivi_json(path_file, dati)


def registra_attivazione(nome_condizione, mondo=None, decisione=None):
    """
    Registra che una condizione è stata attivata con successo.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "attiva",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            },
            "attivazioni_recenti": []
        }

    if "statistiche" not in dati:
        dati["statistiche"] = {}

    dati["statistiche"]["attivazioni"] = dati["statistiche"].get("attivazioni", 0) + 1
    dati["statistiche"]["ultima_attivazione"] = _adesso()
    dati["aggiornata_il"] = _adesso()

    if "attivazioni_recenti" not in dati:
        dati["attivazioni_recenti"] = []

    dati["attivazioni_recenti"].append({
        "tempo": _adesso(),
        "mondo": mondo or "",
        "decisione": decisione or {}
    })

    dati["attivazioni_recenti"] = dati["attivazioni_recenti"][-5:]

    return _scrivi_json(path_file, dati)


def registra_errore_condizione(nome_condizione, errore):
    """
    Registra un errore runtime associato a una condizione.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "problematica",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            },
            "errori_recenti": []
        }

    if "statistiche" not in dati:
        dati["statistiche"] = {}

    dati["statistiche"]["errori_runtime"] = dati["statistiche"].get("errori_runtime", 0) + 1
    dati["statistiche"]["ultimo_errore"] = str(errore)
    dati["aggiornata_il"] = _adesso()

    if "errori_recenti" not in dati:
        dati["errori_recenti"] = []

    dati["errori_recenti"].append({
        "tempo": _adesso(),
        "errore": str(errore)
    })

    dati["errori_recenti"] = dati["errori_recenti"][-5:]

    return _scrivi_json(path_file, dati)


def marca_condizione_rifiutata(nome_condizione, motivo):
    """
    Marca nei metadati che una condizione è stata rifiutata o spostata.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "creata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            }
        }

    dati["stato"] = "rifiutata"
    dati["motivo_rifiuto"] = str(motivo)
    dati["aggiornata_il"] = _adesso()

    if "statistiche" not in dati:
        dati["statistiche"] = {}

    dati["statistiche"]["rifiuti"] = dati["statistiche"].get("rifiuti", 0) + 1

    return _scrivi_json(path_file, dati)

def valuta_affidabilita_condizione(nome_condizione):
    """
    Valuta se una condizione deve essere mantenuta, rigenerata o disattivata
    usando i suoi metadati.
    """

    dati = leggi_metadati_condizione(nome_condizione)

    if dati is None:
        return {
            "azione": "mantieni",
            "motivo": "metadati assenti, mantengo per prudenza"
        }

    statistiche = dati.get("statistiche", {})

    attivazioni = statistiche.get("attivazioni", 0)
    errori = statistiche.get("errori_runtime", 0)
    rifiuti = statistiche.get("rifiuti", 0)

    if rifiuti >= 2:
        return {
            "azione": "disattiva",
            "motivo": "troppi rifiuti registrati"
        }

    if errori >= 3:
        return {
            "azione": "rigenera",
            "motivo": "troppi errori runtime"
        }

    if attivazioni >= 3 and errori == 0 and rifiuti == 0:
        return {
            "azione": "mantieni",
            "motivo": "condizione affidabile"
        }

    return {
        "azione": "mantieni",
        "motivo": "nessun segnale critico"
    }

def registra_esito_riparazione(nome_condizione, esito):
    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "problematica",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso()
        }

    if "riparazione" not in dati:
        dati["riparazione"] = {
            "tentativi": 0,
            "successi": 0,
            "fallimenti": 0,
            "ultimo_esito": "",
            "ultimo_motivo": ""
        }

    dati["riparazione"]["tentativi"] += 1
    dati["riparazione"]["ultimo_esito"] = esito.get("status", "")
    dati["riparazione"]["ultimo_motivo"] = esito.get("reason", "")

    if esito.get("success"):
        dati["riparazione"]["successi"] += 1
    else:
        dati["riparazione"]["fallimenti"] += 1

    dati["aggiornata_il"] = _adesso()

    return _scrivi_json(path_file, dati)