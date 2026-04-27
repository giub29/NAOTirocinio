# -*- coding: utf-8 -*-
"""
Caricatore di condizioni Python generate.
"""

import os
import logging
import imp 

logger = logging.getLogger(__name__)

CONDIZIONI_DIR = os.path.join(os.path.dirname(__file__), "generated_conditions")

_condizioni_cache = None


def reset_cache_condizioni():
    global _condizioni_cache
    _condizioni_cache = None


def carica_condizioni_generate():
    global _condizioni_cache

    if _condizioni_cache is not None:
        return _condizioni_cache

    condizioni = []

    if not os.path.exists(CONDIZIONI_DIR):
        os.makedirs(CONDIZIONI_DIR)
        _condizioni_cache = condizioni
        return condizioni

    for nome_file in os.listdir(CONDIZIONI_DIR):
        if not nome_file.endswith(".py"):
            continue

        if nome_file == "__init__.py":
            continue

        path_file = os.path.join(CONDIZIONI_DIR, nome_file)
        nome_modulo = nome_file.replace(".py", "")

        try:
            modulo = imp.load_source(nome_modulo, path_file)

            if hasattr(modulo, "condizione") and hasattr(modulo, "comportamento"):
                condizioni.append({
                    "nome": nome_modulo,
                    "modulo": modulo
                })

                logger.info(u"[CONDIZIONI] Caricata condizione: {}".format(nome_modulo))

        except Exception as e:
            logger.warning(u"[CONDIZIONI] Errore caricamento {}: {}".format(nome_file, e))

    _condizioni_cache = condizioni
    return condizioni


def valuta_condizioni_generate(mondo, stato_runtime):
    condizioni = carica_condizioni_generate()

    for item in condizioni:
        nome = item["nome"]
        modulo = item["modulo"]

        try:
            if modulo.condizione(mondo, stato_runtime):
                logger.info(u"[CONDIZIONI] Attivata condizione generata: {}".format(nome))
                return modulo.comportamento()

        except Exception as e:
            logger.warning(u"[CONDIZIONI] Errore valutazione {}: {}".format(nome, e))

    return None