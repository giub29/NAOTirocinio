# -*- coding: utf-8 -*-
"""
Caricatore di condizioni Python generate.

Questo modulo permette a NAO di:
1. caricare automaticamente i file Python generati dall'LLM;
2. valutare le condizioni a runtime senza input manuale da tastiera;
3. eseguire il comportamento associato se la condizione risulta vera;
4. isolare in rejected_conditions le condizioni che generano troppi errori.
"""

import os
import logging
import importlib.util
import time
import shutil

from behaviors.condition_memory import (
    registra_attivazione,
    registra_errore_condizione,
    marca_condizione_rifiutata
)

from behaviors.condition_repair import tenta_riparazione_condizione

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
CONDIZIONI_DIR = os.path.join(BASE_DIR, "generated_conditions")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected_conditions")

_condizioni_cache = None
_ultima_attivazione_condizione = {}
_errori_condizione = {}

# Una condizione vera non viene rieseguita continuamente.
COOLDOWN_CONDIZIONE = 30

# Dopo questo numero di errori runtime, la condizione viene disattivata.
MAX_ERRORI_CONDIZIONE = 3


def reset_cache_condizioni():
    global _condizioni_cache
    _condizioni_cache = None


def _assicura_cartelle():
    if not os.path.exists(CONDIZIONI_DIR):
        os.makedirs(CONDIZIONI_DIR)

    if not os.path.exists(REJECTED_DIR):
        os.makedirs(REJECTED_DIR)


def _path_condizione(nome_modulo):
    if nome_modulo.endswith(".py"):
        nome_modulo = nome_modulo[:-3]

    return os.path.join(CONDIZIONI_DIR, nome_modulo + ".py")


def _sposta_in_rejected(nome_modulo, motivo, mondo=None, stato_runtime=None):
    """
    Sposta una condizione difettosa fuori da generated_conditions.

    Fase 4:
    - sposta il file .py in rejected_conditions;
    - aggiorna e sposta il file .meta.json;
    - prova a riparare automaticamente la condizione, se possibile.
    """

    _assicura_cartelle()

    if nome_modulo.endswith(".py"):
        nome_modulo = nome_modulo[:-3]

    origine_py = os.path.join(CONDIZIONI_DIR, nome_modulo + ".py")
    origine_meta = os.path.join(CONDIZIONI_DIR, nome_modulo + ".meta.json")

    timestamp = time.strftime("%Y%m%d_%H%M%S")

    destinazione_py = os.path.join(
        REJECTED_DIR,
        nome_modulo + "_rejected_" + timestamp + ".py"
    )

    destinazione_meta = os.path.join(
        REJECTED_DIR,
        nome_modulo + "_rejected_" + timestamp + ".meta.json"
    )

    try:
        try:
            marca_condizione_rifiutata(nome_modulo, motivo)
        except Exception as e:
            logger.warning(u"[CONDIZIONI] Impossibile aggiornare metadati rifiuto {}: {}".format(
                nome_modulo,
                e
            ))

        if os.path.exists(origine_py):
            shutil.move(origine_py, destinazione_py)

        if os.path.exists(origine_meta):
            shutil.move(origine_meta, destinazione_meta)

        logger.warning(u"[CONDIZIONI] Condizione spostata in rejected_conditions: {} | motivo: {}".format(
            nome_modulo,
            motivo
        ))

        try:
            esito_riparazione = tenta_riparazione_condizione(
                nome_modulo,
                motivo,
                mondo,
                stato_runtime
            )

            if not isinstance(esito_riparazione, dict):
                logger.warning(u"[CONDIZIONI] Riparazione fallita per {} | esito non valido: {}".format(
                    nome_modulo,
                    esito_riparazione
                ))

            elif esito_riparazione.get("success"):
                logger.warning(u"[CONDIZIONI] Riparazione riuscita per {} | nuova condizione: {}".format(
                    nome_modulo,
                    esito_riparazione.get("new_path")
                ))

            else:
                logger.warning(u"[CONDIZIONI] Riparazione fallita per {} | stato: {} | motivo: {}".format(
                    nome_modulo,
                    esito_riparazione.get("status"),
                    esito_riparazione.get("reason")
                ))

        except Exception as e:
            logger.warning(u"[CONDIZIONI] Errore imprevisto nella riparazione automatica di {}: {}".format(
                nome_modulo,
                e
            ))

    except Exception as e:
        logger.error(u"[CONDIZIONI] Impossibile spostare {} in rejected_conditions: {}".format(
            nome_modulo,
            e
        ))

    reset_cache_condizioni()


def _registra_errore(nome_modulo, errore, mondo=None, stato_runtime=None):
    """
    Registra un errore runtime di una condizione.

    Fase 4:
    - aggiorna il contatore interno;
    - aggiorna il .meta.json;
    - se gli errori sono troppi, sposta la condizione in rejected_conditions;
    - dopo il rifiuto prova la riparazione automatica.
    """

    if nome_modulo.endswith(".py"):
        nome_base = nome_modulo[:-3]
    else:
        nome_base = nome_modulo

    numero_errori = _errori_condizione.get(nome_base, 0) + 1
    _errori_condizione[nome_base] = numero_errori

    try:
        registra_errore_condizione(nome_base, errore)
    except Exception as e:
        logger.warning(u"[CONDIZIONI] Errore aggiornamento memoria condizione {}: {}".format(
            nome_base,
            e
        ))

    logger.warning(u"[CONDIZIONI] Errore runtime in {} ({}/{}): {}".format(
        nome_base,
        numero_errori,
        MAX_ERRORI_CONDIZIONE,
        errore
    ))

    if numero_errori >= MAX_ERRORI_CONDIZIONE:
        _sposta_in_rejected(
            nome_base,
            errore,
            mondo,
            stato_runtime
        )

def _priorita_condizione(nome):
    nome = nome.lower()
    punteggio = 0

    if "durante_cammino" in nome:
        punteggio += 100

    if "_e_" in nome:
        punteggio += 80

    if "entrambe" in nome:
        punteggio += 70

    if "ostacolo" in nome:
        punteggio += 40

    return punteggio

def carica_condizioni_generate():
    global _condizioni_cache

    _assicura_cartelle()

    if _condizioni_cache is not None:
        return _condizioni_cache

    condizioni = []

    for nome_file in ordina_condizioni_per_priorita(os.listdir(CONDIZIONI_DIR)):
        if not nome_file.endswith(".py"):
            continue

        if nome_file.startswith("__"):
            continue

        nome_modulo = nome_file.replace(".py", "")
        path_file = os.path.join(CONDIZIONI_DIR, nome_file)

        try:
            spec = importlib.util.spec_from_file_location(nome_modulo, path_file)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)

            if not hasattr(modulo, "condizione"):
                _sposta_in_rejected(nome_modulo, "manca funzione condizione")
                continue

            if not hasattr(modulo, "comportamento"):
                _sposta_in_rejected(nome_modulo, "manca funzione comportamento")
                continue

            condizioni.append({
                "nome": nome_file,
                "modulo": modulo,
                "condizione": modulo.condizione,
                "comportamento": modulo.comportamento
            })

        except Exception as e:
            logger.warning(u"[CONDIZIONI] Errore caricamento {}: {}".format(
                nome_file,
                e
            ))
            _sposta_in_rejected(nome_modulo, str(e))

    condizioni.sort(
        key=lambda item: _priorita_condizione(item["nome"]),
        reverse=True
    )

    _condizioni_cache = condizioni
    return condizioni

def punteggio_specificita_condizione(nome_file):
    """
    Assegna un punteggio alla condizione.
    Piu' il punteggio e' alto, prima viene valutata.

    Obiettivo:
    - condizioni composte prima delle semplici
    - volto riconosciuto prima di tocco generico
    - ostacolo + tocco prima di solo ostacolo
    """

    nome = nome_file.lower()
    punteggio = 0

    # Le condizioni composte spesso hanno "_e_"
    if "_e_" in nome:
        punteggio += 100

    # Più parole specifiche contiene, più è importante
    parole_specifiche = [
        "volto_riconosciuto",
        "volto",
        "riconosciuto",
        "ostacolo",
        "sinistra",
        "destra",
        "mano",
        "piede",
        "testa",
        "fermo",
        "interazione",
        "utente"
    ]

    for parola in parole_specifiche:
        if parola in nome:
            punteggio += 10

    # Le condizioni troppo generiche devono arrivare dopo
    if "tocco_mano_sinistra" in nome:
        punteggio -= 5

    if "tocco_mano_destra" in nome:
        punteggio -= 5

    if "carezza_testa" in nome:
        punteggio -= 5

    return punteggio


def ordina_condizioni_per_priorita(lista_file):
    """
    Ordina i file condizione dalla piu' specifica alla piu' generica.
    """

    return sorted(
        lista_file,
        key=lambda nome: punteggio_specificita_condizione(nome),
        reverse=True
    )

def _decisione_coerente_con_mondo(decisione, mondo, nome_condizione):
    """
    Controlla che una decisione generata sia coerente con il mondo attuale.
    Serve a impedire che vecchie condizioni sbagliate restino attive.
    """

    if not isinstance(decisione, dict):
        return False, "decisione non e' un dizionario"

    azioni = decisione.get("azioni", [])

    if not isinstance(azioni, list):
        return False, "azioni non e' una lista"

    testo_mondo = (mondo or "").lower()
    nome = (nome_condizione or "").lower()

    nome_spaziale = (
        "ostacolo" in nome or
        "oggetto_vicino" in nome or
        "sinistra" in nome or
        "destra" in nome or
        "frontale" in nome
    )

    nome_sociale = (
        "carezza" in nome or
        "mano" in nome or
        "volto" in nome or
        "entrambe" in nome
    )

    mondo_spaziale = nome_spaziale and not nome_sociale

    mondo_sociale = (
        "carezza" in testo_mondo or
        "mano" in testo_mondo or
        "volto" in testo_mondo or
        "riconosco" in testo_mondo
    )

    frasi_sociali_non_coerenti = [
        "ciao",
        "come stai",
        "cosa stai facendo",
        "come posso aiutarti",
        "come ti senti",
        "cosa c'e' qui",
        "cosa c'è qui",
        "cosa c'e' intorno",
        "cosa c'è intorno",
        "cosa vedi"
    ]

    frasi_spostamento = [
        "mi sposto",
        "mi muovo",
        "mi allontano",
        "evito",
        "aggiro"
    ]

    robot_fermo = "sono fermo" in testo_mondo
    robot_camminando = "sto camminando" in testo_mondo

    for azione in azioni:
        if not isinstance(azione, dict):
            return False, "azione non e' un dizionario"

        tipo = azione.get("tipo", "")

        if tipo == "parla":
            testo_azione = azione.get("testo", "").lower()

            if mondo_spaziale:
                for frase in frasi_sociali_non_coerenti:
                    if frase in testo_azione:
                        return False, "frase sociale non coerente con mondo spaziale"

            if robot_fermo and not robot_camminando:
                for frase in frasi_spostamento:
                    if frase in testo_azione:
                        return False, "frase di spostamento non coerente da fermo"

        if tipo in ["cammina", "gira"]:
            if robot_fermo and not robot_camminando:
                return False, "movimento non coerente quando il robot e' fermo"

    return True, "ok"

def valuta_condizioni_generate(mondo, stato_runtime):
    """
    Valuta tutte le condizioni generate.

    Ritorna una decisione se una condizione è vera, altrimenti None.
    Questa funzione è pensata per essere chiamata automaticamente dal ciclo
    principale di soul.py, senza input manuale dell'utente.
    """
    condizioni = carica_condizioni_generate()
    adesso = time.time()

    for item in condizioni:
        nome = item["nome"]
        modulo = item["modulo"]

        try:
            ultimo_tempo = _ultima_attivazione_condizione.get(nome, 0)

            if adesso - ultimo_tempo < COOLDOWN_CONDIZIONE:
                continue

            condizione_vera = modulo.condizione(mondo, stato_runtime)

            if condizione_vera:
                logger.info(u"[CONDIZIONI] Attivata condizione generata: {}".format(nome))

                try:
                    try:
                        decisione = modulo.comportamento(
                            None,
                            stato_runtime.get("memoria", {}),
                            stato_runtime
                        )
                    except TypeError:
                        decisione = modulo.comportamento()

                except Exception as e:
                    _registra_errore(
                        nome,
                        e,
                        mondo,
                        stato_runtime
                    )
                    continue

                coerente, motivo = _decisione_coerente_con_mondo(
                    decisione,
                    mondo,
                    nome
                )

                if not coerente:
                    logger.warning(u"[CONDIZIONI] Condizione incoerente, sposto in rejected: {} | {}".format(
                        nome,
                        motivo
                    ))

                    _sposta_in_rejected(
                        nome.replace(".py", ""),
                        motivo,
                        mondo,
                        stato_runtime
                    )

                    continue

                _ultima_attivazione_condizione[nome] = adesso

                try:
                    registra_attivazione(
                        nome.replace(".py", ""),
                        mondo,
                        decisione
                    )
                except Exception as e:
                    logger.warning(u"[CONDIZIONI] Errore registrazione attivazione condizione: {}".format(e))

                return decisione

        except Exception as e:
            _registra_errore(
                nome,
                e,
                mondo,
                stato_runtime
            )
            continue

    return None

def esegui_condizione_per_nome(nome, mondo, stato_runtime):
    """
    Funzione solo di debug manuale.
    L'autonomia vera usa valuta_condizioni_generate() dentro soul.py.
    """
    condizioni = carica_condizioni_generate()

    nome = nome.lower().strip()

    for item in condizioni:
        nome_condizione = item["nome"].lower()

        if nome in nome_condizione:
            try:
                mondo_test = mondo + u" Sento una carezza sulla testa. Vedo qualcosa vicino. Ostacolo a sinistra."
                if item["modulo"].condizione(mondo_test, stato_runtime):
                    print("[TEST] Attivata:", item["nome"])
                    return item["modulo"].comportamento()
                else:
                    print("[TEST] Condizione trovata ma NON attiva")
                    return None

            except Exception as e:
                print("[TEST ERROR]:", e)
                _registra_errore(item["nome"], e)
                return None

    print("[TEST] Condizione non trovata:", nome)
    return None