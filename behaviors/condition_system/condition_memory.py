# -*- coding: utf-8 -*-
"""
Memoria delle condizioni autonome generate da NAO.

Questo modulo crea e aggiorna file .meta.json separati dal codice Python
delle condizioni. I metadati vengono salvati in condition_metadata/
per mantenere distinta la memoria semantica dal codice eseguibile.
"""

import os
import json
import time
import codecs
import logging

logger = logging.getLogger(__name__)

try:
    basestring
except NameError:
    basestring = str

BASE_DIR = os.path.dirname(__file__)
METADATA_DIR = os.path.join(BASE_DIR, "condition_metadata")
REJECTED_METADATA_DIR = os.path.join(BASE_DIR, "rejected_metadata")
GENERATED_DIR = os.path.join(BASE_DIR, "generated_conditions")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected_conditions")


def _assicura_cartelle():
    for cartella in [
        GENERATED_DIR,
        REJECTED_DIR,
        METADATA_DIR,
        REJECTED_METADATA_DIR
    ]:
        if not os.path.exists(cartella):
            os.makedirs(cartella)


def _meta_path(nome_condizione, cartella=None):
    """
    Ritorna il path del file metadati per una condizione.

    nome_condizione può essere:
    - condizione_ostacolo_destra
    - condizione_ostacolo_destra.py
    """

    _assicura_cartelle()

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    if cartella is None:
        cartella = METADATA_DIR

    return os.path.join(cartella, nome_condizione + ".meta.json")


def _adesso():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _testo_breve(testo, limite=260):
    if isinstance(testo, basestring):
        testo = testo or ""
    else:
        testo = str(testo or "")

    testo = " ".join(testo.split())

    if len(testo) <= limite:
        return testo

    return testo[:limite].rstrip() + "..."


def _aggiungi_esempio_unico(lista, esempio, limite=8):

    firma = (
        esempio.get("mondo", ""),
        esempio.get("motivo", ""),
        esempio.get("fonte", "")
    )

    for esistente in lista:
        firma_esistente = (
            esistente.get("mondo", ""),
            esistente.get("motivo", ""),
            esistente.get("fonte", "")
        )

        if firma_esistente == firma:
            return lista

    lista.append(esempio)

    return lista[-limite:]


def _riassumi_esempi(esempi, limite=2):
    riassunti = []

    try:
        esempi_recenti = esempi[-limite:]
    except Exception:
        esempi_recenti = []

    for esempio in esempi_recenti:
        if not isinstance(esempio, dict):
            continue

        riassunti.append({
            "fonte": esempio.get("fonte", ""),
            "mondo": _testo_breve(esempio.get("mondo", ""), 160),
            "motivo": _testo_breve(esempio.get("motivo", ""), 120)
        })

    return riassunti


def _tokenizza_testo(testo):
    testo = (testo or "").lower()

    for separatore in [
        "\n", "\r", "\t", ".", ",", ";", ":",
        "(", ")", "[", "]", "{", "}", "'", '"',
        "-", "/", "\\", "|"
    ]:
        testo = testo.replace(separatore, " ")

    parole_vuote = [
        "report", "sono", "fermo", "sto", "camminando",
        "vedo", "sento", "rilevo", "una", "uno", "un",
        "la", "il", "lo", "le", "gli", "di", "a", "da",
        "in", "con", "per", "che", "nel", "nella",
        "sul", "sulla", "del", "della", "dei", "delle",
        "non", "qui", "cosa", "qualcosa"
    ]

    token = []

    for parola in testo.split():
        parola = parola.strip().lower()

        if len(parola) < 3:
            continue

        if parola in parole_vuote:
            continue

        if parola not in token:
            token.append(parola)

    return token


def _token_da_voce_memoria(voce):
    testi = [
        voce.get("nome", ""),
        voce.get("categoria_cognitiva", ""),
        voce.get("azione_cognitiva_origine", ""),
        voce.get("motivo_generazione", ""),
        voce.get("contesto_semantico", "")
    ]

    for evento in voce.get("eventi_attivi_origine", []):
        testi.append(str(evento).replace("_", " "))

    for esempio in voce.get("esempi_positivi", []):
        if isinstance(esempio, dict):
            testi.append(esempio.get("mondo", ""))
            testi.append(esempio.get("motivo", ""))

    for esempio in voce.get("esempi_negativi", []):
        if isinstance(esempio, dict):
            testi.append(esempio.get("mondo", ""))
            testi.append(esempio.get("motivo", ""))

    return _tokenizza_testo(u" ".join([t for t in testi if t]))


def _eventi_attivi_da_eventi(eventi):
    eventi_attivi = []

    try:
        for chiave, valore in eventi.items():
            if valore is True:
                eventi_attivi.append(chiave)
    except Exception:
        eventi_attivi = []

    return eventi_attivi


def _contiene_evento(eventi_attivi, nomi):
    eventi_norm = set([str(e).lower() for e in eventi_attivi])

    for nome in nomi:
        nome = str(nome).lower()
        for evento in eventi_norm:
            if evento == nome or nome in evento:
                return True

    return False


def _testo_da_metadati(dati):
    parti = []

    if dati.get("mondo_origine"):
        parti.append(dati.get("mondo_origine"))

    for chiave in ["esempi_positivi", "esempi_negativi"]:
        try:
            esempi = dati.get(chiave, [])
        except Exception:
            esempi = []

        for esempio in esempi:
            if not isinstance(esempio, dict):
                continue

            if esempio.get("mondo"):
                parti.append(esempio.get("mondo"))

            if esempio.get("motivo"):
                parti.append(esempio.get("motivo"))

    return u" ".join([p for p in parti if p]).lower()


def _eventi_da_metadati(dati):
    eventi_attivi = []

    try:
        eventi_attivi = list(dati.get("eventi_attivi_origine", []))
    except Exception:
        eventi_attivi = []

    if eventi_attivi:
        return eventi_attivi

    eventi = dati.get("eventi_completi_origine", {})
    if isinstance(eventi, dict):
        eventi_attivi = _eventi_attivi_da_eventi(eventi)

    if eventi_attivi:
        return eventi_attivi

    nome = str(dati.get("nome", "")).lower()
    nome = nome.replace("condizione_", "")

    candidati = [
        "accesso_disponibile",
        "accesso_non_disponibile",
        "informazione_operativa",
        "contenuto_informativo_rilevante",
        "oggetto_in_zona_rilevante",
        "elemento_ambientale_anomalo",
        "elemento_fuori_posto",
        "ostacolo_destra",
        "ostacolo_sinistra",
        "ostacolo_frontale",
        "oggetto_vicino",
        "rumore_improvviso",
        "mano_sinistra",
        "mano_destra",
        "entrambe_mani",
        "carezza_testa",
        "volto_ignoto",
        "volto_riconosciuto"
    ]

    for candidato in candidati:
        if candidato in nome:
            eventi_attivi.append(candidato)

    if eventi_attivi:
        return eventi_attivi

    testo = _testo_da_metadati(dati)

    zone_accesso = [
        "accesso", "passaggio", "percorso",
        "ingresso", "uscita", "entrata",
        "varco", "porta"
    ]

    accesso_non_disponibile = [
        "chius", "blocc", "ostru",
        "impedit", "non accessibile",
        "non posso passare"
    ]

    accesso_disponibile = [
        "apert", "libero", "accessibile",
        "posso passare"
    ]

    if (
        any(zona in testo for zona in zone_accesso) and
        any(indicatore in testo for indicatore in accesso_non_disponibile)
    ):
        eventi_attivi.append("accesso_non_disponibile")

    elif (
        any(zona in testo for zona in zone_accesso) and
        any(indicatore in testo for indicatore in accesso_disponibile)
    ):
        eventi_attivi.append("accesso_disponibile")

    elif any(indicatore in testo for indicatore in [
        "anomalo", "anomala", "rotto", "rotta",
        "danneggiato", "danneggiata", "fuori posto"
    ]):
        eventi_attivi.append("elemento_ambientale_anomalo")

    elif any(indicatore in testo for indicatore in [
        "informazione", "istruzioni", "testo leggibile",
        "contenuto leggibile", "conferire", "inserire"
    ]):
        eventi_attivi.append("informazione_operativa")

    return eventi_attivi


def _categoria_cognitiva_da_eventi(eventi_attivi, mondo):
    testo = (mondo or "").lower()

    if _contiene_evento(eventi_attivi, [
        "carezza_testa",
        "mano_sinistra",
        "mano_destra",
        "entrambe_mani",
        "volto_ignoto",
        "volto_riconosciuto"
    ]):
        return "sociale"

    if _contiene_evento(eventi_attivi, [
        "rumore_improvviso",
        "rumore_singolo",
        "battiti_mani"
    ]):
        return "prudenza"

    if _contiene_evento(eventi_attivi, [
        "elemento_ambientale_anomalo",
        "elemento_fuori_posto",
        "pericolo",
        "urto_piedi"
    ]) or any(x in testo for x in [
        "anomalo", "anomala", "rotto", "rotta",
        "danneggiato", "danneggiata", "fuori posto"
    ]):
        return "anomalia"

    if _contiene_evento(eventi_attivi, [
        "accesso_disponibile",
        "accesso_non_disponibile",
        "accesso_o_percorso_limitato",
        "percorso_potenzialmente_ostruito"
    ]):
        return "accesso"

    if _contiene_evento(eventi_attivi, [
        "informazione_operativa",
        "contenuto_informativo_rilevante",
        "contenuto_testuale_da_approfondire"
    ]):
        return "informazione"

    if _contiene_evento(eventi_attivi, [
        "oggetto_in_zona_rilevante",
        "ostacolo",
        "urto"
    ]):
        return "prudenza"

    if _contiene_evento(eventi_attivi, [
        "zona_da_esplorare",
        "novita",
        "ambiguita_visiva",
        "elemento_da_approfondire"
    ]):
        return "curiosita"

    return "curiosita"


def _azione_cognitiva_da_categoria(categoria, eventi_attivi):
    if categoria == "sociale":
        return "risposta_sociale_controllata"

    if categoria == "anomalia":
        return "osserva_con_prudenza"

    if categoria == "accesso":
        if _contiene_evento(eventi_attivi, ["accesso_disponibile"]):
            return "valuta_esplorazione"
        return "valuta_accesso"

    if categoria == "informazione":
        return "interpreta_e_memorizza"

    if categoria == "prudenza":
        return "osserva_con_prudenza"

    return "curiosita_controllata"


def _motivo_generazione(categoria, eventi_attivi):

    motivi = {
        "anomalia":
            u"elemento ambientale considerato anomalo o potenzialmente problematico",

        "accesso":
            u"possibile variazione dello stato di accessibilità dell'ambiente",

        "informazione":
            u"contenuto osservato potenzialmente utile o operativo",

        "prudenza":
            u"elemento osservato in una zona funzionalmente rilevante",

        "curiosita":
            u"situazione nuova o non ancora sufficientemente compresa"
        ,

        "sociale":
            u"interazione sociale o tattile riconosciuta come riutilizzabile"
    }

    return motivi.get(
        categoria,
        u"contesto osservato autonomamente"
    )


def _contesto_semantico(categoria, azione_cognitiva, eventi_attivi, stato_robot):
    stato = []

    if isinstance(stato_robot, dict):
        for chiave in ["missione_laboratorio", "in_pattugliamento", "camminando"]:
            if stato_robot.get(chiave):
                stato.append(chiave)

    parti = [
        u"categoria={}".format(categoria),
        u"azione_cognitiva={}".format(azione_cognitiva)
    ]

    if eventi_attivi:
        parti.append(u"eventi={}".format(u", ".join(eventi_attivi)))

    if stato:
        parti.append(u"stato_robot={}".format(u", ".join(stato)))

    return u"; ".join(parti)


def _crea_metadati_cognitivi(mondo, eventi, eventi_attivi, stato_robot):
    categoria = _categoria_cognitiva_da_eventi(eventi_attivi, mondo)
    azione = _azione_cognitiva_da_categoria(categoria, eventi_attivi)
    contesto = _contesto_semantico(
        categoria,
        azione,
        eventi_attivi,
        stato_robot
    )

    return {
        "categoria_cognitiva": categoria,
        "motivo_generazione": _motivo_generazione(categoria, eventi_attivi),
        "azione_cognitiva_origine": azione,
        "contesto_semantico": contesto,
        "esempi_positivi": [
            {
                "mondo": _testo_breve(mondo),
                "eventi_attivi": eventi_attivi,
                "contesto_semantico": contesto
            }
        ],
        "esempi_negativi": [],
        "numero_riparazioni": 0
    }


def _assicura_metadati_cognitivi(dati):
    if dati is None:
        return dati

    eventi_attivi = _eventi_da_metadati(dati)
    mondo = dati.get("mondo_origine", "")
    categoria_inferita = _categoria_cognitiva_da_eventi(
        eventi_attivi,
        mondo
    )
    azione_inferita = _azione_cognitiva_da_categoria(
        categoria_inferita,
        eventi_attivi
    )
    contesto_inferito = _contesto_semantico(
        categoria_inferita,
        azione_inferita,
        eventi_attivi,
        dati.get("stato_robot_origine", {})
    )

    riparazione = dati.get("riparazione", {})
    numero_riparazioni = riparazione.get(
        "tentativi",
        dati.get("numero_riparazioni", 0)
    )

    defaults = {
        "categoria_cognitiva": "curiosita",
        "motivo_generazione": "",
        "azione_cognitiva_origine": "curiosita_controllata",
        "contesto_semantico": "",
        "esempi_positivi": [],
        "esempi_negativi": [],
        "numero_riparazioni": numero_riparazioni
    }

    for chiave, valore in defaults.items():
        if chiave not in dati:
            dati[chiave] = valore

    categoria_precedente = dati.get("categoria_cognitiva")

    if (
        not dati.get("categoria_cognitiva") or
        dati.get("categoria_cognitiva") == "curiosita"
    ) and categoria_inferita != "curiosita":
        dati["categoria_cognitiva"] = categoria_inferita

    categoria_aggiornata = (
        categoria_precedente != dati.get("categoria_cognitiva")
    )

    if (
        not dati.get("azione_cognitiva_origine") or
        dati.get("azione_cognitiva_origine") == "curiosita_controllata"
    ) and azione_inferita != "curiosita_controllata":
        dati["azione_cognitiva_origine"] = azione_inferita

    if (
        not dati.get("motivo_generazione") or
        categoria_aggiornata or
        (
            dati.get("categoria_cognitiva") != "curiosita" and
            "situazione nuova" in dati.get("motivo_generazione", "")
        )
    ):
        dati["motivo_generazione"] = _motivo_generazione(
            dati.get("categoria_cognitiva", categoria_inferita),
            eventi_attivi
        )

    if (
        not dati.get("contesto_semantico") or
        categoria_aggiornata or
        "categoria=curiosita" in dati.get("contesto_semantico", "")
    ):
        dati["contesto_semantico"] = _contesto_semantico(
            dati.get("categoria_cognitiva", categoria_inferita),
            dati.get("azione_cognitiva_origine", azione_inferita),
            eventi_attivi,
            dati.get("stato_robot_origine", {})
        )

    if not dati.get("eventi_attivi_origine") and eventi_attivi:
        dati["eventi_attivi_origine"] = eventi_attivi

    return dati


def _leggi_json(path_file):
    if not os.path.exists(path_file):
        return None

    try:
        with codecs.open(path_file, "r", "utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(u"[COND_MEMORY] Errore lettura metadati {}: {}".format(
            path_file,
            e
        ))
        return None


def _scrivi_json(path_file, dati):
    try:
        with codecs.open(path_file, "w", "utf-8") as f:
            json.dump(
                dati,
                f,
                ensure_ascii=False,
                indent=2,
                sort_keys=True
            )
        return True

    except Exception as e:
        logger.warning(u"[COND_MEMORY] Errore scrittura metadati {}: {}".format(
            path_file,
            e
        ))
        return False


def crea_metadati_base(nome_condizione, mondo, eventi, stato_robot=None, origine="autogenerata"):
    """
    Crea la struttura standard dei metadati per una condizione autonoma.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    if eventi is None:
        eventi = {}

    if stato_robot is None:
        stato_robot = {}

    eventi_attivi = _eventi_attivi_da_eventi(eventi)
    metadati_cognitivi = _crea_metadati_cognitivi(
        mondo,
        eventi,
        eventi_attivi,
        stato_robot
    )

    metadati = {
        "nome": nome_condizione,
        "file_python": nome_condizione + ".py",
        "origine": origine,
        "stato": "promossa",

        "creata_il": _adesso(),
        "aggiornata_il": _adesso(),

        "mondo_origine": mondo,
        "eventi_attivi_origine": eventi_attivi,
        "eventi_completi_origine": eventi,

        "stato_robot_origine": stato_robot,

        "statistiche": {
            "attivazioni": 0,
            "errori_runtime": 0,
            "rifiuti": 0,
            "ultima_attivazione": "",
            "ultimo_errore": ""
        },

        "validazione": {
            "struttura": "ok",
            "modulo": "ok",
            "semantica": "ok"
        },

        "riparazione": {
            "tentativi": 0,
            "successi": 0,
            "fallimenti": 0,
            "ultimo_esito": "",
            "ultimo_motivo": ""
        },

        "note": [
            "Condizione generata autonomamente da NAO.",
            "Il file Python contiene la logica eseguibile.",
            "Questo JSON contiene la memoria e la tracciabilità della condizione."
        ]
    }

    metadati.update(metadati_cognitivi)

    return metadati


def salva_metadati_condizione(nome_condizione, mondo, eventi, stato_robot=None, origine="autogenerata"):
    """
    Salva il file .meta.json accanto alla condizione generata.
    """

    _assicura_cartelle()

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)

    metadati = crea_metadati_base(
        nome_condizione,
        mondo,
        eventi,
        stato_robot,
        origine
    )

    ok = _scrivi_json(path_file, metadati)

    if ok:
        logger.info(u"[COND_MEMORY] Metadati creati per {}".format(nome_condizione))

    return ok


def leggi_metadati_condizione(nome_condizione):
    """
    Legge i metadati di una condizione generata.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    return _assicura_metadati_cognitivi(_leggi_json(path_file))


def memoria_cognitiva_condizioni(limite=8):
    """
    Restituisce un riassunto compatto delle condizioni gia' apprese.

    Serve al generatore per comportarsi in modo piu' simile a una memoria
    cognitiva: vede perche' esistono condizioni precedenti senza leggere
    o modificare il loro codice Python.
    """

    _assicura_cartelle()

    risultati = []

    try:
        nomi_file = os.listdir(METADATA_DIR)
    except Exception:
        nomi_file = []

    for nome_file in nomi_file:
        if not nome_file.endswith(".meta.json"):
            continue

        path_file = os.path.join(METADATA_DIR, nome_file)
        dati = _assicura_metadati_cognitivi(_leggi_json(path_file))

        if not dati:
            continue

        statistiche = dati.get("statistiche", {})
        riparazione = dati.get("riparazione", {})
        esempi_positivi = dati.get("esempi_positivi", [])
        esempi_negativi = dati.get("esempi_negativi", [])

        risultati.append({
            "nome": dati.get("nome", nome_file.replace(".meta.json", "")),
            "categoria_cognitiva": dati.get("categoria_cognitiva", "curiosita"),
            "azione_cognitiva_origine": dati.get(
                "azione_cognitiva_origine",
                "curiosita_controllata"
            ),
            "motivo_generazione": _testo_breve(
                dati.get("motivo_generazione", ""),
                160
            ),
            "contesto_semantico": _testo_breve(
                dati.get("contesto_semantico", ""),
                180
            ),
            "eventi_attivi_origine": dati.get("eventi_attivi_origine", []),
            "attivazioni": statistiche.get("attivazioni", 0),
            "errori_runtime": statistiche.get("errori_runtime", 0),
            "rifiuti": statistiche.get("rifiuti", 0),
            "numero_riparazioni": dati.get(
                "numero_riparazioni",
                riparazione.get("tentativi", 0)
            ),
            "numero_esempi_positivi": len(esempi_positivi),
            "numero_esempi_negativi": len(esempi_negativi),
            "esempi_positivi": _riassumi_esempi(
                esempi_positivi,
                limite=2
            ),
            "esempi_negativi": _riassumi_esempi(
                esempi_negativi,
                limite=2
            )
        })

    def chiave_ordinamento(voce):
        statistiche_positive = voce.get("attivazioni", 0)
        penalita = (
            voce.get("errori_runtime", 0) +
            voce.get("rifiuti", 0) +
            voce.get("numero_riparazioni", 0)
        )
        return (statistiche_positive - penalita, statistiche_positive)

    risultati = sorted(
        risultati,
        key=chiave_ordinamento,
        reverse=True
    )

    return risultati[:limite]


def trova_condizioni_simili(mondo, eventi=None, limite=5):
    """
    Recupera condizioni gia' apprese semanticamente vicine al mondo corrente.

    Non esegue condizioni e non modifica file: serve come retrieval cognitivo
    per supervisore/generatore.
    """

    if eventi is None:
        eventi = {}

    eventi_attivi = []
    if isinstance(eventi, dict):
        eventi_attivi = _eventi_attivi_da_eventi(eventi)

    if not eventi_attivi:
        eventi_attivi = _eventi_da_metadati({
            "nome": "",
            "mondo_origine": mondo,
            "eventi_attivi_origine": [],
            "eventi_completi_origine": {},
            "esempi_positivi": [
                {
                    "mondo": mondo
                }
            ],
            "esempi_negativi": []
        })

    categoria = _categoria_cognitiva_da_eventi(eventi_attivi, mondo)
    token_mondo = set(_tokenizza_testo(mondo))

    for evento in eventi_attivi:
        for pezzo in str(evento).replace("_", " ").split():
            token_mondo.add(pezzo.lower())

    candidati = []

    for voce in memoria_cognitiva_condizioni(limite=9999):
        punteggio = 0
        motivi = []

        if voce.get("categoria_cognitiva") == categoria:
            punteggio += 5
            motivi.append("categoria")

        eventi_voce = [
            str(e).lower()
            for e in voce.get("eventi_attivi_origine", [])
        ]

        for evento in eventi_attivi:
            evento_norm = str(evento).lower()

            if evento_norm in eventi_voce:
                punteggio += 4
                motivi.append("evento:{}".format(evento_norm))
                continue

            pezzi = [
                p for p in evento_norm.replace("_", " ").split()
                if len(p) >= 3
            ]

            for evento_voce in eventi_voce:
                if any(p in evento_voce for p in pezzi):
                    punteggio += 1
                    motivi.append("evento_parziale:{}".format(evento_norm))
                    break

        token_voce = set(_token_da_voce_memoria(voce))
        overlap = token_mondo.intersection(token_voce)

        if overlap:
            incremento = min(len(overlap), 4)
            punteggio += incremento
            motivi.append("testo:{}".format(",".join(sorted(list(overlap))[:4])))

        numero_positivi = voce.get("numero_esempi_positivi", 0)
        numero_negativi = voce.get("numero_esempi_negativi", 0)

        if numero_positivi > 0:
            punteggio += min(numero_positivi, 2)

        if numero_negativi > 0:
            punteggio -= min(numero_negativi, 3)

        if punteggio < 2:
            continue

        risultato = dict(voce)
        risultato["punteggio_similarita"] = punteggio
        risultato["motivi_similarita"] = motivi
        candidati.append(risultato)

    candidati = sorted(
        candidati,
        key=lambda voce: voce.get("punteggio_similarita", 0),
        reverse=True
    )

    return candidati[:limite]


def aggiorna_metadati_condizione(nome_condizione, aggiornamenti):
    """
    Aggiorna parzialmente i metadati di una condizione.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)

    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "attiva",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            },
            "note": []
        }

    dati = _assicura_metadati_cognitivi(dati)

    for chiave, valore in aggiornamenti.items():
        dati[chiave] = valore

    dati["aggiornata_il"] = _adesso()

    return _scrivi_json(path_file, dati)


def registra_attivazione(nome_condizione, mondo=None, decisione=None):
    """
    Registra che una condizione è stata attivata con successo.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "attiva",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            },
            "attivazioni_recenti": []
        }

    dati = _assicura_metadati_cognitivi(dati)

    if "statistiche" not in dati:
        dati["statistiche"] = {}

    dati["statistiche"]["attivazioni"] = dati["statistiche"].get("attivazioni", 0) + 1
    dati["statistiche"]["ultima_attivazione"] = _adesso()
    dati["aggiornata_il"] = _adesso()

    if "attivazioni_recenti" not in dati:
        dati["attivazioni_recenti"] = []

    dati["attivazioni_recenti"].append({
        "tempo": _adesso(),
        "mondo": mondo or "",
        "decisione": decisione or {}
    })

    dati["attivazioni_recenti"] = dati["attivazioni_recenti"][-5:]

    if "esempi_positivi" not in dati:
        dati["esempi_positivi"] = []

    dati["esempi_positivi"] = _aggiungi_esempio_unico(
        dati["esempi_positivi"],
        {
            "tempo": _adesso(),
            "mondo": _testo_breve(mondo or ""),
            "decisione": decisione or {},
            "fonte": "attivazione_reale"
        },
        limite=8
    )

    return _scrivi_json(path_file, dati)


def registra_errore_condizione(nome_condizione, errore):
    """
    Registra un errore runtime associato a una condizione.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "problematica",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            },
            "errori_recenti": []
        }

    dati = _assicura_metadati_cognitivi(dati)

    if "statistiche" not in dati:
        dati["statistiche"] = {}

    dati["statistiche"]["errori_runtime"] = dati["statistiche"].get("errori_runtime", 0) + 1
    dati["statistiche"]["ultimo_errore"] = str(errore)
    dati["aggiornata_il"] = _adesso()

    if "errori_recenti" not in dati:
        dati["errori_recenti"] = []

    dati["errori_recenti"].append({
        "tempo": _adesso(),
        "errore": str(errore)
    })

    dati["errori_recenti"] = dati["errori_recenti"][-5:]

    if "esempi_negativi" not in dati:
        dati["esempi_negativi"] = []

    dati["esempi_negativi"] = _aggiungi_esempio_unico(
        dati["esempi_negativi"],
        {
            "tempo": _adesso(),
            "mondo": "",
            "motivo": str(errore),
            "fonte": "errore_runtime"
        },
        limite=8
    )

    return _scrivi_json(path_file, dati)


def marca_condizione_rifiutata(nome_condizione, motivo):
    """
    Marca nei metadati che una condizione è stata rifiutata o spostata.
    """

    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "creata_il": _adesso(),
            "statistiche": {
                "attivazioni": 0,
                "errori_runtime": 0,
                "rifiuti": 0,
                "ultima_attivazione": "",
                "ultimo_errore": ""
            }
        }

    dati = _assicura_metadati_cognitivi(dati)

    dati["stato"] = "rifiutata"
    dati["motivo_rifiuto"] = str(motivo)
    dati["aggiornata_il"] = _adesso()

    if "statistiche" not in dati:
        dati["statistiche"] = {}

    dati["statistiche"]["rifiuti"] = dati["statistiche"].get("rifiuti", 0) + 1

    if "esempi_negativi" not in dati:
        dati["esempi_negativi"] = []

    dati["esempi_negativi"] = _aggiungi_esempio_unico(
        dati["esempi_negativi"],
        {
            "tempo": _adesso(),
            "mondo": "",
            "motivo": str(motivo),
            "fonte": "rifiuto_validatore"
        },
        limite=8
    )

    return _scrivi_json(path_file, dati)

def valuta_affidabilita_condizione(nome_condizione):
    """
    Valuta se una condizione deve essere mantenuta, rigenerata o disattivata
    usando i suoi metadati.
    """

    dati = leggi_metadati_condizione(nome_condizione)

    if dati is None:
        return {
            "azione": "mantieni",
            "motivo": "metadati assenti, mantengo per prudenza"
        }

    statistiche = dati.get("statistiche", {})

    attivazioni = statistiche.get("attivazioni", 0)
    errori = statistiche.get("errori_runtime", 0)
    rifiuti = statistiche.get("rifiuti", 0)
    esempi_positivi = dati.get("esempi_positivi", [])
    esempi_negativi = dati.get("esempi_negativi", [])
    numero_positivi = len(esempi_positivi)
    numero_negativi = len(esempi_negativi)

    if (
        numero_negativi >= 3 and
        numero_negativi >= numero_positivi + 2
    ):
        return {
            "azione": "disattiva",
            "motivo": (
                "troppi esempi negativi rispetto ai positivi: {} vs {}"
                .format(numero_negativi, numero_positivi)
            )
        }

    if (
        numero_negativi >= 2 and
        numero_negativi >= numero_positivi and
        (errori > 0 or rifiuti > 0)
    ):
        return {
            "azione": "rigenera",
            "motivo": (
                "memoria esperienziale fragile: {} negativi, {} positivi"
                .format(numero_negativi, numero_positivi)
            )
        }

    if rifiuti >= 2:
        return {
            "azione": "disattiva",
            "motivo": "troppi rifiuti registrati"
        }

    if errori >= 3:
        return {
            "azione": "rigenera",
            "motivo": "troppi errori runtime"
        }

    if attivazioni >= 3 and errori == 0 and rifiuti == 0:
        return {
            "azione": "mantieni",
            "motivo": "condizione affidabile"
        }

    if numero_positivi >= 2 and numero_negativi == 0:
        return {
            "azione": "mantieni",
            "motivo": "memoria esperienziale positiva"
        }

    return {
        "azione": "mantieni",
        "motivo": "nessun segnale critico"
    }

def registra_esito_riparazione(nome_condizione, esito):
    if nome_condizione.endswith(".py"):
        nome_condizione = nome_condizione[:-3]

    path_file = _meta_path(nome_condizione)
    dati = _leggi_json(path_file)

    if dati is None:
        dati = {
            "nome": nome_condizione,
            "file_python": nome_condizione + ".py",
            "origine": "sconosciuta",
            "stato": "problematica",
            "creata_il": _adesso(),
            "aggiornata_il": _adesso()
        }

    dati = _assicura_metadati_cognitivi(dati)

    if "riparazione" not in dati:
        dati["riparazione"] = {
            "tentativi": 0,
            "successi": 0,
            "fallimenti": 0,
            "ultimo_esito": "",
            "ultimo_motivo": ""
        }

    dati["riparazione"]["tentativi"] += 1
    dati["numero_riparazioni"] = dati["riparazione"]["tentativi"]
    dati["riparazione"]["ultimo_esito"] = esito.get("status", "")
    dati["riparazione"]["ultimo_motivo"] = esito.get("reason", "")

    if esito.get("success"):
        dati["riparazione"]["successi"] += 1
    else:
        dati["riparazione"]["fallimenti"] += 1

    dati["aggiornata_il"] = _adesso()

    return _scrivi_json(path_file, dati)
