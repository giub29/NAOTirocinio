# -*- coding: utf-8 -*-
"""
Gestione comportamento adattivo.

Step 3:
- se il sistema non sa cosa fare, chiede al LLM un comportamento JSON;
- NON genera ancora codice Python;
- restituisce solo azioni nel formato già validato da soul.py.
"""
import os
import time
import json
import logging
import requests

logger = logging.getLogger(__name__)


def nessuna_condizione_nota(mondo, ultima_decisione):
    azioni = ultima_decisione.get("azioni", [])

    if not azioni:
        return True

    return True #PER IL TEST LA SETTO A TRUE


def _estrai_json(testo):
    try:
        testo = testo.strip()
        testo = testo.replace("```json", "").replace("```", "").strip()

        inizio = testo.find("{")
        fine = testo.rfind("}")

        if inizio != -1 and fine != -1 and fine > inizio:
            testo = testo[inizio:fine + 1]

        return json.loads(testo)

    except Exception as e:
        logger.warning(u"[ADAPTIVE] JSON non valido: {}".format(e))
        logger.warning(u"[ADAPTIVE] Risposta grezza: {}".format(testo))
        return None


def _fallback_base():
    return {
        "stato_interno": "curioso",
        "obiettivo": "analizzare situazione sconosciuta",
        "azioni": [
            {"tipo": "guarda", "x": 0.0, "y": -0.2},
            {"tipo": "occhi", "colore": "yellow"},
            {"tipo": "parla", "testo": "Sto analizzando la situazione."}
        ],
        "memoria": []
    }


def gestisci_comportamento_adattivo(mondo, dati_memoria, stato_robot, chiave_privata):
    logger.info(u"[ADAPTIVE] Nessuna condizione nota. Chiedo comportamento JSON al LLM.")

    prompt = (
        u"Sei un generatore di comportamento adattivo per un robot NAO.\n"
        u"Devi proporre SOLO un comportamento sicuro in JSON valido.\n"
        u"NON generare codice Python.\n"
        u"NON scrivere testo fuori dal JSON.\n\n"

        u"FORMATO OBBLIGATORIO:\n"
        u"{\n"
        u'  "stato_interno": "curioso/prudente/sociale/allerta/neutro",\n'
        u'  "obiettivo": "breve descrizione",\n'
        u'  "azioni": [\n'
        u'    {"tipo":"parla","testo":"..."},\n'
        u'    {"tipo":"guarda","x":0.0,"y":-0.2},\n'
        u'    {"tipo":"occhi","colore":"yellow"}\n'
        u"  ],\n"
        u'  "memoria": []\n'
        u"}\n\n"

        u"AZIONI CONSENTITE:\n"
        u'{"tipo":"parla","testo":"..."}\n'
        u'{"tipo":"guarda","x":0.0,"y":-0.2}\n'
        u'{"tipo":"occhi","colore":"white/red/green/blue/yellow/purple/cyan"}\n'
        u'{"tipo":"animazione","path":"animations/Stand/Gestures/Stretch_1"}\n\n'

        u"REGOLE DI SICUREZZA:\n"
        u"- Non usare cammina.\n"
        u"- Non usare gira.\n"
        u"- Non usare fermati, salvo pericolo esplicito.\n"
        u"- Se il robot è fermo, limita il comportamento a osservare, parlare o cambiare occhi.\n"
        u"- Massimo 3 azioni.\n"
        u"- Se non sei sicuro, fai parlare il robot e fallo osservare.\n\n"

        u"MONDO ATTUALE:\n"
        + mondo +
        u"\n\nMEMORIA:\n"
        + json.dumps(dati_memoria, ensure_ascii=False) +
        u"\n\nSTATO ROBOT:\n"
        + json.dumps(stato_robot, ensure_ascii=False)
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": mondo}
        ],
        "temperature": 0.2,
        "max_tokens": 250
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + chiave_privata
    }

    try:
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=6
        )

        risposta = res.json()["choices"][0]["message"]["content"].strip()
        decisione = _estrai_json(risposta)

        if not decisione:
            return _fallback_base()

        if "azioni" not in decisione:
            return _fallback_base()

        salva_comportamento_generato(mondo, decisione)

        return decisione

    except Exception as e:
        logger.warning(u"[ADAPTIVE] Errore LLM adattivo: {}".format(e))
        return _fallback_base()

GENERATED_DIR = os.path.join(os.path.dirname(__file__), "generated")


def _assicura_cartella_generated():
    if not os.path.exists(GENERATED_DIR):
        os.makedirs(GENERATED_DIR)


def salva_comportamento_generato(mondo, decisione):
    """
    Salva il comportamento adattivo generato dal LLM come file JSON.
    Non salva codice Python.
    """
    try:
        _assicura_cartella_generated()

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        nome_file = "adaptive_{}.json".format(timestamp)
        path_file = os.path.join(GENERATED_DIR, nome_file)

        dati = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mondo": mondo,
            "decisione": decisione
        }

        with open(path_file, "w") as f:
            f.write(json.dumps(dati, ensure_ascii=False, indent=2).encode("utf-8"))

        logger.info(u"[ADAPTIVE] Comportamento salvato in {}".format(path_file))
        return path_file

    except Exception as e:
        logger.warning(u"[ADAPTIVE] Errore salvataggio comportamento: {}".format(e))
        return None