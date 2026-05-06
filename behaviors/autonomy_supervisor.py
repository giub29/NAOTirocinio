# -*- coding: utf-8 -*-
"""
Autonomy Supervisor - FASE B

Questo modulo centralizza la gestione autonoma delle condizioni.

Per ora NON rende ancora NAO totalmente autonomo.
Serve a:
- valutare le condizioni generate
- evitare che soul.py dipenda direttamente dai dettagli interni
- preparare la FASE C, cioe' generazione autonoma piu' indipendente
"""

import logging
import traceback

logger = logging.getLogger(__name__)


def gestisci_autonomia(mondo, stato_runtime=None):
    """
    Punto unico di ingresso per l'autonomia.

    Input:
        mondo: stringa/report sensoriale prodotto da soul.py
        stato_runtime: dizionario opzionale con dati aggiuntivi

    Output:
        dizionario decisione oppure None
    """

    if stato_runtime is None:
        stato_runtime = {}

    logger.info("[AUTONOMIA] Supervisore attivo")

    # 1. Prova prima a usare condizioni Python gia' generate
    decisione = valuta_condizioni_generate_sicure(mondo, stato_runtime)

    if decisione is not None:
        logger.info("[AUTONOMIA] Decisione ottenuta da condizione generata")
        return decisione

    # 2. Per ora non generiamo ancora qui nuove condizioni.
    # Questa parte verra' estesa nella FASE C.
    logger.info("[AUTONOMIA] Nessuna condizione autonoma applicabile")

    return None


def valuta_condizioni_generate_sicure(mondo, stato_runtime):
    """
    Valuta le condizioni generate gia' presenti nel progetto.

    Questa funzione fa da protezione:
    se condition_manager genera errori, soul.py non deve crashare.
    """

    try:
        from behaviors import condition_manager

        # Caso piu' probabile nel tuo progetto:
        if hasattr(condition_manager, "valuta_condizioni_generate"):
            return condition_manager.valuta_condizioni_generate(mondo, stato_runtime)

        # Variante possibile:
        if hasattr(condition_manager, "valuta_condizioni_generate_caricate"):
            return condition_manager.valuta_condizioni_generate_caricate(mondo, stato_runtime)

        logger.warning("[AUTONOMIA] Nessuna funzione valida trovata in condition_manager")
        return None

    except Exception as e:
        logger.error("[AUTONOMIA] Errore valutando condizioni generate: {}".format(e))
        logger.error(traceback.format_exc())
        return None