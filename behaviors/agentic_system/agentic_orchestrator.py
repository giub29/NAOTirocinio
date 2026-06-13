# -*- coding: utf-8 -*-

import logging
import traceback
import time

logger = logging.getLogger(__name__)

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
        valuta_risposta_osservazione_mirata
    )
except Exception:
    costruisci_decisione_osservazione_mirata = None
    valuta_risposta_osservazione_mirata = None


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
        logger.warning("[AGENTIC] Errore world model: {}".format(e))
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
            "[AGENTIC] Errore osservazione mirata: {}".format(e)
        )
        return None


def registra_osservazione_mirata_corrente(stato_runtime, decisione):
    if stato_runtime is None or not isinstance(decisione, dict):
        return decisione

    piano = None
    memoria = decisione.get("memoria", [])

    if isinstance(memoria, list):
        for voce in memoria:
            if isinstance(voce, dict) and voce.get("tipo") == "osservazione_mirata":
                piano = dict(voce)
                break

    if piano is None:
        return decisione

    piano_precedente = stato_runtime.get("osservazione_mirata_corrente", {})
    if not isinstance(piano_precedente, dict):
        piano_precedente = {}

    stesso_target = (
        piano_precedente.get("target")
        and piano_precedente.get("target") == piano.get("target")
    )

    piano["attiva_il"] = piano_precedente.get(
        "attiva_il",
        time.strftime("%Y-%m-%d %H:%M:%S")
    )
    piano["tentativi"] = (
        int(piano_precedente.get("tentativi", 0))
        if stesso_target else 0
    )
    piano["stato"] = "attiva"
    stato_runtime["osservazione_mirata_corrente"] = piano

    storia = stato_runtime.get("osservazioni_mirate_recenti", [])
    if not isinstance(storia, list):
        storia = []

    storia.append(piano)
    stato_runtime["osservazioni_mirate_recenti"] = storia[-5:]

    return decisione


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
            "[AGENTIC] Errore valutando risposta osservazione: {}".format(e)
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

    logger.info("[AGENTIC] Esito osservazione mirata: {}".format(esito))

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
            "[AGENTIC] Errore aggiornando ipotesi da osservazione: {}".format(e)
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
            "[AGENTIC] Errore aggiornando world model da osservazione: {}".format(e)
        )
        return None


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
            "[AGENTIC] Errore memoria ipotesi temporanee: {}".format(e)
        )
        return {
            "ha_ipotesi": False,
            "genera_condizione": False,
            "motivo": "errore memoria ipotesi temporanee"
        }


def decidi_politica_evento(firma, motivo):
    """
    Decide cosa fare prima di generare codice.

    La generazione Python deve essere l'ultima scelta, non la risposta automatica
    a ogni evento semanticamente rilevante.
    """

    if not isinstance(firma, dict):
        firma = {}

    eventi_attivi = firma.get("eventi_attivi", {})

    if not isinstance(eventi_attivi, dict):
        eventi_attivi = {}

    eventi = set(eventi_attivi.keys())
    if not eventi:
        return {
            "azione": "nessuna_politica",
            "motivo": "nessun evento semantico attivo"
        }

    # 1. Informazione operativa: prima osserva/memorizza, non generare subito.
    if "informazione_operativa" in eventi:
        return {
            "azione": "memoria",
            "stato_interno": "attento",
            "obiettivo": "comprendere un contenuto utile per agire",
            "frase": "Ho notato un'informazione utile. La tengo presente prima di decidere cosa fare.",
            "motivo": "informazione operativa da interpretare o memorizzare"
        }

    # 2. Accesso disponibile/non disponibile: prima prudenza/esplorazione.
    if "accesso_non_disponibile" in eventi:
        return {
            "azione": "prudenza",
            "stato_interno": "prudente",
            "obiettivo": "valutare un accesso non disponibile",
            "frase": "Sembra che un passaggio non sia disponibile. Procedo con cautela.",
            "motivo": "accesso o passaggio limitato"
        }

    if "accesso_disponibile" in eventi:
        return {
            "azione": "curiosita",
            "stato_interno": "curioso",
            "obiettivo": "valutare una possibile opportunita' di esplorazione",
            "frase": "Sembra che ci sia un passaggio disponibile. Potrei esplorarlo con attenzione.",
            "motivo": "accesso o passaggio disponibile"
        }

    # 3. Oggetti in zona rilevante: prudenza prima di generare.
    if "oggetto_in_zona_rilevante" in eventi:
        return {
            "azione": "prudenza",
            "stato_interno": "prudente",
            "obiettivo": "valutare un elemento vicino a una zona rilevante",
            "frase": "Ho notato un elemento in una zona importante. Lo considero con prudenza.",
            "motivo": "elemento vicino a zona di movimento/accesso"
        }

    # 4. Testo o contenuto informativo generico: osserva meglio.
    if "contenuto_testuale_da_approfondire" in eventi:
        return {
            "azione": "osserva_meglio",
            "stato_interno": "curioso",
            "obiettivo": "approfondire un contenuto testuale non ancora chiaro",
            "frase": "Vedo del testo, ma non e' ancora abbastanza chiaro. Provo a osservarlo meglio.",
            "motivo": "contenuto testuale incerto"
        }

    if "contenuto_informativo_rilevante" in eventi:
        return {
            "azione": "memoria",
            "stato_interno": "attento",
            "obiettivo": "comprendere un contenuto informativo rilevante",
            "frase": "Ho notato un'informazione potenzialmente utile. La analizzo con attenzione.",
            "motivo": "contenuto informativo rilevante"
        }

    if "vincolo_comportamentale" in eventi:
        return {
            "azione": "prudenza",
            "stato_interno": "prudente",
            "obiettivo": "rispettare un possibile vincolo comportamentale",
            "frase": "Ho rilevato un possibile vincolo. Devo tenerne conto prima di agire.",
            "motivo": "vincolo o limite all'azione"
        }

    # 5. Anomalie ambientali: qui la generazione puo' avere senso.
    if "elemento_ambientale_anomalo" in eventi:
        return {
            "azione": "genera",
            "motivo": "anomalia ambientale potenzialmente ricorrente"
        }

    if "elemento_fuori_posto" in eventi:
        return {
            "azione": "genera",
            "motivo": "elemento fuori posto potenzialmente ricorrente"
        }

    if "accesso_o_percorso_limitato" in eventi:
        return {
            "azione": "genera",
            "motivo": "limitazione di movimento o accesso potenzialmente ricorrente"
        }

    # Default: se non so classificare la maturita', non genero subito.
    return {
        "azione": "osserva_meglio",
        "stato_interno": "riflessivo",
        "obiettivo": "valutare meglio una situazione nuova",
        "frase": "Ho notato qualcosa di nuovo. Prima di creare una condizione, lo osservo meglio.",
        "motivo": motivo or "situazione nuova non ancora matura per generazione"
    }

def costruisci_decisione_da_politica(politica, mondo, firma):
    azione = politica.get("azione")

    if azione == "genera":
        return None

    azione_percettiva = {
        "memoria": "interpreta_e_memorizza",
        "prudenza": "osserva_con_prudenza",
        "curiosita": "osserva_meglio",
        "osserva_meglio": "osserva_meglio"
    }.get(azione)

    if azione_percettiva:
        decisione_mirata = costruisci_osservazione_mirata_sicura(
            mondo,
            azione_cognitiva=azione_percettiva,
            motivo=politica.get("motivo"),
            firma=firma
        )

        if decisione_mirata is not None:
            return decisione_mirata

    colore = "yellow"

    if azione == "prudenza":
        colore = "red"
    elif azione == "memoria":
        colore = "blue"
    elif azione == "curiosita":
        colore = "green"

    return {
        "stato_interno": politica.get("stato_interno", "riflessivo"),
        "obiettivo": politica.get("obiettivo", "valutare una situazione nuova"),
        "azioni": [
            {"tipo": "occhi", "colore": colore},
            {
                "tipo": "parla",
                "testo": politica.get(
                    "frase",
                    "Ho notato qualcosa di nuovo e lo valuto prima di agire."
                )
            }
        ],
        "memoria": [
            {
                "tipo": "politica_agentica",
                "azione": azione,
                "motivo": politica.get("motivo"),
                "mondo": mondo,
                "eventi_attivi": firma.get("eventi_attivi", {})
            }
        ]
    }

def esegui_ciclo_agentico(
    mondo,
    stato_runtime,
    costruisci_firma_situazione,
    valuta_condizioni_generate_sicure,
    situazione_merita_generazione,
    prova_generazione_autonoma,
    costruisci_decisione_curiosa=None,
    pulisci_mondo_per_unknown=None
):
    """
    Orchestratore agentico leggero per NAO.

    Per ora NON cambia la logica del robot:
    organizza il ciclo autonomia in modo più chiaro e controllabile.

    Ciclo:
    1. costruisce firma situazione
    2. valuta condizioni già generate
    3. valuta curiosità autonoma
    4. decide se generare nuova condizione
    5. rivaluta dopo generazione
    """

    if stato_runtime is None:
        stato_runtime = {}

    stato = {
        "mondo": mondo,
        "stato_runtime": stato_runtime,
        "firma": None,
        "decisione": None,
        "motivo": None,
        "errore": None,
        "step": []
    }

    try:
        logger.info("[AGENTIC] Avvio ciclo agentico")

        if stato_runtime.get("agentic_dry_run", False):
            firma = costruisci_firma_situazione(mondo, stato_runtime)
            stato["firma"] = firma
            stato["step"].append("dry_run_firma_costruita")

            deve_generare, motivo = situazione_merita_generazione(
                mondo,
                stato_runtime
            )

            logger.info(
                "[AGENTIC] Dry-run totale: deve_generare={} motivo={}".format(
                    deve_generare,
                    motivo
                )
            )

            return {
                "stato_interno": "riflessivo",
                "obiettivo": "analizzare una situazione nuova senza usare o generare condizioni",
                "azioni": [
                    {"tipo": "occhi", "colore": "yellow"},
                    {
                        "tipo": "parla",
                        "testo": "Ho notato qualcosa di nuovo. Lo analizzo senza creare una nuova condizione."
                    }
                ],
                "memoria": [
                    {
                        "tipo": "agentic_dry_run",
                        "mondo": mondo,
                        "deve_generare": deve_generare,
                        "motivo": motivo,
                        "firma": firma
                    }
                ]
            }

        firma = costruisci_firma_situazione(mondo, stato_runtime)
        stato["firma"] = firma
        stato["step"].append("firma_costruita")
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

        logger.info("[AGENTIC] Firma situazione: {}".format(firma))

        # Propagazione eventi nel runtime
        try:
            stato_runtime["eventi"] = firma.get("eventi", {})
            stato_runtime["eventi_reali"] = firma.get("eventi_attivi", {})

            eventi_descritti = firma.get("eventi_descritti", {})
            eventi_sconosciuti = [
                nome for nome, dati in eventi_descritti.items()
                if not dati.get("conosciuto", True)
            ]

            if eventi_sconosciuti:
                stato_runtime["evento_strutturato"] = {
                    "tipo": "unknown",
                    "categoria": "sconosciuta",
                    "origine": "scoperta",
                    "eventi_core": eventi_sconosciuti
                }

        except Exception as e:
            logger.warning("[AGENTIC] Errore propagando firma: {}".format(e))

        # 1. Prima provo condizioni già esistenti
        decisione = valuta_condizioni_generate_sicure(mondo, stato_runtime)

        if decisione is not None:
            stato["decisione"] = decisione
            stato["motivo"] = "condizione_generata_esistente"
            stato["step"].append("decisione_da_condizione")
            logger.info("[AGENTIC] Decisione da condizione esistente")
            return decisione

        stato["step"].append("nessuna_condizione_attiva")

        esito_ipotesi = valuta_ipotesi_temporanee_sicura(
            mondo,
            firma,
            stato_runtime
        )

        ipotesi_confermata = False

        if esito_ipotesi.get("ha_ipotesi"):
            logger.info(
                "[AGENTIC] Ipotesi temporanea: {}".format(esito_ipotesi)
            )

            if esito_ipotesi.get("genera_condizione"):
                ipotesi_confermata = True
                stato["step"].append("ipotesi_temporanea_confermata")
            else:
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
                        stato["decisione"] = decisione_world
                        stato["motivo"] = "world_model_stabile"
                        stato["step"].append("decisione_da_world_model")
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
                    stato["decisione"] = decisione_mirata
                    stato["motivo"] = "osservazione_mirata"
                    stato["step"].append("decisione_osservazione_mirata")
                    return registra_osservazione_mirata_corrente(
                        stato_runtime,
                        decisione_mirata
                    )

                if costruisci_decisione_ipotesi is not None:
                    decisione_ipotesi = costruisci_decisione_ipotesi(
                        esito_ipotesi
                    )

                if decisione_ipotesi is not None:
                    stato["decisione"] = decisione_ipotesi
                    stato["motivo"] = "ipotesi_temporanea"
                    stato["step"].append("decisione_da_ipotesi_temporanea")
                    return decisione_ipotesi

        # 2. Politica agentica preventiva sugli eventi semantici
        politica_pre = {"azione": "genera", "motivo": "ipotesi confermata"}

        if not ipotesi_confermata:
            politica_pre = decidi_politica_evento(
                firma,
                "politica preventiva su evento semantico"
            )

        logger.info(
            "[AGENTIC] Politica preventiva evento: {}".format(
                politica_pre
            )
        )

        if (
            not ipotesi_confermata and
            politica_pre.get("azione") not in ["genera", "nessuna_politica"]
        ):
            decisione_politica = costruisci_decisione_da_politica(
                politica_pre,
                mondo,
                firma
            )

            if decisione_politica is not None:
                stato["decisione"] = decisione_politica
                stato["motivo"] = "politica_agentica_pre_curiosita"
                stato["step"].append(
                    "decisione_politica_pre_curiosita"
                )
                return registra_osservazione_mirata_corrente(
                    stato_runtime,
                    decisione_politica
                )
            
        # 3. Curiosita' autonoma, se disponibile.
        # Arriva dopo la politica agentica preventiva:
        # se l'evento ha gia' una risposta cognitiva chiara,
        # non serve curiosita' generica.
        try:
            if costruisci_decisione_curiosa is not None:
                mondo_unknown = mondo

                if pulisci_mondo_per_unknown is not None:
                    mondo_unknown = pulisci_mondo_per_unknown(mondo)

                try:
                    from behaviors.event_system.unknown_situation_reasoner import (
                        ragiona_situazione_sconosciuta
                    )

                    ragionamento = ragiona_situazione_sconosciuta(
                        mondo_unknown
                    )

                    if ragionamento is not None:
                        decisione_mirata = (
                            costruisci_osservazione_mirata_sicura(
                                mondo,
                                azione_cognitiva=ragionamento.get(
                                    "azione_cognitiva"
                                ),
                                motivo=ragionamento.get("ipotesi"),
                                world_model=esito_world_model,
                                ragionamento=ragionamento,
                                firma=firma
                            )
                        )

                        if decisione_mirata is not None:
                            stato["decisione"] = decisione_mirata
                            stato["motivo"] = "osservazione_mirata"
                            stato["step"].append(
                                "decisione_osservazione_mirata"
                            )
                            logger.info(
                                "[AGENTIC] Decisione osservazione mirata"
                            )
                            return registra_osservazione_mirata_corrente(
                                stato_runtime,
                                decisione_mirata
                            )

                except Exception as e:
                    logger.warning(
                        "[AGENTIC] Errore planner osservazione: {}".format(e)
                    )

                decisione_curiosa = costruisci_decisione_curiosa(
                    mondo_unknown
                )

                if decisione_curiosa is not None:
                    stato["decisione"] = decisione_curiosa
                    stato["motivo"] = "curiosita_autonoma"
                    stato["step"].append("decisione_curiosa")
                    logger.info("[AGENTIC] Decisione curiosa autonoma")
                    return decisione_curiosa

        except Exception as e:
            logger.warning(
                "[AGENTIC] Errore curiosita autonoma: {}".format(e)
            )    

        # 4. Valuto se generare una nuova condizione
        deve_generare = False
        motivo = ""

        if ipotesi_confermata:
            deve_generare = True
            motivo = esito_ipotesi.get(
                "motivo",
                "ipotesi temporanea confermata"
            )
        else:
            deve_generare, motivo = situazione_merita_generazione(
                mondo,
                stato_runtime
            )

        stato["motivo"] = motivo
        stato["step"].append("valutazione_generazione")

        logger.info("[AGENTIC] Deve generare? {} - {}".format(
            deve_generare,
            motivo
        ))
        if deve_generare:
            politica = {
                "azione": "genera",
                "motivo": "ipotesi temporanea confermata"
            }

            if not ipotesi_confermata:
                politica = decidi_politica_evento(firma, motivo)

            logger.info("[AGENTIC] Politica evento: {}".format(politica))

            if politica.get("azione") != "genera":
                decisione_politica = costruisci_decisione_da_politica(
                    politica,
                    mondo,
                    firma
                )

                if decisione_politica is not None:
                    stato["decisione"] = decisione_politica
                    stato["motivo"] = "politica_agentica"
                    stato["step"].append("decisione_da_politica")
                    return registra_osservazione_mirata_corrente(
                        stato_runtime,
                        decisione_politica
                    )

            if stato_runtime.get("agentic_dry_run", False):
                logger.info(
                    "[AGENTIC] Dry-run attivo: non genero condizioni. Motivo: {}".format(
                        motivo
                    )
                )

                return {
                    "stato_interno": "riflessivo",
                    "obiettivo": "valutare una situazione nuova senza generare codice",
                    "azioni": [
                        {"tipo": "occhi", "colore": "yellow"},
                        {
                            "tipo": "parla",
                            "testo": "Ho notato qualcosa di nuovo. Per ora lo analizzo senza creare una nuova condizione."
                        }
                    ],
                    "memoria": [
                        {
                            "tipo": "agentic_dry_run",
                            "mondo": mondo,
                            "motivo": motivo
                        }
                    ]
                }

            decisione = prova_generazione_autonoma(
                mondo,
                stato_runtime,
                motivo
            )

            if decisione is not None:
                stato["decisione"] = decisione
                stato["step"].append("decisione_dopo_generazione")
                logger.info("[AGENTIC] Decisione dopo generazione")
                return decisione

        stato["step"].append("nessuna_decisione")
        return None

    except Exception as e:
        stato["errore"] = str(e)
        logger.error("[AGENTIC] Errore ciclo agentico: {}".format(e))
        logger.error(traceback.format_exc())
        return None
