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

        genera = rilevanza >= 0.6 or confidenza >= 0.6
        motivo = "ipotesi strutturata confermata"
        if genera:
            motivo = "ipotesi strutturata confermata e rilevante"

        return _esito(
            True,
            "confermata",
            genera,
            motivo,
            "genera_condizione" if genera else None,
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
