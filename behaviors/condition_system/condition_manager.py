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
try:
    import importlib.util
except ImportError:
    importlib = None

try:
    import imp
except ImportError:
    imp = None
import time
import shutil
import sys

from behaviors.condition_system.condition_memory import (
    registra_attivazione,
    registra_errore_condizione,
    marca_condizione_rifiutata,
    valuta_affidabilita_condizione,
    registra_esito_riparazione
)

from behaviors.condition_system.condition_repair import tenta_riparazione_condizione

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
CONDIZIONI_DIR = os.path.join(BASE_DIR, "generated_conditions")
REJECTED_DIR = os.path.join(BASE_DIR, "rejected_conditions")

_condizioni_cache = None
_firma_cache_condizioni = None
_ultima_attivazione_condizione = {}
_ultima_firma_condizione = {}
_errori_condizione = {}

# Evita loop: una stessa condizione sullo stesso evento non viene rieseguita subito.
COOLDOWN_CONDIZIONE = 8

# Dopo questo numero di errori runtime, la condizione viene disattivata.
MAX_ERRORI_CONDIZIONE = 3


def reset_cache_condizioni():
    global _condizioni_cache
    global _firma_cache_condizioni
    _condizioni_cache = None
    _firma_cache_condizioni = None


def _firma_cartella_condizioni():
    """
    Restituisce una firma dello stato reale di generated_conditions.
    Serve per capire se una condizione e' stata spostata, eliminata o rigenerata
    mentre soul.py e' ancora acceso.
    """

    _assicura_cartelle()

    firma = []

    try:
        nomi_file = os.listdir(CONDIZIONI_DIR)
    except Exception:
        nomi_file = []

    for nome_file in nomi_file:
        if not nome_file.endswith(".py"):
            continue

        if nome_file.startswith("__"):
            continue

        path_file = os.path.join(CONDIZIONI_DIR, nome_file)

        try:
            stat = os.stat(path_file)
            firma.append((nome_file, stat.st_mtime, stat.st_size))
        except OSError:
            continue

    return tuple(sorted(firma))


def _rimuovi_modulo_da_memoria(nome_modulo):
    """
    Rimuove dalla memoria Python una condizione gia' caricata.
    Questo risolve il bug: se il file .py viene spostato in rejected_conditions,
    NAO non deve continuare a usare la vecchia condizione rimasta in cache.
    """

    if nome_modulo.endswith(".py"):
        nome_modulo = nome_modulo[:-3]

    try:
        if nome_modulo in sys.modules:
            del sys.modules[nome_modulo]
    except Exception:
        pass


def _pulisci_bytecode_condizione(nome_modulo):
    """
    Elimina eventuali .pyc/.pyo rimasti.
    Utile soprattutto con Python 2 sul robot NAO.
    """

    if nome_modulo.endswith(".py"):
        nome_modulo = nome_modulo[:-3]

    possibili = [
        os.path.join(CONDIZIONI_DIR, nome_modulo + ".pyc"),
        os.path.join(CONDIZIONI_DIR, nome_modulo + ".pyo"),
    ]

    for path in possibili:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(u"[CONDIZIONI] Bytecode rimosso: {}".format(path))
        except Exception as e:
            logger.warning(u"[CONDIZIONI] Impossibile rimuovere bytecode {}: {}".format(path, e))


def _assicura_cartelle():
    if not os.path.exists(CONDIZIONI_DIR):
        os.makedirs(CONDIZIONI_DIR)

    if not os.path.exists(REJECTED_DIR):
        os.makedirs(REJECTED_DIR)

def _firma_evento_corrente(mondo, stato_runtime):
    """
    Crea una firma stabile dell'evento corrente.
    Serve per evitare che la stessa condizione venga eseguita in loop
    mentre l'evento resta ancora nei recenti.
    """
    parti = []

    try:
        evento_strutturato = stato_runtime.get("evento_strutturato", {})
        if isinstance(evento_strutturato, dict):
            for chiave in sorted(evento_strutturato.keys()):
                parti.append("{}={}".format(chiave, evento_strutturato.get(chiave)))
    except:
        pass

    try:
        eventi = stato_runtime.get("eventi", {})
        if isinstance(eventi, dict):
            for chiave in sorted(eventi.keys()):
                if eventi.get(chiave):
                    parti.append("evento:{}".format(chiave))
    except:
        pass

    if not parti:
        testo = (mondo or "").lower().strip()
        parti.append(testo[:180])

    return "|".join(parti)

def _path_condizione(nome_modulo):
    if nome_modulo.endswith(".py"):
        nome_modulo = nome_modulo[:-3]

    return os.path.join(CONDIZIONI_DIR, nome_modulo + ".py")


def _sposta_in_rejected(nome_modulo, motivo, mondo=None, stato_runtime=None):
    """
    Sposta una condizione difettosa fuori da generated_conditions.

    Fase 4:
    - sposta il file .py in rejected_conditions;
    - aggiorna e sposta il file .meta.json;
    - prova a riparare automaticamente la condizione, se possibile.
    """

    _assicura_cartelle()

    if nome_modulo.endswith(".py"):
        nome_modulo = nome_modulo[:-3]

    origine_py = os.path.join(CONDIZIONI_DIR, nome_modulo + ".py")
    origine_meta = os.path.join(CONDIZIONI_DIR, nome_modulo + ".meta.json")

    timestamp = time.strftime("%Y%m%d_%H%M%S")

    destinazione_py = os.path.join(
        REJECTED_DIR,
        nome_modulo + "_rejected_" + timestamp + ".py"
    )

    destinazione_meta = os.path.join(
        REJECTED_DIR,
        nome_modulo + "_rejected_" + timestamp + ".meta.json"
    )

    try:
        try:
            marca_condizione_rifiutata(nome_modulo, motivo)
        except Exception as e:
            logger.warning(u"[CONDIZIONI] Impossibile aggiornare metadati rifiuto {}: {}".format(
                nome_modulo,
                e
            ))

        if os.path.exists(origine_py):
            shutil.move(origine_py, destinazione_py)

        if os.path.exists(origine_meta):
            shutil.move(origine_meta, destinazione_meta)

        _rimuovi_modulo_da_memoria(nome_modulo)
        _pulisci_bytecode_condizione(nome_modulo)

        logger.warning(u"[CONDIZIONI] Condizione spostata in rejected_conditions: {} | motivo: {}".format(
            nome_modulo,
            motivo
        ))

        try:
            esito_riparazione = tenta_riparazione_condizione(
                nome_modulo,
                motivo,
                mondo,
                stato_runtime
            )

            try:
                registra_esito_riparazione(nome_modulo, esito_riparazione)
            except Exception as e:
                logger.warning(u"[CONDIZIONI] Impossibile registrare esito riparazione {}: {}".format(
                    nome_modulo,
                    e
                ))

            if not isinstance(esito_riparazione, dict):
                logger.warning(u"[CONDIZIONI] Riparazione fallita per {} | esito non valido: {}".format(
                    nome_modulo,
                    esito_riparazione
                ))

            elif esito_riparazione.get("success"):
                logger.warning(u"[CONDIZIONI] Riparazione riuscita per {} | nuova condizione: {}".format(
                    nome_modulo,
                    esito_riparazione.get("new_path")
                ))

            else:
                logger.warning(u"[CONDIZIONI] Riparazione fallita per {} | stato: {} | motivo: {}".format(
                    nome_modulo,
                    esito_riparazione.get("status"),
                    esito_riparazione.get("reason")
                ))

        except Exception as e:
            logger.warning(u"[CONDIZIONI] Errore imprevisto nella riparazione automatica di {}: {}".format(
                nome_modulo,
                e
            ))

    except Exception as e:
        logger.error(u"[CONDIZIONI] Impossibile spostare {} in rejected_conditions: {}".format(
            nome_modulo,
            e
        ))

    reset_cache_condizioni()


def _registra_errore(nome_modulo, errore, mondo=None, stato_runtime=None):
    """
    Registra un errore runtime di una condizione.

    Ritorna:
    - True se la condizione e' stata spostata in rejected;
    - False altrimenti.
    """

    if nome_modulo.endswith(".py"):
        nome_base = nome_modulo[:-3]
    else:
        nome_base = nome_modulo

    numero_errori = _errori_condizione.get(nome_base, 0) + 1
    _errori_condizione[nome_base] = numero_errori

    try:
        registra_errore_condizione(nome_base, errore)
    except Exception as e:
        logger.warning(u"[CONDIZIONI] Errore aggiornamento memoria condizione {}: {}".format(
            nome_base,
            e
        ))

    logger.warning(u"[CONDIZIONI] Errore runtime in {} ({}/{}): {}".format(
        nome_base,
        numero_errori,
        MAX_ERRORI_CONDIZIONE,
        errore
    ))

    if numero_errori >= MAX_ERRORI_CONDIZIONE:
        _sposta_in_rejected(
            nome_base,
            errore,
            mondo,
            stato_runtime
        )
        return True

    return False

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

def _carica_modulo_da_file(nome_modulo, path_file):
    """
    Carica un modulo Python da file.
    Compatibile sia con Python 3 sia con Python 2.7/NAO.
    """
    _rimuovi_modulo_da_memoria(nome_modulo)

    if importlib is not None:
        try:
            spec = importlib.util.spec_from_file_location(nome_modulo, path_file)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
            return modulo
        except Exception:
            pass

    if imp is not None:
        return imp.load_source(nome_modulo, path_file)

    raise ImportError("Nessun sistema disponibile per caricare il modulo")

def carica_condizioni_generate():
    global _condizioni_cache
    global _firma_cache_condizioni

    _assicura_cartelle()

    firma_attuale = _firma_cartella_condizioni()

    if _condizioni_cache is not None and _firma_cache_condizioni == firma_attuale:
        return _condizioni_cache

    if _condizioni_cache is not None and _firma_cache_condizioni != firma_attuale:
        logger.info(u"[CONDIZIONI] Cartella condizioni cambiata: ricarico cache")

    condizioni = []

    for nome_file in ordina_condizioni_per_priorita(os.listdir(CONDIZIONI_DIR)):
        if not nome_file.endswith(".py"):
            continue

        if nome_file.startswith("__"):
            continue

        nome_modulo = nome_file.replace(".py", "")
        path_file = os.path.join(CONDIZIONI_DIR, nome_file)

        try:
            modulo = _carica_modulo_da_file(nome_modulo, path_file)

            if not hasattr(modulo, "condizione"):
                _sposta_in_rejected(nome_modulo, "manca funzione condizione")
                continue

            if not hasattr(modulo, "comportamento"):
                _sposta_in_rejected(nome_modulo, "manca funzione comportamento")
                continue

            condizioni.append({
                "nome": nome_file,
                "modulo": modulo,
                "condizione": modulo.condizione,
                "comportamento": modulo.comportamento
            })

        except Exception as e:
            logger.warning(u"[CONDIZIONI] Errore caricamento {}: {}".format(
                nome_file,
                e
            ))
            _sposta_in_rejected(nome_modulo, str(e))

    condizioni.sort(
        key=lambda item: _priorita_condizione(item["nome"]),
        reverse=True
    )

    _condizioni_cache = condizioni
    _firma_cache_condizioni = firma_attuale
    return condizioni

def punteggio_specificita_condizione(nome_file):
    """
    Assegna un punteggio alla condizione.
    Piu' il punteggio e' alto, prima viene valutata.

    Obiettivo:
    - condizioni composte prima delle semplici
    - volto riconosciuto prima di tocco generico
    - ostacolo + tocco prima di solo ostacolo
    """

    nome = nome_file.lower()
    punteggio = 0

    # Le condizioni composte spesso hanno "_e_"
    if "_e_" in nome:
        punteggio += 100

    # Più parole specifiche contiene, più è importante
    parole_specifiche = [
        "volto_riconosciuto",
        "volto",
        "riconosciuto",
        "ostacolo",
        "sinistra",
        "destra",
        "mano",
        "piede",
        "testa",
        "fermo",
        "interazione",
        "utente"
    ]

    for parola in parole_specifiche:
        if parola in nome:
            punteggio += 10

    # Le condizioni troppo generiche devono arrivare dopo
    if "tocco_mano_sinistra" in nome:
        punteggio -= 5

    if "tocco_mano_destra" in nome:
        punteggio -= 5

    if "carezza_testa" in nome:
        punteggio -= 5

    return punteggio


def ordina_condizioni_per_priorita(lista_file):
    """
    Ordina i file condizione dalla piu' specifica alla piu' generica.
    """

    return sorted(
        lista_file,
        key=lambda nome: punteggio_specificita_condizione(nome),
        reverse=True
    )

def _decisione_coerente_con_mondo(decisione, mondo, nome_condizione):
    """
    Controlla che una decisione generata sia coerente con il mondo attuale.
    Serve a impedire che vecchie condizioni sbagliate restino attive.
    """

    if not isinstance(decisione, dict):
        return False, "decisione non e' un dizionario"

    azioni = decisione.get("azioni", [])

    if not isinstance(azioni, list):
        return False, "azioni non e' una lista"

    testo_mondo = (mondo or "").lower()
    nome = (nome_condizione or "").lower()

    nome_spaziale = (
        "ostacolo" in nome or
        "oggetto_vicino" in nome or
        "sinistra" in nome or
        "destra" in nome or
        "frontale" in nome
    )

    nome_sociale = (
        "carezza" in nome or
        "mano" in nome or
        "volto" in nome or
        "entrambe" in nome
    )

    mondo_spaziale = nome_spaziale and not nome_sociale

    mondo_sociale = (
        "carezza" in testo_mondo or
        "mano" in testo_mondo or
        "volto" in testo_mondo or
        "riconosco" in testo_mondo
    )

    frasi_sociali_non_coerenti = [
        "ciao",
        "come stai",
        "cosa stai facendo",
        "come posso aiutarti",
        "come ti senti",
        "cosa c'e' qui",
        "cosa c'è qui",
        "cosa c'e' intorno",
        "cosa c'è intorno",
        "cosa vedi"
    ]

    frasi_spostamento = [
        "mi sposto",
        "mi muovo",
        "mi allontano",
        "evito",
        "aggiro"
    ]

    robot_fermo = "sono fermo" in testo_mondo
    robot_camminando = "sto camminando" in testo_mondo

    for azione in azioni:
        if not isinstance(azione, dict):
            return False, "azione non e' un dizionario"

        tipo = azione.get("tipo", "")

        if tipo == "parla":
            testo_azione = azione.get("testo", "").lower()

            if mondo_spaziale:
                for frase in frasi_sociali_non_coerenti:
                    if frase in testo_azione:
                        return False, "frase sociale non coerente con mondo spaziale"

            if robot_fermo and not robot_camminando:
                for frase in frasi_spostamento:
                    if frase in testo_azione:
                        return False, "frase di spostamento non coerente da fermo"

        if tipo in ["cammina", "gira"]:
            if robot_fermo and not robot_camminando:
                return False, "movimento non coerente quando il robot e' fermo"

    return True, "ok"

def _condizione_ammessa_per_evento(nome_condizione, mondo, stato_runtime):
    """
    Filtra condizioni troppo generiche usando la firma evento strutturata.

    Regola centrale:
    - le condizioni esistenti possono attivarsi solo se coerenti con evento_strutturato;
    - gli eventi unknown/scoperta NON devono essere intercettati da condizioni vecchie;
    - eventi composti richiedono condizioni composte;
    - durante cammino servono condizioni specifiche durante_cammino.
    """

    nome = (nome_condizione or "").lower()
    nome_evento = nome.replace("condizione_", "").replace(".py", "")

    
    eventi = stato_runtime.get("eventi", {})
    eventi_reali = stato_runtime.get("eventi_reali", {})
    evento_strutturato = stato_runtime.get("evento_strutturato", {})

    if not isinstance(eventi, dict):
        eventi = {}

    if not isinstance(eventi_reali, dict):
        eventi_reali = {}

    if not isinstance(evento_strutturato, dict):
        evento_strutturato = {}

    tipo = str(evento_strutturato.get("tipo", "")).lower()
    categoria = str(evento_strutturato.get("categoria", "")).lower()
    origine = str(evento_strutturato.get("origine", "")).lower()
    direzione = str(evento_strutturato.get("direzione", "")).lower()

    eventi_core = evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        eventi_core = []

    camminando = (
        evento_strutturato.get("camminando", False) or
        eventi.get("camminando", False) or
        eventi_reali.get("camminando", False)
    )

    if tipo == "tocco_mano" and not camminando:

        if direzione == "sinistra":
            return (
                "mano_sinistra" in nome
                or "tocco_mano_sinistra" in nome
            )

        if direzione == "destra":
            return (
                "mano_destra" in nome
                or "tocco_mano_destra" in nome
            )

        return "entrambe_mani" in nome
    
    # Un evento sconosciuto/scoperto non deve essere catturato da condizioni vecchie.
    # Deve tornare al supervisore, che genera nuova condizione autonoma.
    if (
        tipo in ["unknown", "sconosciuto", "scoperta"]
        or categoria in ["unknown", "sconosciuta", "scoperta"]
        or origine in ["scoperta", "unknown"]
    ):
        eventi_core_norm = [
            str(e).lower().replace("-", "_")
            for e in eventi_core
        ]

        eventi_attivi_unknown = []
        for chiave, valore in eventi.items():
            if valore not in [False, None, "", [], {}]:
                eventi_attivi_unknown.append(
                    str(chiave).lower().replace("-", "_")
                )

        # Se esiste già una condizione generata esattamente per questo evento unknown,
        # allora può attivarsi. Altrimenti l'unknown deve tornare al supervisore.
        eventi_unknown_norm = set(eventi_core_norm + eventi_attivi_unknown)

        for ev in eventi_unknown_norm:
            ev = str(ev).lower().replace("-", "_").strip()

            if not ev:
                continue

            if (
                nome_evento == ev
                or nome_evento.endswith(ev)
                or ev in nome_evento
            ):
                return True

        return False

    eventi_attivi = []

    for chiave, valore in eventi.items():
        if valore not in [False, None, "", [], {}]:
            eventi_attivi.append(str(chiave).lower())

    for chiave, valore in eventi_reali.items():
        if valore not in [False, None, "", [], {}]:
            chiave_norm = str(chiave).lower()
            if chiave_norm not in eventi_attivi:
                eventi_attivi.append(chiave_norm)

    for chiave in eventi_core:
        chiave_norm = str(chiave).lower()
        if chiave_norm not in eventi_attivi:
            eventi_attivi.append(chiave_norm)

    eventi_significativi = [
        e for e in eventi_attivi
        if e not in [
            "fermo",
            "camminando",
            "batteria",
            "battery",
            "batteria_percentuale",
            "batteria_bassa",
            "batteria_critica"
        ]
    ]

    evento_composto = (
        evento_strutturato.get("evento_composto", False)
        or len(eventi_significativi) >= 2
    )

    # Se evento composto, una condizione semplice NON deve passare.
    if evento_composto:
        eventi_coperti = 0

        for evento in eventi_significativi:
            evento_norm = evento.replace("-", "_").lower()
            pezzi_evento = [
                pezzo.strip()
                for pezzo in evento_norm.split("_")
                if pezzo.strip()
            ]

            if not pezzi_evento:
                continue

            if any(pezzo in nome for pezzo in pezzi_evento):
                eventi_coperti += 1

        condizione_composta = (
            "_e_" in nome
            or "entrambe" in nome
            or eventi_coperti >= 2
        )

        if not condizione_composta:
            return False

    # Durante cammino servono condizioni specifiche.
    if camminando and "durante_cammino" not in nome:
        return False

    if camminando and tipo == "ostacolo":
        if direzione == "destra":
            return "ostacolo_destra_durante_cammino" in nome
        if direzione == "sinistra":
            return "ostacolo_sinistra_durante_cammino" in nome
        if direzione == "frontale":
            return "ostacolo_frontale_durante_cammino" in nome

    if camminando and tipo == "urto_piedi":
        return "urto_piedi_durante_cammino" in nome

    if camminando and tipo == "carezza":
        return "carezza_durante_cammino" in nome

    if camminando and tipo == "tocco_mano" and direzione == "sinistra":
        return "mano_sinistra_durante_cammino" in nome

    if camminando and tipo == "tocco_mano" and direzione == "destra":
        return "mano_destra_durante_cammino" in nome

    if camminando and tipo == "volto_riconosciuto":
        return "volto_riconosciuto_durante_cammino" in nome

    if camminando and tipo == "volto_ignoto":
        return "volto_ignoto_durante_cammino" in nome

    # Da fermo non deve passare una condizione durante_cammino.
    if not camminando and "durante_cammino" in nome:
        return False

    # Caso noto e semplice: passa solo se il nome evento è presente negli eventi attivi.
    if nome_evento in eventi_attivi:
        return True

    if tipo and tipo in nome:
        return True

    return True

def _condizione_visiva_bloccata_da_negativi(nome_file, mondo):
    """
    Evita che condizioni visive si attivino quando il testo dice
    chiaramente che NON ci sono contenuti leggibili.

    Esempio bug reale:
    monitor spento -> "Che interessante codice!"
    """

    try:
        nome_norm = (nome_file or "").lower()
        testo = (mondo or "").lower()
    except Exception:
        return False

    # Solo condizioni visuali unknown
    if "informazione_visiva" not in nome_norm:
        return False

    negativi = [
        "non ci sono elementi leggibili",
        "non ci sono elementi leggibili come testo",
        "non ci sono testi leggibili",
        "nessun testo visibile",
        "nessuna informazione leggibile",
        "non mostra alcun contenuto identificabile",
        "non mostra contenuto identificabile",
        "non contiene informazioni leggibili",
        "non contiene codice",
        "monitor spento",
        "schermo nero",
        "non e presente testo",
        "non e presente alcun testo",
        "non e' presente testo",
        "non e' presente alcun testo",
        "testo non leggibile",
        "codice non leggibile",
        "non ci sono monitor o computer visibili",
        "non ci sono monitor o computer visibili con contenuti leggibili",
        "non ci sono informazioni chiare",
        "testo leggibile definiti",
        "non e possibile leggere il testo in modo chiaro",
        "non e' possibile leggere il testo in modo chiaro",
        "lavagna nera con scritte e disegni",
        "non ci sono monitor o computer",
        "non ci sono schermi o monitor accesi",
        "non e presente testo leggibile ne codice",
        "non e' presente testo leggibile ne' codice",
        "interfaccia grafica senza contenuti chiari",
        "senza contenuti chiari",
        "non contengono informazioni visibili",
        "non contiene informazioni leggibili",
        "solo un monitor acceso",
        "testo non identificabile",
        "codice o testo non identificabile",
        "cartone di raccolta",
        "conferisci qui",
        "fogli fotocopie quaderni",
        "quaderni usati",
        "raccolta",
        "non ci sono schermi o computer accesi"
    ]

    for negativo in negativi:
        if negativo in testo:
            logger.info(
                u"[CONDIZIONI] Blocco condizione visiva per evidenza negativa: {}".format(
                    nome_file
                )
            )
            return True

    return False

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

        if not _condizione_ammessa_per_evento(nome, mondo, stato_runtime):
            logger.info(u"[CONDIZIONI] Ignoro condizione generica non adatta al contesto: {}".format(nome))
            continue

        valutazione = valuta_affidabilita_condizione(nome)
        logger.info(
            u"[CONDIZIONI][FIDUCIA] {} -> {} ({})".format(
                nome,
                valutazione.get("azione", "mantieni"),
                valutazione.get("motivo", "")
            )
        )

        if valutazione.get("azione") == "disattiva":
            logger.warning(u"[CONDIZIONI] Condizione ignorata per bassa affidabilita': {} | {}".format(
                nome,
                valutazione.get("motivo")
            ))
            continue

        try:
            firma_corrente = _firma_evento_corrente(mondo, stato_runtime)
            ultima_firma = _ultima_firma_condizione.get(nome)
            ultimo_tempo = _ultima_attivazione_condizione.get(nome, 0)

            if ultima_firma == firma_corrente and adesso - ultimo_tempo < COOLDOWN_CONDIZIONE:
                logger.info(u"[CONDIZIONI] Skip anti-loop: {} ancora in cooldown".format(nome))
                continue

            if _condizione_visiva_bloccata_da_negativi(
                nome,
                mondo
            ):
                continue

            condizione_vera = modulo.condizione(mondo, stato_runtime)

            if condizione_vera:
                logger.info(u"[CONDIZIONI] Attivata condizione generata: {}".format(nome))

                try:
                    try:
                        decisione = modulo.comportamento(
                            None,
                            stato_runtime.get("memoria", {}),
                            stato_runtime
                        )
                    except TypeError:
                        decisione = modulo.comportamento()

                except Exception as e:
                    spostata = _registra_errore(
                        nome,
                        e,
                        mondo,
                        stato_runtime
                    )

                    if spostata:
                        return None

                    continue

                coerente, motivo = _decisione_coerente_con_mondo(
                    decisione,
                    mondo,
                    nome
                )

                if not coerente:
                    logger.warning(u"[CONDIZIONI] Condizione incoerente, sposto in rejected: {} | {}".format(
                        nome,
                        motivo
                    ))

                    _sposta_in_rejected(
                        nome.replace(".py", ""),
                        motivo,
                        mondo,
                        stato_runtime
                    )

                    continue

                _ultima_attivazione_condizione[nome] = adesso
                _ultima_firma_condizione[nome] = firma_corrente
                try:
                    registra_attivazione(
                        nome.replace(".py", ""),
                        mondo,
                        decisione
                    )
                except Exception as e:
                    logger.warning(u"[CONDIZIONI] Errore registrazione attivazione condizione: {}".format(e))

                return decisione

        except Exception as e:
            _registra_errore(
                nome,
                e,
                mondo,
                stato_runtime
            )
            continue

    # Arrivo qui solo se nessuna condizione esistente si e' attivata.
    # La generazione autonoma NON deve stare qui.
    # Deve essere centralizzata in autonomy_supervisor.py.
    logger.info(u"[CONDIZIONI] Nessuna condizione generata attiva per il mondo corrente")
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