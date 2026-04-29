# -*- coding: utf-8 -*-
"""
Generatore autonomo di condizioni Python tramite LLM.

Flusso:
1. chiede al LLM codice Python libero;
2. salva il codice in quarantine_conditions;
3. analizza il codice;
4. se sicuro, lo importa e lo valida;
5. se valido, lo promuove in generated_conditions;
6. se non valido, lo sposta in rejected_conditions.
"""

import os
import re
import time
import shutil
import logging
import requests
import json
import imp

from behaviors.condition_manager import reset_cache_condizioni

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)

QUARANTINE_DIR = os.path.join(BASE_DIR, "quarantine_conditions")
GENERATED_DIR = os.path.join(BASE_DIR, "generated_conditions")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected_conditions")

AZIONI_CONSENTITE = [
    "parla",
    "guarda",
    "occhi",
    "animazione",
    "posa",
    "fermati"
]

TOKEN_VIETATI = [
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import shutil",
    "import requests",
    "open(",
    "file(",
    "exec",
    "eval",
    "compile",
    "__import__",
    "globals",
    "locals",
    "input(",
    "raw_input(",
    "while True",
    "while 1",
    "for ever",
    "ALProxy",
    "naoqi",
    "thread",
    "multiprocessing"
]


def _assicura_cartelle():
    for cartella in [QUARANTINE_DIR, GENERATED_DIR, REJECTED_DIR]:
        if not os.path.exists(cartella):
            os.makedirs(cartella)


def _slug_testo(testo):
    testo = testo.lower()
    testo = re.sub(r"[^a-z0-9_]+", "_", testo)
    testo = re.sub(r"_+", "_", testo)
    testo = testo.strip("_")

    if not testo:
        testo = "condizione_generata"

    return testo[:50]


def _estrai_codice_python(testo):
    testo = testo.strip()

    if "```python" in testo:
        testo = testo.split("```python", 1)[1]
        testo = testo.split("```", 1)[0]

    elif "```" in testo:
        testo = testo.split("```", 1)[1]
        testo = testo.split("```", 1)[0]

    return testo.strip()


def _scrivi_file(path_file, contenuto):
    with open(path_file, "wb") as f:
        f.write(contenuto.encode("utf-8"))


def _leggi_file(path_file):
    with open(path_file, "rb") as f:
        return f.read().decode("utf-8")


def _codice_contiene_token_vietati(codice):
    codice_lower = codice.lower()

    for token in TOKEN_VIETATI:
        if token.lower() in codice_lower:
            return token

    return None


def _valida_struttura_codice(codice):
    if "def condizione(" not in codice:
        return False, "Manca def condizione(mondo, stato_runtime)"

    if "def comportamento(" not in codice:
        return False, "Manca def comportamento()"

    if "return" not in codice:
        return False, "Manca return"

    token_vietato = _codice_contiene_token_vietati(codice)

    if token_vietato:
        return False, "Token vietato trovato: {}".format(token_vietato)

    return True, "ok"


def _valida_modulo_python(path_file):
    nome_modulo = os.path.basename(path_file).replace(".py", "")

    try:
        modulo = imp.load_source(nome_modulo, path_file)

        if not hasattr(modulo, "condizione"):
            return False, "Funzione condizione assente"

        if not hasattr(modulo, "comportamento"):
            return False, "Funzione comportamento assente"

        test_mondo = u"REPORT: situazione di test. SONO FERMO."
        test_runtime = {}

        risultato_condizione = modulo.condizione(test_mondo, test_runtime)

        if not isinstance(risultato_condizione, bool):
            return False, "condizione() deve restituire True/False"

        comportamento = modulo.comportamento()

        if not isinstance(comportamento, dict):
            return False, "comportamento() deve restituire un dizionario"

        if "azioni" not in comportamento:
            return False, "comportamento() non contiene azioni"

        azioni = comportamento.get("azioni", [])

        if not isinstance(azioni, list):
            return False, "azioni deve essere una lista"

        for azione in azioni:
            if not isinstance(azione, dict):
                return False, "azione non valida"

            tipo = azione.get("tipo", "")

            if tipo not in AZIONI_CONSENTITE:
                return False, "Azione non consentita: {}".format(tipo)

        return True, "ok"

    except Exception as e:
        return False, "Errore import/test modulo: {}".format(e)


def _sposta_in_rejected(path_file, motivo):
    _assicura_cartelle()

    nome = os.path.basename(path_file)
    nuovo_nome = nome.replace(".py", "_rejected.py")
    path_rejected = os.path.join(REJECTED_DIR, nuovo_nome)

    try:
        shutil.move(path_file, path_rejected)

        motivo_path = path_rejected + ".reason.txt"

        with open(motivo_path, "wb") as f:
            f.write(motivo.encode("utf-8"))

        logger.warning(u"[GENERATOR] Condizione rifiutata: {}".format(motivo))

    except Exception as e:
        logger.warning(u"[GENERATOR] Errore spostamento rejected: {}".format(e))


def _promuovi_in_generated(path_file):
    _assicura_cartelle()

    nome = os.path.basename(path_file)
    path_finale = os.path.join(GENERATED_DIR, nome)

    if os.path.exists(path_finale):
        base, ext = os.path.splitext(nome)
        nome = "{}_{}".format(base, int(time.time())) + ext
        path_finale = os.path.join(GENERATED_DIR, nome)

    shutil.move(path_file, path_finale)
    reset_cache_condizioni()

    logger.info(u"[GENERATOR] Nuova condizione promossa: {}".format(path_finale))
    return path_finale


def _costruisci_prompt(mondo, dati_memoria, stato_robot):
    return (
        u"Sei un generatore di codice Python per un robot NAO.\n"
        u"Devi generare UNA nuova condizione Python autonoma.\n\n"

        u"REGOLE OBBLIGATORIE:\n"
        u"- Genera SOLO codice Python.\n"
        u"- Non scrivere spiegazioni.\n"
        u"- Non usare import.\n"
        u"- Non usare open, exec, eval, subprocess, socket, thread.\n"
        u"- Non chiamare direttamente NAOqi o ALProxy.\n"
        u"- Non creare loop infiniti.\n"
        u"- Il file deve contenere SOLO due funzioni:\n"
        u"  1) condizione(mondo, stato_runtime)\n"
        u"  2) comportamento()\n\n"

        u"FORMATO OBBLIGATORIO:\n"
        u"# -*- coding: utf-8 -*-\n\n"
        u"def condizione(mondo, stato_runtime):\n"
        u"    return u\"testo trigger\" in mondo\n\n"
        u"def comportamento():\n"
        u"    return {\n"
        u"        \"stato_interno\": \"curioso\",\n"
        u"        \"obiettivo\": \"descrizione breve\",\n"
        u"        \"azioni\": [\n"
        u"            {\"tipo\": \"parla\", \"testo\": \"Frase sicura.\"}\n"
        u"        ],\n"
        u"        \"memoria\": []\n"
        u"    }\n\n"

        u"AZIONI CONSENTITE:\n"
        u"- parla\n"
        u"- guarda\n"
        u"- occhi\n"
        u"- animazione\n"
        u"- posa\n"
        u"- fermati\n\n"

        u"MONDO ATTUALE:\n"
        + mondo +
        u"\n\nMEMORIA:\n"
        + json.dumps(dati_memoria, ensure_ascii=False) +
        u"\n\nSTATO ROBOT:\n"
        + json.dumps(stato_robot, ensure_ascii=False)
    )


def _chiama_llm_codice(mondo, dati_memoria, stato_robot, chiave_privata):
    prompt = _costruisci_prompt(mondo, dati_memoria, stato_robot)

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": mondo}
        ],
        "temperature": 0.1,
        "max_tokens": 700
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + chiave_privata
    }

    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=10
    )

    if res.status_code != 200:
        raise Exception("Errore HTTP LLM: {}".format(res.text))

    return res.json()["choices"][0]["message"]["content"]

def _mondo_generabile(mondo):
    eventi_da_non_generare = [
        u"STO CAMMINANDO",
        u"Riconosco",
        u"Vedo un volto ignoto",
        u"La mia batteria",
        u"L'utente dice"
    ]

    for evento in eventi_da_non_generare:
        if evento in mondo:
            return False

    return True

def genera_condizione_autonoma(mondo, dati_memoria, stato_robot, chiave_privata):
    _assicura_cartelle()

    if not _mondo_generabile(mondo):
        logger.info(u"[GENERATOR] Mondo non adatto alla generazione autonoma.")
        return None

    if not chiave_privata:
        logger.warning(u"[GENERATOR] OPENAI_API_KEY assente. Non genero condizioni.")
        return None

    try:
        logger.info(u"[GENERATOR] Richiesta nuova condizione Python al LLM")

        risposta = _chiama_llm_codice(
            mondo,
            dati_memoria,
            stato_robot,
            chiave_privata
        )

        codice = _estrai_codice_python(risposta)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        nome_base = _slug_testo(mondo)
        nome_file = "condizione_{}_{}.py".format(nome_base, timestamp)

        path_quarantine = os.path.join(QUARANTINE_DIR, nome_file)

        _scrivi_file(path_quarantine, codice)

        valido, motivo = _valida_struttura_codice(codice)

        if not valido:
            _sposta_in_rejected(path_quarantine, motivo)
            return None

        valido, motivo = _valida_modulo_python(path_quarantine)

        if not valido:
            _sposta_in_rejected(path_quarantine, motivo)
            return None

        return _promuovi_in_generated(path_quarantine)

    except Exception as e:
        logger.warning(u"[GENERATOR] Errore generazione condizione: {}".format(e))
        return None