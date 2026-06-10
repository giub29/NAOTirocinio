# -*- coding: utf-8 -*-

import logging
import traceback

logger = logging.getLogger(__name__)

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

        # 2. Politica agentica preventiva sugli eventi semantici
        politica_pre = decidi_politica_evento(
            firma,
            "politica preventiva su evento semantico"
        )

        logger.info(
            "[AGENTIC] Politica preventiva evento: {}".format(
                politica_pre
            )
        )

        if politica_pre.get("azione") not in ["genera", "nessuna_politica"]:
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
                return decisione_politica
            
        # 3. Curiosita' autonoma, se disponibile.
        # Arriva dopo la politica agentica preventiva:
        # se l'evento ha gia' una risposta cognitiva chiara,
        # non serve curiosita' generica.
        try:
            if costruisci_decisione_curiosa is not None:
                mondo_unknown = mondo

                if pulisci_mondo_per_unknown is not None:
                    mondo_unknown = pulisci_mondo_per_unknown(mondo)

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
                    return decisione_politica

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