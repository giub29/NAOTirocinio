# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import json
import time
import re

try:
    basestring
except NameError:
    basestring = str


BASE_DIR = "/data/home/nao/NAOTirocinio"
DATA_DIR = "/data/home/nao/.nao_knowledge_memory"
MEMORY_PATH = os.path.join(DATA_DIR, "knowledge_memory.json")


def _testo(valore):
    try:
        if isinstance(valore, basestring):
            return valore.lower().strip()
        return str(valore or "").lower().strip()
    except Exception:
        return ""


def _normalizza(testo):
    testo = _testo(testo)
    testo = re.sub(r"[^a-z0-9àèéìòù\s_]", " ", testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    return testo


def _carica_memoria():
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except Exception:
            pass

    if not os.path.exists(MEMORY_PATH):
        return {"ipotesi": []}

    try:
        with open(MEMORY_PATH, "r") as f:
            dati = json.load(f)
        if not isinstance(dati, dict):
            return {"ipotesi": []}
        if "ipotesi" not in dati or not isinstance(dati["ipotesi"], list):
            dati["ipotesi"] = []
        return dati
    except Exception:
        return {"ipotesi": []}


def _salva_memoria(dati):
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except Exception:
            pass

    try:
        with open(MEMORY_PATH, "w") as f:
            json.dump(dati, f, indent=2, sort_keys=True)
        return True
    except Exception:
        return False


def _firma(concetto, evidenze):
    parole = [_normalizza(concetto)]

    if isinstance(evidenze, list):
        for e in evidenze:
            t = _normalizza(e)
            if t and t not in parole:
                parole.append(t)

    return "|".join(parole[:8])


def estrai_evidenze_da_testo(testo):
    testo = _normalizza(testo)

    evidenze = []
    parole_utili = [
        "aperto", "chiuso", "orario", "venerdi", "venerdì",
        "weekly", "bar", "caffe", "caffè", "laboratorio",
        "accesso", "uscita", "entrata", "vietato", "attenzione",
        "istruzioni", "premere", "usare", "errore", "warning"
    ]

    for parola in parole_utili:
        if parola in testo and parola not in evidenze:
            evidenze.append(parola)

    return evidenze


def costruisci_ipotesi_da_evento(evento, mondo):
    evento = _testo(evento)
    testo = _normalizza(mondo)
    evidenze = estrai_evidenze_da_testo(testo)

    if evento in ["contenuto_informativo_rilevante", "informazione_operativa"]:
        return {
            "concetto": "fonte_informativa",
            "ipotesi": (
                "la scena potrebbe contenere informazioni utili "
                "per comprendere il contesto"
            ),
            "evidenze": evidenze,
            "fiducia": 0.35 if evidenze else 0.25,
            "origine": evento
        }

    if evento == "supporto_informativo_potenziale":
        return {
            "concetto": "supporto_informativo_potenziale",
            "ipotesi": (
                "e' presente un possibile supporto informativo, "
                "ma il contenuto non e' ancora disponibile"
            ),
            "evidenze": evidenze,
            "fiducia": 0.25,
            "origine": evento
        }

    if evento == "dettaglio_funzionale_osservabile":
        return {
            "concetto": "dettaglio_funzionale",
            "ipotesi": (
                "la scena contiene un dettaglio potenzialmente utile "
                "per orientamento o decisioni future"
            ),
            "evidenze": evidenze,
            "fiducia": 0.30,
            "origine": evento
        }

    return None


def salva_ipotesi_semantica(ipotesi, mondo=None):
    if not isinstance(ipotesi, dict):
        return None

    concetto = _testo(ipotesi.get("concetto"))
    if not concetto:
        return None

    evidenze = ipotesi.get("evidenze", [])
    if not isinstance(evidenze, list):
        evidenze = []

    dati = _carica_memoria()
    firma = _firma(concetto, evidenze)

    for voce in dati["ipotesi"]:
        if voce.get("firma") == firma:
            voce["ultimo_aggiornamento"] = time.time()
            voce["osservazioni"] = int(voce.get("osservazioni", 1)) + 1
            voce["fiducia"] = min(
                1.0,
                float(voce.get("fiducia", 0.3)) + 0.05
            )

            for e in evidenze:
                if e not in voce.get("evidenze", []):
                    voce.setdefault("evidenze", []).append(e)

            _salva_memoria(dati)
            return voce

    nuova = {
        "firma": firma,
        "concetto": concetto,
        "ipotesi": ipotesi.get("ipotesi", ""),
        "evidenze": evidenze,
        "fiducia": float(ipotesi.get("fiducia", 0.3)),
        "conferme": 0,
        "smentite": 0,
        "osservazioni": 1,
        "origine": ipotesi.get("origine", "osservazione"),
        "mondo_esempio": mondo or "",
        "creata": time.time(),
        "ultimo_aggiornamento": time.time()
    }

    dati["ipotesi"].append(nuova)
    dati["ipotesi"] = dati["ipotesi"][-100:]
    _salva_memoria(dati)
    return nuova


def trova_ipotesi_simili(concetto=None, evidenze=None, limite=5):
    dati = _carica_memoria()
    risultati = []

    concetto_norm = _testo(concetto)
    evidenze_norm = []
    if isinstance(evidenze, list):
        evidenze_norm = [_normalizza(e) for e in evidenze]

    for voce in dati.get("ipotesi", []):
        punteggio = 0

        if concetto_norm and concetto_norm == _testo(voce.get("concetto")):
            punteggio += 3

        voce_evidenze = [
            _normalizza(e)
            for e in voce.get("evidenze", [])
        ]

        for e in evidenze_norm:
            if e in voce_evidenze:
                punteggio += 1

        if punteggio > 0:
            copia = dict(voce)
            copia["punteggio_similarita"] = punteggio
            risultati.append(copia)

    risultati.sort(
        key=lambda v: (
            v.get("punteggio_similarita", 0),
            v.get("fiducia", 0)
        ),
        reverse=True
    )

    return risultati[:limite]


def aggiorna_fiducia_ipotesi(firma, confermata=True, motivo=""):
    dati = _carica_memoria()

    for voce in dati.get("ipotesi", []):
        if voce.get("firma") != firma:
            continue

        if confermata:
            voce["conferme"] = int(voce.get("conferme", 0)) + 1
            voce["fiducia"] = min(
                1.0,
                float(voce.get("fiducia", 0.3)) + 0.15
            )
        else:
            voce["smentite"] = int(voce.get("smentite", 0)) + 1
            voce["fiducia"] = max(
                0.0,
                float(voce.get("fiducia", 0.3)) - 0.20
            )

        voce["ultimo_motivo_aggiornamento"] = motivo
        voce["ultimo_aggiornamento"] = time.time()
        _salva_memoria(dati)
        return voce

    return None


def ipotesi_pronta_per_condizione(voce):
    if not isinstance(voce, dict):
        return False

    try:
        fiducia = float(voce.get("fiducia", 0.0))
    except Exception:
        fiducia = 0.0

    conferme = int(voce.get("conferme", 0) or 0)
    smentite = int(voce.get("smentite", 0) or 0)

    return (
        fiducia >= 0.70
        and conferme >= 2
        and smentite == 0
    )


def elenco_conoscenze():
    return _carica_memoria().get("ipotesi", [])