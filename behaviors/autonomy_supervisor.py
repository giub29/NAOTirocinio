# -*- coding: utf-8 -*-
"""
Autonomy Supervisor

Modulo centrale per la gestione autonoma delle condizioni.

Responsabilità:
- valutare automaticamente le condizioni già generate;
- decidere se una situazione nuova merita una nuova condizione;
- generare autonomamente nuove condizioni tramite LLM;
- rivalutare subito le condizioni dopo la generazione;
- proteggere soul.py da errori del generator o del condition_manager;
- dare priorità agli eventi composti prima delle condizioni semplici.

Questo modulo è il punto di passaggio tra:
percezione → firma evento → condizione esistente/generazione → decisione.
"""

import logging
import traceback
import time
import os
import inspect

try:
    from behaviors.event_system.unknown_event_extractor import (
        estrai_eventi_sconosciuti
    )
except Exception:
    estrai_eventi_sconosciuti = None

try:
    from behaviors.event_system.structured_event import (
        costruisci_evento_strutturato as costruisci_evento_strutturato_layer
    )
except Exception:
    costruisci_evento_strutturato_layer = None

try:
    from behaviors.event_system.structured_event_policy import (
        decidi_da_evento_strutturato
    )
except Exception:
    decidi_da_evento_strutturato = None

try:
    from behaviors.event_system.structured_hypothesis_evaluator import (
        valuta_ipotesi_da_evento_strutturato
    )
except Exception:
    valuta_ipotesi_da_evento_strutturato = None

try:
    from behaviors.event_system.event_registry import arricchisci_eventi_registro
except Exception:
    arricchisci_eventi_registro = None

try:
    from behaviors.event_system.autonomous_curiosity_manager import (
        costruisci_decisione_curiosa
    )
except Exception:
    costruisci_decisione_curiosa = None

try:
    from behaviors.agentic_system.agentic_orchestrator import (
        esegui_ciclo_agentico
    )
except Exception:
    esegui_ciclo_agentico = None

try:
    from behaviors.condition_system.condition_memory import (
        trova_condizioni_simili,
        registra_feedback_osservazione_mirata
    )
except Exception:
    trova_condizioni_simili = None
    registra_feedback_osservazione_mirata = None

try:
    from behaviors.event_system.episodic_hypothesis_memory import (
        valuta_ipotesi_temporanee,
        costruisci_decisione_ipotesi,
        aggiorna_ipotesi_da_osservazione_mirata
    )
except Exception:
    valuta_ipotesi_temporanee = None
    costruisci_decisione_ipotesi = None
    aggiorna_ipotesi_da_osservazione_mirata = None

try:
    from behaviors.event_system.world_model_memory import (
        aggiorna_world_model,
        costruisci_decisione_world_model,
        aggiorna_world_model_da_osservazione_mirata
    )
except Exception:
    aggiorna_world_model = None
    costruisci_decisione_world_model = None
    aggiorna_world_model_da_osservazione_mirata = None

try:
    from behaviors.event_system.active_perception_planner import (
        costruisci_decisione_osservazione_mirata,
        valuta_risposta_osservazione_mirata,
        registra_osservazione_mirata_corrente
    )
except Exception:
    costruisci_decisione_osservazione_mirata = None
    valuta_risposta_osservazione_mirata = None
    registra_osservazione_mirata_corrente = (
        lambda stato_runtime, decisione: decisione
    )

try:
    from behaviors.agentic_system.goal_intent_memory import (
        valuta_goal_intent,
        costruisci_decisione_goal_intent,
        registra_revisione_piano_corrente,
        costruisci_decisione_azione_successiva,
        aggiorna_azione_successiva_da_osservazione
    )
except Exception:
    valuta_goal_intent = None
    costruisci_decisione_goal_intent = None
    registra_revisione_piano_corrente = (
        lambda stato_runtime, decisione: decisione
    )
    costruisci_decisione_azione_successiva = None
    aggiorna_azione_successiva_da_osservazione = None

from behaviors.event_system.unknown_generation_simulator import simula_condizione_sconosciuta

logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(__file__)
CONDIZIONI_GENERATE_DIR = os.path.join(
    BASE_DIR,
    "condition_system",
    "generated_conditions"
)
ULTIMA_GENERAZIONE = 0
INTERVALLO_MINIMO_GENERAZIONE = 20
ULTIMO_MONDO_GENERATO = None
EVENTI_HELPER_NON_GENERATIVI = [
    "interazione_utente"
]


def filtra_eventi_helper(eventi):
    if not isinstance(eventi, list):
        return []

    return [
        e for e in eventi
        if str(e).lower().strip() not in EVENTI_HELPER_NON_GENERATIVI
    ]


def integra_eventi_sconosciuti_in_evento_strutturato(
    evento_strutturato,
    eventi_sconosciuti
):
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if not isinstance(eventi_sconosciuti, list):
        eventi_sconosciuti = []

    tipo_attuale = str(evento_strutturato.get("tipo", "") or "").lower()
    if tipo_attuale in ["", "generico", "neutra"]:
        evento_strutturato["tipo"] = "unknown"

    categoria_attuale = str(
        evento_strutturato.get("categoria", "") or ""
    ).lower()
    if categoria_attuale in ["", "neutra"]:
        evento_strutturato["categoria"] = "sconosciuta"

    origine_attuale = str(
        evento_strutturato.get("origine", "") or ""
    ).lower()
    if origine_attuale in ["", "report"]:
        evento_strutturato["origine"] = "scoperta"

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_uniti = []
    for evento in eventi_core + eventi_sconosciuti:
        if evento in [None, False, "", [], {}]:
            continue

        if evento not in eventi_uniti:
            eventi_uniti.append(evento)

    evento_strutturato["eventi_core"] = eventi_uniti
    evento_strutturato["evento_composto"] = len(eventi_uniti) >= 2

    return evento_strutturato


def evento_strutturato_va_ricostruito(evento_strutturato, mondo):
    if not isinstance(evento_strutturato, dict):
        return True

    if not evento_strutturato:
        return True

    testo_originale = evento_strutturato.get("testo_originale")
    if testo_originale and mondo and testo_originale != mondo:
        return True

    categoria = str(evento_strutturato.get("categoria", "") or "").lower()
    tipo = str(evento_strutturato.get("tipo", "") or "").lower()
    eventi_core = evento_strutturato.get("eventi_core", [])

    if not isinstance(eventi_core, list):
        eventi_core = []

    return (
        categoria in ["", "neutra"]
        and tipo in ["", "generico", "neutra"]
        and len(eventi_core) == 0
    )


def salva_ipotesi_temporanea_da_decisione(stato_runtime, decisione):
    if stato_runtime is None or not isinstance(decisione, dict):
        return None

    ipotesi = decisione.get("ipotesi_temporanea")
    if not isinstance(ipotesi, dict):
        return None

    stato_runtime["ipotesi_temporanea"] = ipotesi

    recenti = stato_runtime.get("ipotesi_temporanee_recenti", [])
    if not isinstance(recenti, list):
        recenti = []

    recenti.append(ipotesi)
    stato_runtime["ipotesi_temporanee_recenti"] = recenti[-5:]

    return ipotesi


def archivia_ipotesi_strutturata(stato_runtime, esito, motivo=None):
    if stato_runtime is None:
        return None

    ipotesi = stato_runtime.get("ipotesi_temporanea")
    if not isinstance(ipotesi, dict):
        stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
        stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)
        return None

    archiviata = dict(ipotesi)
    archiviata["esito_finale"] = esito
    archiviata["motivo_finale"] = motivo
    archiviata["chiusa"] = True

    archivio = stato_runtime.get("ipotesi_strutturate_archiviate", [])
    if not isinstance(archivio, list):
        archivio = []

    archivio.append(archiviata)
    stato_runtime["ipotesi_strutturate_archiviate"] = archivio[-10:]

    stato_runtime.pop("ipotesi_temporanea", None)
    stato_runtime.pop("forza_generazione_da_ipotesi_strutturata", None)
    stato_runtime.pop("motivo_generazione_ipotesi_strutturata", None)

    return archiviata


def valuta_ipotesi_strutturata_sicura(stato_runtime, evento_strutturato, mondo):
    if stato_runtime is None:
        return None

    ipotesi = stato_runtime.get("ipotesi_temporanea")
    if not isinstance(ipotesi, dict):
        return None

    if valuta_ipotesi_da_evento_strutturato is None:
        return None

    try:
        valutazione = valuta_ipotesi_da_evento_strutturato(
            ipotesi,
            evento_strutturato,
            nuovo_mondo=mondo
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore valutando ipotesi strutturata: {}".format(e)
        )
        return None

    if not isinstance(valutazione, dict):
        return None

    stato_runtime["valutazione_ipotesi_strutturata"] = valutazione

    ipotesi_aggiornata = valutazione.get("ipotesi")
    if isinstance(ipotesi_aggiornata, dict):
        stato_runtime["ipotesi_temporanea"] = ipotesi_aggiornata

    if valutazione.get("stato") in ["smentita", "scaduta"]:
        archivia_ipotesi_strutturata(
            stato_runtime,
            valutazione.get("stato"),
            valutazione.get("motivo")
        )
        return valutazione

    if (
        valutazione.get("stato") == "confermata"
        and valutazione.get("genera_condizione") is True
    ):
        stato_runtime["forza_generazione_da_ipotesi_strutturata"] = True
        stato_runtime["motivo_generazione_ipotesi_strutturata"] = (
            valutazione.get(
                "motivo",
                "ipotesi strutturata confermata"
            )
        )

    return valutazione


def aggiorna_world_model_sicuro(mondo, firma, stato_runtime):
    if stato_runtime is None:
        stato_runtime = {}

    if aggiorna_world_model is None:
        return {
            "aggiornato": False,
            "motivo": "world model non disponibile"
        }

    try:
        esito = aggiorna_world_model(
            mondo,
            firma,
            stato_runtime
        )
        stato_runtime["world_model"] = esito
        return esito
    except Exception as e:
        logger.warning("[AUTONOMIA] Errore world model: {}".format(e))
        return {
            "aggiornato": False,
            "motivo": "errore world model"
        }


def costruisci_osservazione_mirata_sicura(
    mondo,
    azione_cognitiva=None,
    motivo=None,
    ipotesi=None,
    world_model=None,
    ragionamento=None,
    firma=None
):
    if costruisci_decisione_osservazione_mirata is None:
        return None

    try:
        return costruisci_decisione_osservazione_mirata(
            mondo=mondo,
            azione_cognitiva=azione_cognitiva,
            motivo=motivo,
            ipotesi=ipotesi,
            world_model=world_model,
            ragionamento=ragionamento,
            firma=firma
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore osservazione mirata: {}".format(e)
        )
        return None


def valuta_osservazione_mirata_corrente_sicura(
    mondo,
    firma,
    stato_runtime,
    world_model=None
):
    if stato_runtime is None:
        return None

    piano = stato_runtime.get("osservazione_mirata_corrente")
    if not isinstance(piano, dict):
        return None

    if valuta_risposta_osservazione_mirata is None:
        return None

    try:
        esito = valuta_risposta_osservazione_mirata(
            mondo,
            piano,
            firma=firma,
            world_model=world_model
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore valutando risposta osservazione mirata: {}".format(e)
        )
        return None

    if not isinstance(esito, dict):
        return None

    tentativi = int(piano.get("tentativi", 0)) + 1
    piano["tentativi"] = tentativi

    esito["tentativo"] = tentativi
    stato_runtime["esito_osservazione_mirata"] = esito
    aggiorna_ipotesi_da_osservazione_mirata_sicura(
        esito,
        stato_runtime
    )
    aggiorna_world_model_da_osservazione_mirata_sicura(
        esito,
        stato_runtime
    )
    aggiorna_azione_successiva_sicura(
        esito,
        stato_runtime
    )
    condizioni_aggiornate = registra_feedback_condizioni_sicuro(
        esito,
        stato_runtime
    )
    if condizioni_aggiornate:
        stato_runtime["condizioni_feedback_osservazione_mirata"] = (
            condizioni_aggiornate
        )

    storia = stato_runtime.get("esiti_osservazioni_mirate", [])
    if not isinstance(storia, list):
        storia = []

    storia.append(esito)
    stato_runtime["esiti_osservazioni_mirate"] = storia[-5:]

    if esito.get("trovato") or tentativi >= 3:
        piano["stato"] = "completata" if esito.get("trovato") else "scaduta"
        stato_runtime.pop("osservazione_mirata_corrente", None)
    else:
        stato_runtime["osservazione_mirata_corrente"] = piano

    logger.info(
        "[AUTONOMIA] Esito osservazione mirata: {}".format(esito)
    )

    return esito


def aggiorna_ipotesi_da_osservazione_mirata_sicura(esito, stato_runtime):
    if aggiorna_ipotesi_da_osservazione_mirata is None:
        return None

    try:
        return aggiorna_ipotesi_da_osservazione_mirata(
            esito,
            stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando ipotesi da osservazione: {}".format(e)
        )
        return None


def aggiorna_world_model_da_osservazione_mirata_sicura(esito, stato_runtime):
    if aggiorna_world_model_da_osservazione_mirata is None:
        return None

    try:
        return aggiorna_world_model_da_osservazione_mirata(
            esito,
            stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando world model da osservazione: {}".format(e)
        )
        return None


def aggiorna_azione_successiva_sicura(esito, stato_runtime):
    if aggiorna_azione_successiva_da_osservazione is None:
        return None

    try:
        return aggiorna_azione_successiva_da_osservazione(
            esito,
            stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando azione successiva: {}".format(e)
        )
        return None


def registra_feedback_condizioni_sicuro(esito, stato_runtime):
    if registra_feedback_osservazione_mirata is None:
        return []

    try:
        return registra_feedback_osservazione_mirata(
            esito,
            stato_runtime=stato_runtime
        )
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore aggiornando memoria condizioni da osservazione: {}".format(e)
        )
        return []


def valuta_goal_intent_sicuro(mondo, firma, stato_runtime, world_model=None):
    if valuta_goal_intent is None:
        return {
            "goal_attivo": False,
            "motivo": "goal intent memory non disponibile"
        }

    try:
        esito = valuta_goal_intent(
            mondo,
            firma=firma,
            stato_runtime=stato_runtime,
            world_model=world_model
        )

        if isinstance(esito, dict):
            stato_runtime["goal_intent"] = esito

        return esito
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore goal/intent reasoning: {}".format(e)
        )
        return {
            "goal_attivo": False,
            "motivo": "errore goal intent"
        }


def costruisci_decisione_goal_sicura(esito_goal):
    if costruisci_decisione_goal_intent is None:
        return None

    try:
        return costruisci_decisione_goal_intent(esito_goal)
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore decisione goal/intent: {}".format(e)
        )
        return None


def costruisci_decisione_azione_successiva_sicura(stato_runtime):
    if costruisci_decisione_azione_successiva is None:
        return None

    try:
        return costruisci_decisione_azione_successiva(stato_runtime)
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore costruendo azione successiva: {}".format(e)
        )
        return None


def _generatore_supporta_storia_episodica(funzione_generatore):
    try:
        if hasattr(inspect, "getfullargspec"):
            specifica = inspect.getfullargspec(funzione_generatore)
            argomenti = specifica.args
            keywords = specifica.varkw
        else:
            specifica = inspect.getargspec(funzione_generatore)
            argomenti = specifica.args
            keywords = specifica.keywords

        if "storia_episodica" in argomenti:
            return True
        if keywords is not None:
            return True
        return False
    except Exception:
        return True


def chiama_genera_condizione_autonoma_sicura(
    funzione_generatore,
    mondo,
    dati_memoria,
    stato_robot,
    chiave_privata,
    storia_episodica=None
):
    if _generatore_supporta_storia_episodica(funzione_generatore):
        return funzione_generatore(
            mondo,
            dati_memoria,
            stato_robot,
            chiave_privata,
            storia_episodica=storia_episodica
        )

    logger.warning(
        "[AUTONOMIA] Generator senza parametro storia_episodica: uso chiamata legacy"
    )
    return funzione_generatore(
        mondo,
        dati_memoria,
        stato_robot,
        chiave_privata
    )


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

    try:
        evento_strutturato = stato_runtime.get("evento_strutturato", {})
        if (
            costruisci_evento_strutturato_layer is not None
            and evento_strutturato_va_ricostruito(
                evento_strutturato,
                mondo
            )
        ):
            evento_strutturato = costruisci_evento_strutturato_layer(
                mondo,
                stato_runtime
            )
            stato_runtime["evento_strutturato"] = evento_strutturato

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore costruendo evento strutturato: {}".format(e)
        )

    if stato_runtime.get("usa_agentic_orchestrator", False):
        if esegui_ciclo_agentico is not None:
            logger.info("[AUTONOMIA] Uso orchestratore agentico")

            return esegui_ciclo_agentico(
                mondo,
                stato_runtime,
                costruisci_firma_situazione,
                valuta_condizioni_generate_sicure,
                situazione_merita_generazione,
                prova_generazione_autonoma,
                costruisci_decisione_curiosa,
                _pulisci_mondo_per_unknown
            )

    firma = costruisci_firma_situazione(mondo, stato_runtime)
    esito_world_model = aggiorna_world_model_sicuro(
        mondo,
        firma,
        stato_runtime
    )
    valuta_osservazione_mirata_corrente_sicura(
        mondo,
        firma,
        stato_runtime,
        world_model=esito_world_model
    )

    try:
        stato_runtime["eventi"] = firma.get("eventi", {})
        stato_runtime["eventi_reali"] = firma.get("eventi_attivi", {})

        eventi_descritti = firma.get("eventi_descritti", {})
        eventi_sconosciuti = [
            nome
            for nome, dati in eventi_descritti.items()
            if not dati.get("conosciuto", True)
        ]

        eventi_sconosciuti = filtra_eventi_helper(eventi_sconosciuti)

        if eventi_sconosciuti:
            stato_runtime["evento_strutturato"] = (
                integra_eventi_sconosciuti_in_evento_strutturato(
                    stato_runtime.get("evento_strutturato", {}),
                    eventi_sconosciuti
                )
            )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore propagando firma nel runtime: {}".format(e)
        )

    logger.info("[AUTONOMIA] Firma situazione: {}".format(firma))

    if "eventi" not in stato_runtime:
        stato_runtime["eventi"] = firma.get("eventi", {})

    if "eventi_reali" not in stato_runtime:
        stato_runtime["eventi_reali"] = firma.get("eventi_attivi", {})

    # EVENTI UNKNOWN:
    # propago TUTTI gli eventi attivi della firma dentro stato_runtime["eventi"],
    # inclusi quelli scoperti autonomamente.
    try:
        stato_runtime.setdefault("eventi", {})

        eventi_attivi_firma = firma.get("eventi_attivi", {})

        if isinstance(eventi_attivi_firma, dict):
            for nome_evento, valore in eventi_attivi_firma.items():
                if valore not in [False, None, "", [], {}]:
                    stato_runtime["eventi"][nome_evento] = True

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore propagando eventi_attivi nel runtime: {}".format(e)
        )

    valutazione_ipotesi_strutturata = valuta_ipotesi_strutturata_sicura(
        stato_runtime,
        stato_runtime.get("evento_strutturato", {}),
        mondo
    )

    if stato_runtime.get("forza_generazione_da_ipotesi_strutturata", False):
        motivo_ipotesi_strutturata = stato_runtime.get(
            "motivo_generazione_ipotesi_strutturata",
            "ipotesi strutturata confermata"
        )
        nuova_decisione = prova_generazione_autonoma(
            mondo,
            stato_runtime,
            motivo_ipotesi_strutturata
        )
        archivia_ipotesi_strutturata(
            stato_runtime,
            "generata" if nuova_decisione is not None else "generazione_fallita",
            motivo_ipotesi_strutturata
        )

        if nuova_decisione is not None:
            logger.info(
                "[AUTONOMIA] Decisione ottenuta da ipotesi strutturata"
            )
            return nuova_decisione

    try:
        valutazione_strutturata = stato_runtime.get(
            "valutazione_ipotesi_strutturata",
            {}
        )
        if not isinstance(valutazione_strutturata, dict):
            valutazione_strutturata = {}

        if (
            decidi_da_evento_strutturato is not None
            and not stato_runtime.get(
                "forza_generazione_da_ipotesi_strutturata",
                False
            )
            and valutazione_strutturata.get("stato") not in [
                "confermata",
                "smentita",
                "scaduta"
            ]
        ):
            decisione_evento_strutturato = (
                decidi_da_evento_strutturato(
                    stato_runtime.get("evento_strutturato", {}),
                    mondo=mondo,
                    stato_runtime=stato_runtime
                )
            )

            if decisione_evento_strutturato is not None:
                logger.info("[AUTONOMIA] Decisione da evento strutturato")
                salva_ipotesi_temporanea_da_decisione(
                    stato_runtime,
                    decisione_evento_strutturato
                )
                return registra_osservazione_mirata_corrente(
                    stato_runtime,
                    decisione_evento_strutturato
                )

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore policy evento strutturato: {}".format(e)
        )

    decisione_azione_successiva = (
        costruisci_decisione_azione_successiva_sicura(
            stato_runtime
        )
    )

    if decisione_azione_successiva is not None:
        logger.info("[AUTONOMIA] Decisione da azione successiva suggerita")
        return registra_osservazione_mirata_corrente(
            stato_runtime,
            decisione_azione_successiva
        )

    esito_goal = valuta_goal_intent_sicuro(
        mondo,
        firma,
        stato_runtime,
        world_model=esito_world_model
    )
    decisione_goal = costruisci_decisione_goal_sicura(esito_goal)

    if decisione_goal is not None:
        logger.info("[AUTONOMIA] Decisione da goal/intent reasoning")
        registra_revisione_piano_corrente(
            stato_runtime,
            decisione_goal
        )
        return registra_osservazione_mirata_corrente(
            stato_runtime,
            decisione_goal
        )

    if stato_runtime.get("forza_generazione_safety", False):
        motivo_safety = stato_runtime.get(
            "motivo_safety",
            "evento safety prioritario"
        )

        logger.warning("[AUTONOMIA] Generazione safety richiesta: {}".format(
            motivo_safety
        ))

        nuova_decisione = prova_generazione_autonoma(
            mondo,
            stato_runtime,
            "safety: {}".format(motivo_safety)
        )

        if nuova_decisione is not None:
            logger.info("[AUTONOMIA] Decisione ottenuta dopo generazione safety")
            return nuova_decisione

        logger.info("[AUTONOMIA] Generazione safety non riuscita: provo condizioni esistenti")

        decisione = valuta_condizioni_generate_sicure(
            mondo,
            stato_runtime
        )

        if decisione is not None:
            return decisione

        return None

    eventi_reali = stato_runtime.get("eventi_reali", {})
    eventi_attivi = list(firma.get("eventi_attivi", {}).keys())

    eventi_reali_generativi = [
        k for k, v in eventi_reali.items()
        if v not in [False, None, "", [], {}]
        and str(k).lower().strip() != "interazione_utente"
    ]

    numero_eventi_reali = len(eventi_reali_generativi)

    eventi_attivi_generativi = [
        e for e in eventi_attivi
        if str(e).lower().strip() != "interazione_utente"
    ]

    evento_composto = (
        len(eventi_attivi_generativi) >= 2
    )

    # CASO SPECIALE:
    # se la situazione e' composta, proviamo prima a generare/imparare
    # la condizione composta. Altrimenti una condizione semplice gia'
    # esistente potrebbe intercettare l'evento e impedire l'apprendimento.
    if evento_composto:
        logger.info("[AUTONOMIA] Evento composto: priorita' alla generazione autonoma")

        esito_ipotesi = valuta_ipotesi_temporanee_sicura(
            mondo,
            firma,
            stato_runtime
        )

        if esito_ipotesi.get("ha_ipotesi") and not esito_ipotesi.get("genera_condizione"):
            decisione_ipotesi = None

            decisione_mirata = costruisci_osservazione_mirata_sicura(
                mondo,
                azione_cognitiva=esito_ipotesi.get("azione_temporanea"),
                motivo=esito_ipotesi.get("motivo"),
                ipotesi=esito_ipotesi.get("ipotesi"),
                world_model=esito_world_model,
                firma=firma
            )

            if decisione_mirata is not None:
                logger.info(
                    "[AUTONOMIA] Decisione da osservazione mirata composta"
                )
                return registra_osservazione_mirata_corrente(
                    stato_runtime,
                    decisione_mirata
                )

            if costruisci_decisione_ipotesi is not None:
                decisione_ipotesi = costruisci_decisione_ipotesi(esito_ipotesi)

            if decisione_ipotesi is not None:
                logger.info("[AUTONOMIA] Decisione da ipotesi temporanea composta")
                return decisione_ipotesi

        deve_generare, motivo = situazione_merita_generazione(mondo, stato_runtime)

        if esito_ipotesi.get("genera_condizione"):
            deve_generare = True
            motivo = esito_ipotesi.get(
                "motivo",
                "ipotesi temporanea confermata"
            )

        logger.info("[AUTONOMIA] Valutazione generazione autonoma: {} - {}".format(
            deve_generare,
            motivo
        ))

        if deve_generare:
            generazione_da_ipotesi_strutturata = stato_runtime.get(
                "forza_generazione_da_ipotesi_strutturata",
                False
            )
            nuova_decisione = prova_generazione_autonoma(
                mondo,
                stato_runtime,
                "evento composto prioritario: {}".format(motivo)
            )

            if generazione_da_ipotesi_strutturata:
                archivia_ipotesi_strutturata(
                    stato_runtime,
                    "generata" if nuova_decisione is not None else "generazione_fallita",
                    motivo
                )

            if nuova_decisione is not None:
                logger.info("[AUTONOMIA] Decisione ottenuta dopo generazione autonoma composta")
                return nuova_decisione

        logger.info("[AUTONOMIA] Generazione composta non riuscita: provo condizioni esistenti")

        decisione = valuta_condizioni_generate_sicure(mondo, stato_runtime)

        if decisione is not None:
            logger.info("[AUTONOMIA] Decisione ottenuta da condizione generata esistente")
            return decisione

        return None

    # CASO NORMALE:
    # per situazioni semplici, prima uso condizioni gia' generate.
    decisione = valuta_condizioni_generate_sicure(mondo, stato_runtime)

    if decisione is not None:
        logger.info("[AUTONOMIA] Decisione ottenuta da condizione generata")
        return decisione

    logger.info("[AUTONOMIA] Nessuna condizione autonoma applicabile")

    esito_ipotesi = valuta_ipotesi_temporanee_sicura(
        mondo,
        firma,
        stato_runtime
    )

    if esito_ipotesi.get("ha_ipotesi") and not esito_ipotesi.get("genera_condizione"):
        decisione_ipotesi = None

        if (
            esito_world_model.get("familiare")
            and not esito_world_model.get("anomalia")
            and costruisci_decisione_world_model is not None
        ):
            decisione_world = costruisci_decisione_world_model(
                esito_world_model
            )

            if decisione_world is not None:
                logger.info("[AUTONOMIA] Decisione da world model stabile")
                return decisione_world

        decisione_mirata = costruisci_osservazione_mirata_sicura(
            mondo,
            azione_cognitiva=esito_ipotesi.get("azione_temporanea"),
            motivo=esito_ipotesi.get("motivo"),
            ipotesi=esito_ipotesi.get("ipotesi"),
            world_model=esito_world_model,
            firma=firma
        )

        if decisione_mirata is not None:
            logger.info("[AUTONOMIA] Decisione da osservazione mirata")
            return registra_osservazione_mirata_corrente(
                stato_runtime,
                decisione_mirata
            )

        if costruisci_decisione_ipotesi is not None:
            decisione_ipotesi = costruisci_decisione_ipotesi(esito_ipotesi)

        if decisione_ipotesi is not None:
            logger.info("[AUTONOMIA] Decisione da ipotesi temporanea")
            return decisione_ipotesi
    
    # Curiosità epistemica:
    # se non ci sono condizioni attive e la scena non merita ancora
    # una condizione permanente, NAO può decidere di osservare meglio.
    try:
        if costruisci_decisione_curiosa is not None:

            mondo_unknown = _pulisci_mondo_per_unknown(
                mondo
            )

            logger.info(
                u"[AUTONOMIA][UNKNOWN] mondo_unknown={}".format(
                    mondo_unknown
                )
            )

            decisione_curiosa = (
                costruisci_decisione_curiosa(
                    mondo_unknown
                )
            )

            logger.info(
                u"[AUTONOMIA][UNKNOWN] decisione_curiosa={}".format(
                    decisione_curiosa
                )
            )

            # Politica: osserva con prudenza
            try:
                from behaviors.event_system.unknown_situation_reasoner import (
                    ragiona_situazione_sconosciuta
                )

                ragionamento = ragiona_situazione_sconosciuta(
                    mondo_unknown
                )

                decisione_mirata = None
                if ragionamento is not None:
                    decisione_mirata = costruisci_osservazione_mirata_sicura(
                        mondo,
                        azione_cognitiva=ragionamento.get("azione_cognitiva"),
                        motivo=ragionamento.get("ipotesi"),
                        world_model=esito_world_model,
                        ragionamento=ragionamento,
                        firma=firma
                    )

                if decisione_mirata is not None:
                    logger.info(
                        "[AUTONOMIA] Decisione curiosa da osservazione mirata"
                    )
                    return registra_osservazione_mirata_corrente(
                        stato_runtime,
                        decisione_mirata
                    )

                if (
                    ragionamento is not None
                    and ragionamento.get("azione_cognitiva")
                    == "osserva_con_prudenza"
                ):
                    return {
                        "stato_interno": "prudente",
                        "obiettivo":
                            "valutare un elemento vicino a una zona rilevante",
                        "azioni": [
                            {
                                "tipo": "occhi",
                                "colore": "yellow"
                            },
                            {
                                "tipo": "guarda",
                                "x": 0.0,
                                "y": -0.25
                            },
                            {
                                "tipo": "parla",
                                "testo": (
                                    "Ho notato qualcosa vicino "
                                    "a una zona importante. "
                                    "Lo osservo con prudenza "
                                    "prima di decidere."
                                )
                            }
                        ],
                        "memoria": [
                            {
                                "tipo": "politica_agentica",
                                "azione":
                                    "osserva_con_prudenza",
                                "motivo":
                                    ragionamento.get(
                                        "ipotesi",
                                        "elemento vicino "
                                        "a una zona rilevante"
                                    )
                            }
                        ]
                    }

            except Exception as e:
                logger.warning(
                    "[AUTONOMIA] Errore politica prudenza: {}".format(e)
                )

            if decisione_curiosa is not None:
                logger.info(
                    "[AUTONOMIA] Decisione curiosa autonoma senza generare condizione"
                )
                return decisione_curiosa

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore curiosita epistemica: {}".format(
                e
            )
        )

    deve_generare, motivo = situazione_merita_generazione(
        mondo,
        stato_runtime
    )

    if esito_ipotesi.get("genera_condizione"):
        deve_generare = True
        motivo = esito_ipotesi.get(
            "motivo",
            "ipotesi temporanea confermata"
        )

    logger.info(
        "[AUTONOMIA] Valutazione generazione autonoma: {} - {}".format(
            deve_generare,
            motivo
        )
    )

    if deve_generare:
        generazione_da_ipotesi_strutturata = stato_runtime.get(
            "forza_generazione_da_ipotesi_strutturata",
            False
        )
        nuova_decisione = prova_generazione_autonoma(mondo, stato_runtime, motivo)

        if generazione_da_ipotesi_strutturata:
            archivia_ipotesi_strutturata(
                stato_runtime,
                "generata" if nuova_decisione is not None else "generazione_fallita",
                motivo
            )

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
        import behaviors.condition_system.condition_manager as condition_manager

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


def _eventi_per_memoria_cognitiva(firma, stato_runtime):
    eventi = {}

    for sorgente in [
        firma.get("eventi", {}),
        firma.get("eventi_attivi", {}),
        stato_runtime.get("eventi", {}),
        stato_runtime.get("eventi_reali", {})
    ]:
        if not isinstance(sorgente, dict):
            continue

        for nome_evento, valore in sorgente.items():
            if valore not in [False, None, "", [], {}]:
                eventi[nome_evento] = True

    evento_strutturato = firma.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    for nome_evento in eventi_core:
        nome_evento = str(nome_evento).strip()
        if nome_evento:
            eventi[nome_evento] = True

    return eventi


def _condizione_memoria_eseguibile(voce):
    nome = voce.get("nome", "")

    if not nome:
        return False

    if nome.endswith(".py"):
        nome = nome[:-3]

    path_file = os.path.join(CONDIZIONI_GENERATE_DIR, nome + ".py")

    return os.path.exists(path_file)


def _evento_coperto_da_voce(evento, voce):
    evento_norm = str(evento).lower().replace("-", "_").strip()

    if not evento_norm:
        return False

    testi_voce = [
        voce.get("nome", ""),
        voce.get("contesto_semantico", "")
    ]

    for evento_voce in voce.get("eventi_attivi_origine", []):
        testi_voce.append(str(evento_voce))

    testo_voce = " ".join(testi_voce).lower().replace("-", "_")

    if evento_norm in testo_voce:
        return True

    pezzi = [
        pezzo.strip()
        for pezzo in evento_norm.split("_")
        if len(pezzo.strip()) >= 4
    ]

    for pezzo in pezzi:
        if pezzo in testo_voce:
            return True

    return False


def _numero_eventi_coperti_da_voce(firma, stato_runtime, voce):
    eventi = _eventi_per_memoria_cognitiva(firma, stato_runtime)
    coperti = 0

    for nome_evento in eventi.keys():
        nome_norm = str(nome_evento).lower().strip()

        if nome_norm in [
            "fermo",
            "interazione_utente"
        ]:
            continue

        if _evento_coperto_da_voce(nome_evento, voce):
            coperti += 1

    return coperti


def _generazione_gia_coperta_da_memoria(mondo, firma, stato_runtime):
    """
    Recupera condizioni simili prima di arrivare al prompt LLM.

    Il filtro e' conservativo: blocca la generazione solo quando la memoria
    contiene una condizione molto vicina e non chiaramente fragile.
    """

    if trova_condizioni_simili is None:
        return False, "", []

    try:
        eventi = _eventi_per_memoria_cognitiva(firma, stato_runtime)
        simili = trova_condizioni_simili(mondo, eventi, limite=5)
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore recuperando condizioni simili: {}".format(e)
        )
        return False, "", []

    if not simili:
        return False, "", []

    simili_eseguibili = [
        voce for voce in simili
        if _condizione_memoria_eseguibile(voce)
    ]

    if not simili_eseguibili:
        return False, "", simili

    stato_runtime["condizioni_simili_richiamate"] = simili

    scena_composta = (
        firma.get("eventi_multipli", False)
        or firma.get("situazione_composta", False)
    )

    for voce in simili_eseguibili:
        punteggio = voce.get("punteggio_similarita", 0)
        positivi = voce.get("numero_esempi_positivi", 0)
        negativi = voce.get("numero_esempi_negativi", 0)
        motivi = voce.get("motivi_similarita", [])

        eventi_match = [
            motivo for motivo in motivi
            if str(motivo).startswith("evento:")
        ]

        testo_match = [
            motivo for motivo in motivi
            if str(motivo).startswith("testo:")
        ]

        if negativi > positivi and negativi >= 2:
            continue

        if scena_composta:
            eventi_coperti = _numero_eventi_coperti_da_voce(
                firma,
                stato_runtime,
                voce
            )

            if eventi_coperti < 2:
                continue

        if punteggio >= 11:
            return True, (
                "condizione simile gia' appresa: {} (punteggio {})"
                .format(voce.get("nome", "sconosciuta"), punteggio)
            ), simili

        if punteggio >= 8 and eventi_match and testo_match:
            return True, (
                "condizione simile recuperata dalla memoria: {}"
                .format(voce.get("nome", "sconosciuta"))
            ), simili

        if punteggio >= 7 and eventi_match and positivi >= 2 and negativi == 0:
            return True, (
                "condizione simile affidabile gia' presente: {}"
                .format(voce.get("nome", "sconosciuta"))
            ), simili

    return False, "", simili


def valuta_ipotesi_temporanee_sicura(mondo, firma, stato_runtime):
    if stato_runtime is None:
        stato_runtime = {}

    cache = stato_runtime.get("_esito_ipotesi_temporanea")

    if isinstance(cache, dict) and cache.get("mondo") == mondo:
        return cache.get("esito", {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "ipotesi temporanea non disponibile"
        })

    if valuta_ipotesi_temporanee is None:
        return {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "memoria ipotesi temporanee non disponibile"
        }

    try:
        esito = valuta_ipotesi_temporanee(
            mondo,
            firma,
            stato_runtime
        )
        stato_runtime["_esito_ipotesi_temporanea"] = {
            "mondo": mondo,
            "esito": esito
        }
        return esito
    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore memoria ipotesi temporanee: {}".format(e)
        )
        return {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "errore memoria ipotesi temporanee"
        }
    
def situazione_merita_generazione(mondo, stato_runtime):
    """
    Decide se la situazione osservata merita una nuova condizione autonoma.

    Versione finale:
    - gli eventi unknown/scoperta devono poter generare davvero;
    - non dipende piu' dal flag abilita_generazione_eventi_sconosciuti;
    - mantiene i filtri contro mondo vuoto, banale e gia' tentato.
    """

    firma = costruisci_firma_situazione(mondo, stato_runtime)
    logger.info("[AUTONOMIA] Firma situazione: {}".format(firma))

    if stato_runtime.get("forza_generazione_da_ipotesi_strutturata", False):
        return True, stato_runtime.get(
            "motivo_generazione_ipotesi_strutturata",
            "ipotesi strutturata confermata"
        )

    if firma["mondo_vuoto"]:
        return False, "mondo vuoto"

    if firma["gia_tentata"]:
        return False, "situazione gia' tentata"

    if firma["banale"]:
        return False, "situazione banale"

    evento_strutturato = firma.get("evento_strutturato", {})
    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    tipo = str(evento_strutturato.get("tipo", "")).lower()
    categoria = str(evento_strutturato.get("categoria", "")).lower()
    origine = str(evento_strutturato.get("origine", "")).lower()

    eventi_core = firma.get("eventi_core", [])

        # Propago SEMPRE tutti gli eventi attivi della firma
    # dentro stato_runtime["eventi"], inclusi gli unknown.
    try:
        stato_runtime.setdefault("eventi", {})

        eventi_attivi_firma = firma.get("eventi_attivi", {})

        if isinstance(eventi_attivi_firma, dict):
            for nome_evento, valore in eventi_attivi_firma.items():
                if valore not in [False, None, "", [], {}]:
                    stato_runtime["eventi"][nome_evento] = True

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore propagando eventi_attivi nel runtime: {}".format(e)
        )

    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = filtra_eventi_helper(eventi_core)

    gia_coperta, motivo_memoria, condizioni_simili = (
        _generazione_gia_coperta_da_memoria(
            mondo,
            firma,
            stato_runtime
        )
    )

    if condizioni_simili:
        logger.info(
            "[AUTONOMIA][MEMORIA] Condizioni simili richiamate: {}".format(
                [
                    (
                        voce.get("nome"),
                        voce.get("punteggio_similarita")
                    )
                    for voce in condizioni_simili[:3]
                ]
            )
        )

    if gia_coperta:
        logger.info(
            "[AUTONOMIA][MEMORIA] Generazione evitata: {}".format(
                motivo_memoria
            )
        )
        return False, motivo_memoria

    esito_ipotesi = valuta_ipotesi_temporanee_sicura(
        mondo,
        firma,
        stato_runtime
    )

    if esito_ipotesi.get("ha_ipotesi"):
        if esito_ipotesi.get("genera_condizione"):
            return True, esito_ipotesi.get(
                "motivo",
                "ipotesi temporanea confermata"
            )

        return False, esito_ipotesi.get(
            "motivo",
            "ipotesi temporanea ancora debole"
        )

    esito_world_model = stato_runtime.get("world_model", {})
    if (
        isinstance(esito_world_model, dict)
        and esito_world_model.get("familiare")
        and not esito_world_model.get("anomalia")
    ):
        return False, "situazione gia' familiare nel world model"

    if (
        tipo in ["unknown", "sconosciuto", "scoperta"]
        or categoria in ["unknown", "sconosciuta", "scoperta"]
        or origine in ["unknown", "scoperta"]
    ):
        if len(eventi_core) > 0:
            return True, "evento sconosciuto/scoperta valido"

        return False, "evento sconosciuto senza eventi_core"

    if firma["eventi_multipli"]:
        return True, "eventi multipli rilevati"

    if firma["situazione_composta"]:
        return True, "situazione composta non banale"

    if firma["ha_novita_runtime"]:
        eventi_descritti = firma.get("eventi_descritti", {})

        eventi_sconosciuti = [
            nome
            for nome, dati in eventi_descritti.items()
            if not dati.get("conosciuto", True)
        ]

        if eventi_sconosciuti:
            return True, "eventi sconosciuti rilevati: {}".format(
                ", ".join(eventi_sconosciuti)
            )

        return True, "novita' runtime non ancora coperta"

    if firma["ha_testo_sensoriale_non_banale"]:
        if len(firma.get("eventi_attivi", {}).keys()) == 0:
            return False, "situazione sensoriale osservata ma senza eventi attivi"

        return True, "situazione sensoriale non banale"

    return False, "situazione non abbastanza significativa"

def _estrai_eventi_noti_minimi(mondo):
    testo = (mondo or "").lower()

    eventi = {
        "carezza_testa": "testa" in testo and ("tocc" in testo or "carezza" in testo),
        "mano_destra": "mano destra" in testo,
        "mano_sinistra": "mano sinistra" in testo,
        "entrambe_mani": "entrambe le mani" in testo,
        "volto_riconosciuto": "riconosco" in testo,
        "volto_ignoto": "volto ignoto" in testo or "non riconosco" in testo,
        "ostacolo_destra": "ostacolo a destra" in testo,
        "ostacolo_sinistra": "ostacolo a sinistra" in testo,
        "ostacolo_frontale": "ostacolo frontale" in testo,
        "rumore_improvviso": "rumore improvviso" in testo or "suono improvviso" in testo,
        "rumore_singolo": "rumore singolo" in testo or "colpo" in testo,
        "battiti_mani": "battiti" in testo or "battito" in testo,
        "fermo": "sono fermo" in testo,
        "camminando": "sto camminando" in testo
    }

    if eventi.get("camminando", False):
        eventi["fermo"] = False

    if eventi.get("fermo", False):
        eventi["camminando"] = False

    return eventi

def _pulisci_mondo_per_unknown(mondo):
    """
    Rimuove marker tecnici usati da soul.py per attivare la curiosità.
    Gli eventi UNKNOWN devono nascere dal contenuto osservato,
    non da PRENDI L'INIZIATIVA / OSSERVAZIONE_AUTONOMA.
    """
    testo = (mondo or "").lower()

    marker = [
        "report:",
        "prendi l'iniziativa",
        "prendi l iniziativa",
        "prendi liniziativa",
        "osservazione_autonoma",
        "osservazione autonoma",
        "nessuna_condizione_attiva",
        "nessuna condizione attiva",
        "sono fermo",
        "sto camminando"
    ]

    for m in marker:
        testo = testo.replace(m, " ")

    # Se c'è VEDO:, privilegio la parte visiva.
    if "vedo:" in testo:
        testo = testo.split("vedo:", 1)[1]

    testo = testo.replace("vedo:", " ")
    testo = testo.replace(".", " ")
    testo = " ".join(testo.split())

    return testo

def costruisci_firma_situazione(mondo, stato_runtime):
    """
    Trasforma il mondo attuale in una descrizione piu' astratta.

    L'obiettivo e' non dipendere solo da condizioni scritte a mano
    come tocco testa, tocco piede, ostacolo, volto, ecc.
    """

    if stato_runtime is None:
        stato_runtime = {}

    testo = (mondo or "").strip().lower()
    eventi = dict(stato_runtime.get("eventi", {}))
    eventi_reali = dict(stato_runtime.get("eventi_reali", {}))
    evento_strutturato = stato_runtime.get("evento_strutturato", {})

    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    if not isinstance(eventi, dict):
        eventi = {}
    
    if not isinstance(eventi_reali, dict):
        eventi_reali = {}

    eventi_noti_testo = _estrai_eventi_noti_minimi(mondo)

    for chiave, valore in eventi_noti_testo.items():
        if chiave not in eventi:
            eventi[chiave] = valore
    
    # Eventi UNKNOWN cognitivamente significativi.
    # NON trasformiamo descrizioni statiche in eventi.
    # Usiamo solo situazioni utili al comportamento.

    try:
        if estrai_eventi_sconosciuti is not None:

            mondo_unknown = _pulisci_mondo_per_unknown(
                mondo
            )

        if mondo_unknown:
            # Reasoner semantico generalista
            try:
                from behaviors.event_system.unknown_situation_reasoner import (
                    ragiona_situazione_sconosciuta
                )

                ragionamento = (
                    ragiona_situazione_sconosciuta(
                        mondo_unknown
                    )
                )

                if (
                    isinstance(ragionamento, dict)
                    and ragionamento.get("evento")
                ):
                    eventi[
                        ragionamento["evento"]
                    ] = True

            except Exception as e:
                logger.warning(
                    "[AUTONOMIA] Errore reasoner semantico: {}".format(e)
                )

            # Extractor eventi sconosciuti
            eventi_unknown = (
                estrai_eventi_sconosciuti(
                    mondo_unknown
                )
            )

            for ev in eventi_unknown:

                if not isinstance(ev, dict):
                    continue

                nome = ev.get("nome")

                if nome:
                    eventi[nome] = True
                    if not isinstance(ev, dict):
                        continue

                    nome = ev.get("nome")

                    if nome:
                        eventi[nome] = True

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore estrazione eventi sconosciuti: {}".format(e)
        )
    
    parole_banali = [
        "la mia batteria",
        "batteria",
        "sono fermo",
        "fermo",
        "nessun evento",
        "nessuna interazione"
    ]

    parole_sensoriali_generiche = [
        "sento",
        "percepisco",
        "rilevo",
        "vedo",
        "tocca",
        "tocco",
        "pressione",
        "contatto",
        "movimento",
        "ostacolo",
        "volto",
        "rumore",
        "suono",
        "voce",
        "interazione",
        "evento"
    ]

    chiavi_runtime_banali = [
        "batteria",
        "battery",
        "livello_batteria",
        "postura",
        "stato_movimento",
        "fermo",
        "timestamp",
        "tempo"
    ]

    eventi_attivi = {}

    # Eventi estratti dal testo
    for chiave, valore in eventi.items():
        chiave_norm = str(chiave).lower()

        if chiave_norm in chiavi_runtime_banali:
            continue

        if valore not in [None, False, "", [], {}]:
            eventi_attivi[chiave] = valore

    # Eventi reali dei sensori (priorità alta)
    for chiave, valore in eventi_reali.items():
        chiave_norm = str(chiave).lower()

        if chiave_norm in chiavi_runtime_banali:
            continue

        if valore not in [None, False, "", [], {}]:
            eventi_attivi[chiave] = valore

    indicatori_composti = [
        ["sinistra", "destra"],
        ["mano", "piede"],
        ["testa", "mano"],
        ["volto", "voce"],
        ["interazione", "movimento"]
    ]

    # EVENTI STRUTTURATI PRIORITARI
    # Se ho eventi reali coerenti, li uso prima del parsing testo.
    eventi_sociali = [
        "carezza_testa",
        "mano_sinistra",
        "mano_destra",
        "entrambe_mani",
        "volto_riconosciuto",
        "volto_ignoto"
    ]

    eventi_safety = [
        "ostacolo_sinistra",
        "ostacolo_destra",
        "ostacolo_frontale",
        "urto_piedi",
        "piede_sinistro",
        "piede_destro",
        "pericolo_caduta"
    ]

    eventi_audio = [
        "rumore_improvviso",
        "rumore_singolo",
        "battiti_mani"
    ]

    mondo_vuoto = not testo

    solo_banale = False
    if testo:
        contiene_banale = any(p in testo for p in parole_banali)
        contiene_sensoriale = any(p in testo for p in parole_sensoriali_generiche)
        solo_banale = contiene_banale and not contiene_sensoriale and len(eventi_attivi) == 0

    eventi_core = evento_strutturato.get("eventi_core", [])

    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = [
        e for e in eventi_core
        if str(e).lower().strip() != "interazione_utente"
    ]
    
    numero_eventi_reali = len(eventi_attivi.keys())

    # Se gli eventi strutturati reali esistono,
    # considero la situazione significativa anche con poco testo.
    presenza_eventi_reali = any([
        k in eventi_attivi
        for k in (
            eventi_sociali +
            eventi_safety +
            eventi_audio
        )
    ])

    eventi_attivi_generativi = [
        k for k in eventi_attivi.keys()
        if str(k).lower().strip() != "interazione_utente"
    ]

    eventi_multipli = (
        len(eventi_core) >= 2
        or len(eventi_attivi_generativi) >= 2
        or (
            evento_strutturato.get("evento_composto", False)
            and len(eventi_core) >= 2
        )
    )

    situazione_composta = False

    for gruppo in indicatori_composti:
        if all(parola in testo for parola in gruppo):
            situazione_composta = True
            break

    chiavi_eventi_attivi = " ".join(str(k).lower() for k in eventi_attivi.keys())

    if not situazione_composta:
        for gruppo in indicatori_composti:
            if all(parola in chiavi_eventi_attivi for parola in gruppo):
                situazione_composta = True
                break

    eventi_significativi = [
        k for k in eventi_attivi.keys()
        if str(k).lower().strip() not in [
            "fermo",
            "camminando",
            "interazione_utente"
        ]
    ]

    ha_novita_runtime = (
        presenza_eventi_reali
        or len(eventi_significativi) > 0
        or evento_strutturato.get("tipo", "generico") != "generico"
    )

    ha_testo_sensoriale_non_banale = (
        bool(testo)
        and not solo_banale
        and (
            any(p in testo for p in parole_sensoriali_generiche)
            or len(testo.split()) >= 8
        )
    )

    mondo_normalizzato = testo
    gia_tentata = mondo_normalizzato == ULTIMO_MONDO_GENERATO

    eventi_descritti = {}

    try:
        if arricchisci_eventi_registro is not None:
            eventi_descritti = arricchisci_eventi_registro(eventi_attivi)
    except Exception:
        eventi_descritti = {}

    return {
        "testo": testo,
        "eventi": eventi,
        "eventi_attivi": eventi_attivi,
        "eventi_descritti": eventi_descritti,
        "mondo_vuoto": mondo_vuoto,
        "banale": solo_banale,
        "eventi_multipli": eventi_multipli,
        "situazione_composta": situazione_composta,
        "ha_novita_runtime": ha_novita_runtime,
        "ha_testo_sensoriale_non_banale": ha_testo_sensoriale_non_banale,
        "evento_strutturato": evento_strutturato,
        "eventi_core": eventi_core,
        "gia_tentata": gia_tentata
    }
    

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
    mondo_normalizzato = (mondo or "").strip().lower()

    if ULTIMO_MONDO_GENERATO == mondo_normalizzato:
        logger.info("[AUTONOMIA] Generazione saltata: situazione gia' tentata")
        return None

    if adesso - ULTIMA_GENERAZIONE < INTERVALLO_MINIMO_GENERAZIONE:
        logger.info("[AUTONOMIA] Generazione saltata: troppo ravvicinata")
        return None

    ULTIMA_GENERAZIONE = adesso

    try:
        import behaviors.condition_system.condition_generator as condition_generator

        logger.info("[AUTONOMIA] Provo generazione autonoma. Motivo: {}".format(motivo))

        if hasattr(condition_generator, "genera_condizione_autonoma"):
            dati_memoria_runtime = stato_runtime.get("memoria", {})
            if not isinstance(dati_memoria_runtime, dict):
                dati_memoria_runtime = {}

            dati_memoria = dict(dati_memoria_runtime)
            if stato_runtime.get("world_model"):
                dati_memoria["world_model"] = stato_runtime.get("world_model")
            stato_robot = stato_runtime.get("stato_robot", {})
            storia_episodica = stato_runtime.get("ipotesi_temporanea")

            if isinstance(storia_episodica, dict):
                storia_episodica = dict(storia_episodica)
                storia_episodica["motivo_cognitivo_generazione"] = motivo
            else:
                storia_episodica = None

            chiave_privata = (
                stato_runtime.get("openai_api_key")
                or os.environ.get("OPENAI_API_KEY")
            )
            logger.info(
                "[AUTONOMIA][LLM] API key presente per generator: {} | fonte={}".format(
                    bool(str(chiave_privata or "").strip()),
                    "runtime" if stato_runtime.get("openai_api_key") else "env"
                )
            )

            path_nuova_condizione = chiama_genera_condizione_autonoma_sicura(
                condition_generator.genera_condizione_autonoma,
                mondo,
                dati_memoria,
                stato_robot,
                chiave_privata,
                storia_episodica=storia_episodica
            )

            if path_nuova_condizione:
                ULTIMO_MONDO_GENERATO = mondo_normalizzato

                logger.info("[AUTONOMIA] Nuova condizione generata: {}".format(
                    path_nuova_condizione
                ))

                try:
                    if hasattr(condition_generator, "reset_cache_condizioni"):
                        condition_generator.reset_cache_condizioni()
                except Exception:
                    pass

                try:
                    from behaviors.condition_system.condition_manager import reset_cache_condizioni
                    reset_cache_condizioni()
                except Exception:
                    pass
            else:
                logger.info(
                    "[AUTONOMIA] Nessuna nuova condizione generata: rivaluto condizioni esistenti"
                )

                try:
                    from behaviors.condition_system.condition_manager import (
                        reset_cache_condizioni
                    )
                    reset_cache_condizioni()
                except Exception:
                    pass

                return valuta_condizioni_generate_sicure(
                    mondo,
                    stato_runtime
                )

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
