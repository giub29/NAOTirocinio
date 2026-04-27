# -*- coding: utf-8 -*-
"""
Gestione comportamento adattivo:
- cerca comportamenti JSON già generati;
- se trova un comportamento simile, lo riusa;
- se non lo trova, chiede al LLM;
- salva il nuovo comportamento generato.
"""

import os
import time
import json
import logging
import requests

logger = logging.getLogger(__name__)

GENERATED_DIR = os.path.join(os.path.dirname(__file__), "generated")
SOGLIA_SIMILARITA = 1


def _assicura_cartella_generated():
    if not os.path.exists(GENERATED_DIR):
        os.makedirs(GENERATED_DIR)


def nessuna_condizione_nota(mondo, ultima_decisione):
    if u"STO CAMMINANDO" in mondo:
        return False

    if u"L'utente dice" in mondo:
        return False

    if u"Riconosco" in mondo or u"Vedo un volto ignoto" in mondo:
        return False

    azioni = ultima_decisione.get("azioni", [])

    if not azioni:
        return True

    return False


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


def salva_comportamento_generato(mondo, decisione):
    try:
        _assicura_cartella_generated()

        timestamp_file = time.strftime("%Y%m%d_%H%M%S")
        nome_file = "adaptive_{}.json".format(timestamp_file)
        path_file = os.path.join(GENERATED_DIR, nome_file)

        dati = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mondo": mondo,
            "decisione": decisione
        }

        with open(path_file, "wb") as f:
            f.write(json.dumps(dati, ensure_ascii=False, indent=2).encode("utf-8"))

        logger.info(u"[ADAPTIVE] Comportamento salvato in {}".format(path_file))
        return path_file

    except Exception as e:
        logger.warning(u"[ADAPTIVE] Errore salvataggio comportamento: {}".format(e))
        return None


def carica_comportamenti_generati():
    comportamenti = []

    try:
        _assicura_cartella_generated()

        for nome_file in os.listdir(GENERATED_DIR):
            if not nome_file.endswith(".json"):
                continue

            path_file = os.path.join(GENERATED_DIR, nome_file)

            try:
                with open(path_file, "rb") as f:
                    contenuto = f.read().decode("utf-8")

                dati = json.loads(contenuto)

                if "mondo" in dati and "decisione" in dati:
                    comportamenti.append(dati)

            except Exception as e:
                logger.warning(u"[ADAPTIVE] Impossibile caricare {}: {}".format(
                    nome_file,
                    e
                ))

    except Exception as e:
        logger.warning(u"[ADAPTIVE] Errore lettura cartella generated: {}".format(e))

    return comportamenti


def _normalizza_unicode(testo):
    try:
        if isinstance(testo, str):
            testo = testo.decode("utf-8", "ignore")
    except Exception:
        pass

    return testo.lower()


def _tokenizza(testo):
    testo = _normalizza_unicode(testo)

    separatori = [u".", u",", u";", u":", u"!", u"?", u"'", u'"', u"(", u")", u"[", u"]"]

    for sep in separatori:
        testo = testo.replace(sep, u" ")

    parole = testo.split()

    stopword = set([
        u"report", u"sono", u"fermo", u"sto", u"camminando",
        u"la", u"il", u"lo", u"le", u"gli",
        u"un", u"una", u"di", u"a", u"al", u"in",
        u"e", u"è", u"c", u"ce", u"qualcosa"
    ])

    parole_utili = []

    for p in parole:
        if len(p) < 3:
            continue

        if p in stopword:
            continue

        parole_utili.append(p)

    return set(parole_utili)


def _similarita_mondo(mondo_a, mondo_b):
    token_a = _tokenizza(mondo_a)
    token_b = _tokenizza(mondo_b)

    if not token_a or not token_b:
        return 0

    comuni = token_a.intersection(token_b)
    return len(comuni)


def trova_comportamento_simile(mondo):
    comportamenti = carica_comportamenti_generati()

    migliore = None
    miglior_punteggio = 0

    for comp in comportamenti:
        mondo_salvato = comp.get("mondo", "")
        punteggio = _similarita_mondo(mondo, mondo_salvato)

        if punteggio > miglior_punteggio:
            miglior_punteggio = punteggio
            migliore = comp

    if migliore and miglior_punteggio >= SOGLIA_SIMILARITA:
        logger.info(u"[ADAPTIVE] Riuso comportamento salvato. Similarità: {}".format(
            miglior_punteggio
        ))
        return migliore.get("decisione", None)

    return None


def _genera_comportamento_con_llm(mondo, dati_memoria, stato_robot, chiave_privata):
    logger.info(u"[ADAPTIVE] Nessun comportamento simile. Chiedo comportamento JSON al LLM.")

    if not chiave_privata:
        logger.warning(u"[ADAPTIVE] OPENAI_API_KEY assente. Uso fallback.")
        return _fallback_base()

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

        if res.status_code != 200:
            logger.warning(u"[ADAPTIVE] Errore HTTP LLM: {}".format(res.text))
            return _fallback_base()

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


def gestisci_comportamento_adattivo(mondo, dati_memoria, stato_robot, chiave_privata):
    logger.info(u"[ADAPTIVE] Controllo comportamenti già generati.")

    decisione_salvata = trova_comportamento_simile(mondo)

    if decisione_salvata:
        logger.info(u"[ADAPTIVE] Uso comportamento già appreso.")
        return decisione_salvata

    return _genera_comportamento_con_llm(
        mondo,
        dati_memoria,
        stato_robot,
        chiave_privata
    )