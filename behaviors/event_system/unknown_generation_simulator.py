# -*- coding: utf-8 -*-

from behaviors.event_system.unknown_condition_validator import valida_condizione_sconosciuta


PAROLE_TROPPO_GENERICHE = [
    "porta",
    "rumore",
    "suono",
    "fischio",
    "oggetto",
    "persona",
    "cosa",
    "evento",
    "movimento",
    "voce"
]


def evento_sufficientemente_specifico(nome_evento):
    nome = (nome_evento or "").strip().lower()

    if not nome:
        return False, "nome evento vuoto"

    if nome in PAROLE_TROPPO_GENERICHE:
        return False, "evento troppo generico"

    parti = [p for p in nome.split("_") if p]

    if len(parti) < 2:
        return False, "evento con meno di due elementi semantici"

    return True, "ok"


def simula_condizione_sconosciuta(nome_evento):
    specifico, motivo_specificita = evento_sufficientemente_specifico(nome_evento)

    codice = '''
def condizione(mondo, stato_runtime):
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("''' + nome_evento + '''", False)
'''

    valido, motivo = valida_condizione_sconosciuta(nome_evento, codice)

    valido_finale = valido and specifico

    if not specifico:
        motivo = motivo_specificita

    return {
        "evento": nome_evento,
        "codice_simulato": codice,
        "valido": valido_finale,
        "motivo": motivo,
        "specifico": specifico,
        "generazione_reale_permessa": valido_finale
    }