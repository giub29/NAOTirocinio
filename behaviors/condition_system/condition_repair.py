# -*- coding: utf-8 -*-
"""
Riparazione autonoma delle condizioni generate.
"""

import os
import time
import logging

logger = logging.getLogger(__name__)

_ultime_riparazioni = {}

COOLDOWN_RIPARAZIONE = 20


REPAIR_SUCCESS = "repair_success"
REPAIR_COOLDOWN = "repair_cooldown"
REPAIR_NO_API_KEY = "repair_no_api_key"
REPAIR_INVALID_API_KEY = "repair_invalid_api_key"
REPAIR_NO_WORLD = "repair_no_world"
REPAIR_VALIDATION_FAILED = "repair_validation_failed"
REPAIR_EXCEPTION = "repair_exception"


def _esito(success, status, reason=u"", new_path=None):
    return {
        "success": success,
        "status": status,
        "reason": reason,
        "new_path": new_path
    }


def _puo_riparare(nome_condizione):
    adesso = time.time()
    ultimo = _ultime_riparazioni.get(nome_condizione, 0)

    if adesso - ultimo < COOLDOWN_RIPARAZIONE:
        return False

    _ultime_riparazioni[nome_condizione] = adesso
    return True


def tenta_riparazione_condizione(nome_condizione, motivo, mondo=None, stato_runtime=None):
    """
    Prova a rigenerare automaticamente una condizione rifiutata.

    Ritorna sempre un dizionario:

    {
        "success": True/False,
        "status": "...",
        "reason": "...",
        "new_path": "..." oppure None
    }
    """

    try:
        if stato_runtime is None:
            stato_runtime = {}

        if nome_condizione.endswith(".py"):
            nome_condizione = nome_condizione[:-3]

        logger.warning(u"[REPAIR] START {} | motivo: {}".format(
            nome_condizione,
            motivo
        ))

        if not _puo_riparare(nome_condizione):
            reason = u"riparazione saltata per cooldown"
            logger.info(u"[REPAIR] COOLDOWN {} | {}".format(
                nome_condizione,
                reason
            ))
            return _esito(False, REPAIR_COOLDOWN, reason)

        chiave_api = (
            stato_runtime.get("openai_api_key") or
            os.getenv("OPENAI_API_KEY")
        )

        if not chiave_api:
            reason = u"OPENAI_API_KEY assente"
            logger.warning(u"[REPAIR] NO_API_KEY {} | {}".format(
                nome_condizione,
                reason
            ))
            return _esito(False, REPAIR_NO_API_KEY, reason)

        if not mondo:
            reason = u"mondo assente: impossibile ricostruire il contesto"
            logger.warning(u"[REPAIR] NO_WORLD {} | {}".format(
                nome_condizione,
                reason
            ))
            return _esito(False, REPAIR_NO_WORLD, reason)

        memoria = stato_runtime.get("memoria", {})
        stato_robot = stato_runtime.get("stato_robot", {})

        mondo_riparazione = (
            mondo +
            u" CONDIZIONE_RIFIUTATA: {}. MOTIVO_RIFIUTO: {}. "
            u"Genera una nuova condizione corretta, piu' coerente e sicura."
        ).format(
            nome_condizione,
            motivo
        )

        logger.warning(u"[REPAIR] GENERAZIONE {} | invio richiesta al generatore".format(
            nome_condizione
        ))

        from behaviors.condition_system.condition_generator import genera_condizione_autonoma

        nuova_condizione = genera_condizione_autonoma(
            mondo_riparazione,
            memoria,
            stato_robot,
            chiave_api
        )

        if nuova_condizione:
            logger.warning(u"[REPAIR] SUCCESS {} -> {}".format(
                nome_condizione,
                nuova_condizione
            ))
            return _esito(
                True,
                REPAIR_SUCCESS,
                u"condizione rigenerata e validata",
                nuova_condizione
            )

        reason = u"nessuna condizione valida generata dal generatore"
        logger.warning(u"[REPAIR] VALIDATION_FAILED {} | {}".format(
            nome_condizione,
            reason
        ))
        return _esito(False, REPAIR_VALIDATION_FAILED, reason)

    except Exception as e:
        reason = unicode(e) if "unicode" in globals() else str(e)
        if "invalid_api_key" in reason or "Incorrect API key" in reason:
            logger.warning(u"[REPAIR] INVALID_API_KEY {} | {}".format(
                nome_condizione,
                reason
            ))
            return _esito(False, REPAIR_INVALID_API_KEY, reason)

        logger.warning(u"[REPAIR] EXCEPTION {} | {}".format(
            nome_condizione,
            reason
        ))
        return _esito(False, REPAIR_EXCEPTION, reason)