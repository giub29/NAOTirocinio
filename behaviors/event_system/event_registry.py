# -*- coding: utf-8 -*-
"""
Registro unificato degli eventi osservabili.

Scopo:
- trattare eventi noti e sconosciuti nello stesso modo;
- NON eseguire comportamenti;
- NON sostituire le condizioni autogenerate;
- preparare il flusso uniforme:
  evento -> supervisore -> condizione autogenerata.
"""

EVENTI_BASE_NOTI = {
    "carezza_testa": {
        "origine": "nota",
        "categoria": "sociale",
        "descrizione": "contatto/carezza sulla testa"
    },
    "mano_destra": {
        "origine": "nota",
        "categoria": "sociale",
        "descrizione": "tocco sulla mano destra"
    },
    "mano_sinistra": {
        "origine": "nota",
        "categoria": "sociale",
        "descrizione": "tocco sulla mano sinistra"
    },
    "entrambe_mani": {
        "origine": "nota",
        "categoria": "sociale",
        "descrizione": "tocco su entrambe le mani"
    },
    "volto_riconosciuto": {
        "origine": "nota",
        "categoria": "sociale",
        "descrizione": "persona riconosciuta"
    },
    "volto_ignoto": {
        "origine": "nota",
        "categoria": "sociale",
        "descrizione": "persona non riconosciuta"
    },
    "ostacolo_destra": {
        "origine": "nota",
        "categoria": "spaziale",
        "descrizione": "ostacolo sul lato destro"
    },
    "ostacolo_sinistra": {
        "origine": "nota",
        "categoria": "spaziale",
        "descrizione": "ostacolo sul lato sinistro"
    },
    "ostacolo_frontale": {
        "origine": "nota",
        "categoria": "spaziale",
        "descrizione": "ostacolo frontale"
    },
    "urto_piedi": {
        "origine": "nota",
        "categoria": "safety",
        "descrizione": "urto o contatto ai piedi"
    },
    "pericolo": {
        "origine": "nota",
        "categoria": "safety",
        "descrizione": "situazione di pericolo"
    },
    "rumore_improvviso": {
        "origine": "nota",
        "categoria": "audio",
        "descrizione": "rumore improvviso"
    },
    "rumore_singolo": {
        "origine": "nota",
        "categoria": "audio",
        "descrizione": "rumore singolo o colpo"
    },
    "battiti_mani": {
        "origine": "nota",
        "categoria": "audio",
        "descrizione": "battito o battiti di mani"
    },
    "fermo": {
        "origine": "nota",
        "categoria": "stato_robot",
        "descrizione": "robot fermo"
    },
    "camminando": {
        "origine": "nota",
        "categoria": "stato_robot",
        "descrizione": "robot in movimento"
    }
}


def normalizza_nome_evento(nome_evento):
    nome = (nome_evento or "").strip().lower()
    nome = nome.replace("-", "_").replace(" ", "_")

    while "__" in nome:
        nome = nome.replace("__", "_")

    return nome.strip("_")


def descrivi_evento(nome_evento):
    """
    Restituisce metadati dell'evento.
    Se l'evento non e' nel registro noto, viene trattato come scoperto.
    """

    nome = normalizza_nome_evento(nome_evento)

    if nome in EVENTI_BASE_NOTI:
        dati = dict(EVENTI_BASE_NOTI[nome])
        dati["nome"] = nome
        dati["conosciuto"] = True
        return dati

    return {
        "nome": nome,
        "origine": "scoperta",
        "categoria": "sconosciuta",
        "descrizione": "evento scoperto autonomamente",
        "conosciuto": False
    }


def arricchisci_eventi_registro(eventi):
    """
    Converte:
    {"mano_destra": True, "porta_aperta": True}

    in:
    {
      "mano_destra": {...},
      "porta_aperta": {...}
    }

    Non modifica i valori originali delle condizioni.
    Serve solo come livello descrittivo.
    """

    if not isinstance(eventi, dict):
        return {}

    risultato = {}

    for nome, valore in eventi.items():
        if valore in [False, None, "", [], {}]:
            continue

        nome_norm = normalizza_nome_evento(nome)
        dati = descrivi_evento(nome_norm)
        dati["attivo"] = True
        dati["valore"] = valore
        risultato[nome_norm] = dati

    return risultato