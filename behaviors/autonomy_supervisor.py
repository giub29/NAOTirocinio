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
import time
import os

logger = logging.getLogger(__name__)
ULTIMA_GENERAZIONE = 0
INTERVALLO_MINIMO_GENERAZIONE = 20
ULTIMO_MONDO_GENERATO = None

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

    logger.info("[AUTONOMIA] Nessuna condizione autonoma applicabile")

    deve_generare, motivo = situazione_merita_generazione(mondo, stato_runtime)
    logger.info("[AUTONOMIA] Valutazione generazione autonoma: {} - {}".format(
        deve_generare,
        motivo
    ))

    if deve_generare:
        nuova_decisione = prova_generazione_autonoma(mondo, stato_runtime, motivo)

        if nuova_decisione is not None:
            logger.info("[AUTONOMIA] Decisione ottenuta dopo generazione autonoma")
            return nuova_decisione

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
    
def situazione_merita_generazione(mondo, stato_runtime):
    """
    Decide se la situazione osservata merita una nuova condizione autonoma.

    Questa funzione e' volutamente prudente:
    evita di generare condizioni per stati banali come solo batteria/fermo.
    """

    if not mondo:
        return False, "mondo vuoto"

    testo = mondo.lower()

    elementi_utili = [
        "evento recente",
        "sento",
        "tocco",
        "carezza",
        "urto",
        "ostacolo",
        "qualcosa a sinistra",
        "qualcosa a destra",
        "volto",
        "riconosco",
        "sconosciuto",
        "interazione_utente"
    ]

    elementi_banali = [
        "la mia batteria",
        "sono fermo"
    ]

    ha_elemento_utile = any(e in testo for e in elementi_utili)

    solo_banale = True
    for parte in elementi_utili:
        if parte in testo:
            solo_banale = False
            break

    if not ha_elemento_utile:
        return False, "nessun evento utile"

    if solo_banale:
        return False, "situazione banale"

    eventi = stato_runtime.get("eventi", {})

    if isinstance(eventi, dict):
        if len(eventi.keys()) >= 2:
            return True, "eventi multipli rilevati"

    # Caso importante: piu' indizi nello stesso mondo
    indicatori_presenti = 0

    gruppi = [
        ["mano sinistra", "mano_sinistra"],
        ["mano destra", "mano_destra"],
        ["piede sinistro", "piede_sinistro"],
        ["piede destro", "piede_destro"],
        ["testa"],
        ["sinistra"],
        ["destra"],
        ["volto", "riconosco", "sconosciuto"],
        ["ostacolo", "qualcosa"]
    ]

    for gruppo in gruppi:
        if any(g in testo for g in gruppo):
            indicatori_presenti += 1

    if indicatori_presenti >= 2:
        return True, "situazione composta non banale"

    return False, "evento utile ma non abbastanza specifico"


def prova_generazione_autonoma(mondo, stato_runtime, motivo):
    """
    Prova a generare una nuova condizione tramite condition_generator.

    FASE C:
    - limita la frequenza di generazione
    - passa al generator i 4 argomenti corretti
    - non fa crashare soul.py
    - dopo la generazione rivaluta subito le condizioni
    """

    global ULTIMA_GENERAZIONE
    global ULTIMO_MONDO_GENERATO

    adesso = time.time()
    mondo_normalizzato = mondo.strip().lower()

    if ULTIMO_MONDO_GENERATO == mondo_normalizzato:
        logger.info("[AUTONOMIA] Generazione saltata: situazione gia' tentata")
        return None

    if adesso - ULTIMA_GENERAZIONE < INTERVALLO_MINIMO_GENERAZIONE:
        logger.info("[AUTONOMIA] Generazione saltata: troppo ravvicinata")
        return None

    ULTIMA_GENERAZIONE = adesso

    try:
        from behaviors import condition_generator

        logger.info("[AUTONOMIA] Provo generazione autonoma. Motivo: {}".format(motivo))

        if hasattr(condition_generator, "genera_condizione_autonoma"):
            dati_memoria = stato_runtime.get("memoria", {})
            stato_robot = stato_runtime.get("stato_robot", {})
            chiave_privata = (
                stato_runtime.get("openai_api_key")
                or os.environ.get("OPENAI_API_KEY")
            )
            
            ULTIMO_MONDO_GENERATO = mondo_normalizzato

            path_nuova_condizione = condition_generator.genera_condizione_autonoma(
                mondo,
                dati_memoria,
                stato_robot,
                chiave_privata
            )

            if path_nuova_condizione:
                logger.info("[AUTONOMIA] Nuova condizione generata: {}".format(
                    path_nuova_condizione
                ))
            else:
                logger.info("[AUTONOMIA] Nessuna nuova condizione generata")
                return None

        elif hasattr(condition_generator, "genera_condizione_da_mondo"):
            condition_generator.genera_condizione_da_mondo(mondo, stato_runtime)

        elif hasattr(condition_generator, "valuta_e_genera_condizione"):
            condition_generator.valuta_e_genera_condizione(mondo, stato_runtime)

        else:
            logger.warning("[AUTONOMIA] Nessuna funzione di generazione compatibile trovata")
            return None

        logger.info("[AUTONOMIA] Generazione completata, rivaluto condizioni")

        return valuta_condizioni_generate_sicure(mondo, stato_runtime)

    except Exception as e:
        logger.error("[AUTONOMIA] Errore durante generazione autonoma: {}".format(e))
        logger.error(traceback.format_exc())
        return None