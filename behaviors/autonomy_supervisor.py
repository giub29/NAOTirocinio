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

try:
    from behaviors.event_system.unknown_event_extractor import arricchisci_eventi_con_sconosciuti
except Exception:
    arricchisci_eventi_con_sconosciuti = None

try:
    from behaviors.event_system.event_registry import arricchisci_eventi_registro
except Exception:
    arricchisci_eventi_registro = None

from behaviors.event_system.unknown_generation_simulator import simula_condizione_sconosciuta

logger = logging.getLogger(__name__)
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

    firma = costruisci_firma_situazione(mondo, stato_runtime)

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
            stato_runtime["evento_strutturato"] = {
                "tipo": "unknown",
                "categoria": "sconosciuta",
                "origine": "scoperta",
                "eventi_core": eventi_sconosciuti
            }

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
    # gli eventi scoperti autonomamente devono entrare anche
    # in stato_runtime["eventi"], altrimenti le condizioni
    # autogenerate non possono attivarsi davvero.
    try:
        eventi_core = firma.get("eventi_core", [])

        if not isinstance(eventi_core, list):
            eventi_core = []

        eventi_reali_correnti = stato_runtime.get("eventi_reali", {})
        for nome_evento in eventi_core:
            nome_evento = str(nome_evento).lower().strip()

            if nome_evento and eventi_reali_correnti.get(nome_evento, False):
                stato_runtime.setdefault("eventi", {})
                stato_runtime["eventi"][nome_evento] = True

    except Exception as e:
        logger.warning(
            "[AUTONOMIA] Errore propagando eventi_core nel runtime: {}".format(e)
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

        deve_generare, motivo = situazione_merita_generazione(mondo, stato_runtime)

        logger.info("[AUTONOMIA] Valutazione generazione autonoma: {} - {}".format(
            deve_generare,
            motivo
        ))

        if deve_generare:
            nuova_decisione = prova_generazione_autonoma(
                mondo,
                stato_runtime,
                "evento composto prioritario: {}".format(motivo)
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
    if not isinstance(eventi_core, list):
        eventi_core = []

    eventi_core = filtra_eventi_helper(eventi_core)

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
    
    # Eventi sconosciuti:
    # se il mondo contiene concetti nuovi, li trasformo in eventi candidati.
    # Per osservazione autonoma pulisco i marker tecnici e passo solo
    # il contenuto visivo reale all'estrattore unknown.
    try:
        if arricchisci_eventi_con_sconosciuti is not None:
            mondo_unknown = _pulisci_mondo_per_unknown(mondo)

            if mondo_unknown:
                eventi = arricchisci_eventi_con_sconosciuti(
                    mondo_unknown,
                    eventi
                )
    except Exception as e:
        logger.warning("[AUTONOMIA] Errore estrazione eventi sconosciuti: {}".format(e))
    
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

    ha_novita_runtime = (
        presenza_eventi_reali
        or len(eventi_attivi.keys()) > 0
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
            dati_memoria = stato_runtime.get("memoria", {})
            stato_robot = stato_runtime.get("stato_robot", {})
            chiave_privata = (
                stato_runtime.get("openai_api_key")
                or os.environ.get("OPENAI_API_KEY")
            )

            path_nuova_condizione = condition_generator.genera_condizione_autonoma(
                mondo,
                dati_memoria,
                stato_robot,
                chiave_privata
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