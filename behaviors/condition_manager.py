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
import imp
import time
import shutil


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
    return os.path.join(CONDIZIONI_DIR, nome_modulo + ".py")


def _sposta_in_rejected(nome_modulo, motivo):
    """
    Sposta una condizione difettosa fuori da generated_conditions.
    In questo modo NAO non continuerà a ricaricarla nei cicli successivi.
    """
    _assicura_cartelle()

    origine = _path_condizione(nome_modulo)

    if not os.path.exists(origine):
        return

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    destinazione = os.path.join(
        REJECTED_DIR,
        nome_modulo + "_rejected_" + timestamp + ".py"
    )

    try:
        shutil.move(origine, destinazione)
        logger.warning(u"[CONDIZIONI] Condizione spostata in rejected_conditions: {} | motivo: {}".format(
            nome_modulo,
            motivo
        ))
    except Exception as e:
        logger.error(u"[CONDIZIONI] Impossibile spostare {} in rejected_conditions: {}".format(
            nome_modulo,
            e
        ))

    reset_cache_condizioni()


def _registra_errore(nome_modulo, errore):
    numero_errori = _errori_condizione.get(nome_modulo, 0) + 1
    _errori_condizione[nome_modulo] = numero_errori

    logger.warning(u"[CONDIZIONI] Errore runtime in {} ({}/{}): {}".format(
        nome_modulo,
        numero_errori,
        MAX_ERRORI_CONDIZIONE,
        errore
    ))

    if numero_errori >= MAX_ERRORI_CONDIZIONE:
        _sposta_in_rejected(nome_modulo, errore)

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
    condizioni = []

    for nome_file in os.listdir(CONDIZIONI_DIR):
        if not nome_file.endswith(".py"):
            continue

        # importa il file
        # verifica che abbia condizione() e comportamento()
        # aggiunge alla lista:
        condizioni.append({
            "nome": nome_file,
            "modulo": modulo,
            "condizione": modulo.condizione,
            "comportamento": modulo.comportamento
        })

    # QUI va messo l'ordinamento
    condizioni.sort(
        key=lambda item: _priorita_condizione(item["nome"]),
        reverse=True
    )

    return condizioni

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
                _ultima_attivazione_condizione[nome] = adesso

                try:
                    return modulo.comportamento()
                except Exception as e:
                    _registra_errore(nome, e)
                    return None

        except Exception as e:
            _registra_errore(nome, e)

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