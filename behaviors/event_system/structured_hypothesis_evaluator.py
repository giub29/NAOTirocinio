# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    basestring
except NameError:
    basestring = str


def _testo(valore):
    try:
        if isinstance(valore, basestring):
            return valore.lower().strip()
        return str(valore or "").lower().strip()
    except Exception:
        return ""


def _numero(valore, default=0.0):
    try:
        return float(valore)
    except Exception:
        return default


def _tentativi(ipotesi):
    try:
        return int(ipotesi.get("tentativi", 0) or 0)
    except Exception:
        return 0


def _copia_ipotesi(ipotesi):
    aggiornata = dict(ipotesi)
    return aggiornata


def _evento_strutturato_puo_generare(evento):
    if not isinstance(evento, dict):
        return False

    categoria = _testo(evento.get("categoria"))
    stato = _testo(evento.get("stato"))
    tipo = _testo(evento.get("tipo"))

    if categoria in ["", "neutra", "ambiguita", "supporto_informativo"]:
        return False

    eventi_core = evento.get("eventi_core", [])
    if not isinstance(eventi_core, list):
        return False

    eventi_core = [
        e for e in eventi_core
        if e not in [None, False, "", [], {}]
    ]
    eventi_core_norm = [_testo(e) for e in eventi_core]

    if len(eventi_core) == 0:
        return False

    if (
        stato in ["potenziale", "non_disponibile"]
        or tipo in [
            "supporto_informativo_potenziale",
            "supporto_informativo_non_disponibile"
        ]
        or "supporto_informativo_potenziale" in eventi_core_norm
        or "supporto_informativo_non_disponibile" in eventi_core_norm
    ):
        return False

    ragionamento = evento.get("ragionamento_unknown", {})
    if (
        isinstance(ragionamento, dict)
        and "evento" in ragionamento
        and ragionamento.get("evento") in [None, False, "", [], {}]
    ):
        return False

    return True


def _supporto_informativo_peggiorato_ma_inconclusivo(
    categoria_ipotesi,
    stato_ipotesi,
    categoria_nuova,
    stato_nuovo
):
    return (
        categoria_ipotesi == "supporto_informativo"
        and stato_ipotesi == "potenziale"
        and categoria_nuova == "supporto_informativo"
        and stato_nuovo == "non_disponibile"
    )


def _esito(
    ha_ipotesi,
    stato,
    genera_condizione,
    motivo,
    azione_successiva,
    ipotesi
):
    return {
        "ha_ipotesi": ha_ipotesi,
        "stato": stato,
        "genera_condizione": genera_condizione,
        "motivo": motivo,
        "azione_successiva": azione_successiva,
        "ipotesi": ipotesi
    }


def valuta_ipotesi_da_evento_strutturato(
    ipotesi,
    nuovo_evento_strutturato,
    nuovo_mondo=None
):
    if not isinstance(ipotesi, dict):
        return _esito(
            False,
            "assente",
            False,
            "nessuna ipotesi temporanea",
            None,
            None
        )

    if not isinstance(nuovo_evento_strutturato, dict):
        nuovo_evento_strutturato = {}

    aggiornata = _copia_ipotesi(ipotesi)
    categoria_ipotesi = _testo(ipotesi.get("categoria"))
    stato_ipotesi = _testo(ipotesi.get("stato"))
    categoria_nuova = _testo(nuovo_evento_strutturato.get("categoria"))
    stato_nuovo = _testo(nuovo_evento_strutturato.get("stato"))
    azione_nuova = _testo(nuovo_evento_strutturato.get("azione_cognitiva"))
    eventi_core_nuovi = nuovo_evento_strutturato.get("eventi_core", [])
    if not isinstance(eventi_core_nuovi, list):
        eventi_core_nuovi = []

    rilevanza = _numero(
        nuovo_evento_strutturato.get(
            "rilevanza",
            ipotesi.get("rilevanza", 0.0)
        )
    )
    confidenza = _numero(
        nuovo_evento_strutturato.get(
            "confidenza",
            ipotesi.get("confidenza", 0.0)
        )
    )

    if categoria_ipotesi == categoria_nuova and stato_ipotesi == stato_nuovo:
        tentativi = _tentativi(ipotesi) + 1
        aggiornata["tentativi"] = tentativi
        aggiornata["confermata"] = True
        aggiornata["ultimo_mondo"] = nuovo_mondo
        aggiornata["ultima_categoria"] = categoria_nuova
        aggiornata["ultimo_stato"] = stato_nuovo

        if (
            categoria_nuova == "supporto_informativo"
            and stato_nuovo in ["potenziale", "non_disponibile"]
        ):
            return _esito(
                True,
                "scaduta",
                False,
                "supporto informativo non convertito dopo osservazione mirata",
                None,
                aggiornata
            )

        genera = (
            (rilevanza >= 0.6 or confidenza >= 0.6)
            and _evento_strutturato_puo_generare(nuovo_evento_strutturato)
        )
        motivo = "ipotesi strutturata confermata"
        if genera:
            motivo = "ipotesi strutturata confermata e rilevante"
        elif categoria_nuova in ["", "neutra"] or len(eventi_core_nuovi) == 0:
            motivo = "ipotesi strutturata confermata ma non generativa"

        return _esito(
            True,
            "confermata",
            genera,
            motivo,
            "genera_condizione" if genera else None,
            aggiornata
        )

    if _supporto_informativo_peggiorato_ma_inconclusivo(
        categoria_ipotesi,
        stato_ipotesi,
        categoria_nuova,
        stato_nuovo
    ):
        tentativi = _tentativi(ipotesi) + 1
        aggiornata["tentativi"] = tentativi
        aggiornata["confermata"] = False
        aggiornata["ultimo_mondo"] = nuovo_mondo
        aggiornata["ultima_categoria"] = categoria_nuova
        aggiornata["ultimo_stato"] = stato_nuovo
        aggiornata["osservazione_inconclusiva"] = True

        if tentativi >= 3:
            return _esito(
                True,
                "scaduta",
                False,
                "supporto informativo potenziale non chiarito dopo osservazioni ripetute",
                None,
                aggiornata
            )

        return _esito(
            True,
            "incerta",
            False,
            "osservazione mirata inconclusiva: mantengo ipotesi potenziale",
            None,
            aggiornata
        )

    if categoria_nuova == "ambiguita" or azione_nuova == "osserva_meglio":
        tentativi = _tentativi(ipotesi) + 1
        aggiornata["tentativi"] = tentativi
        aggiornata["confermata"] = False
        aggiornata["ultimo_mondo"] = nuovo_mondo
        aggiornata["ultima_categoria"] = categoria_nuova
        aggiornata["ultimo_stato"] = stato_nuovo

        if tentativi >= 3:
            return _esito(
                True,
                "scaduta",
                False,
                "ipotesi strutturata rimasta incerta troppo a lungo",
                None,
                aggiornata
            )

        return _esito(
            True,
            "incerta",
            False,
            "nuova osservazione ancora ambigua",
            "osserva_meglio",
            aggiornata
        )

    if categoria_ipotesi == categoria_nuova and stato_ipotesi != stato_nuovo:
        aggiornata["confermata"] = False
        aggiornata["ultimo_mondo"] = nuovo_mondo
        aggiornata["ultima_categoria"] = categoria_nuova
        aggiornata["ultimo_stato"] = stato_nuovo

        return _esito(
            True,
            "smentita",
            False,
            "stato incompatibile con ipotesi strutturata",
            None,
            aggiornata
        )

    tentativi = _tentativi(ipotesi) + 1
    aggiornata["tentativi"] = tentativi
    aggiornata["confermata"] = False
    aggiornata["ultimo_mondo"] = nuovo_mondo
    aggiornata["ultima_categoria"] = categoria_nuova
    aggiornata["ultimo_stato"] = stato_nuovo

    if tentativi >= 3:
        return _esito(
            True,
            "scaduta",
            False,
            "ipotesi strutturata scaduta",
            None,
            aggiornata
        )

    return _esito(
        True,
        "incerta",
        False,
        "nuova osservazione non conclusiva",
        "osserva_meglio",
        aggiornata
    )
