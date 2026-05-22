# -*- coding: utf-8 -*-
"""
Validatore per condizioni legate a eventi sconosciuti.

Scopo:
- evitare condizioni troppo generiche;
- verificare che una condizione sconosciuta usi l'evento candidato corretto;
- testare offline prima di permettere generazione reale.
"""


def valida_condizione_sconosciuta(nome_evento, codice):
    """
    Ritorna:
    (True, "ok") se la condizione sembra specifica.
    (False, motivo) se e' troppo generica o incoerente.
    """

    if not nome_evento:
        return False, "nome evento assente"

    if not codice:
        return False, "codice assente"

    codice_lower = codice.lower()
    nome_evento = nome_evento.lower()

    parole_evento = [
        p for p in nome_evento.split("_")
        if len(p.strip()) >= 4
    ]

    if len(parole_evento) == 0:
        return False, "evento troppo generico"

    usa_evento_runtime = (
        'eventi.get("{}"'.format(nome_evento) in codice_lower or
        "eventi.get('{}'".format(nome_evento) in codice_lower
    )

    if usa_evento_runtime:
        return True, "ok"

    parole_presenti = [
        parola for parola in parole_evento
        if parola in codice_lower
    ]

    if len(parole_presenti) < len(parole_evento):
        return False, "condizione non copre tutte le parti dell'evento"

    if len(parole_presenti) < 2:
        return False, "condizione troppo generica per evento sconosciuto"

    if "mondo.lower()" not in codice_lower and "testo =" not in codice_lower:
        return False, "condizione testuale senza normalizzazione"

    return True, "ok"


def simula_validazione(nome_evento):
    """
    Crea esempi finti per verificare il validatore.
    Non scrive file, non modifica condizioni.
    """

    codice_buono_runtime = '''
def condizione(mondo, stato_runtime):
    eventi = stato_runtime.get("eventi", {})
    return eventi.get("''' + nome_evento + '''", False)
'''

    codice_buono_testo = '''
def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return "''' + '" in testo and "'.join(nome_evento.split("_")) + '''" in testo
'''

    prima_parola = nome_evento.split("_")[0]

    codice_troppo_generico = '''
def condizione(mondo, stato_runtime):
    testo = mondo.lower()
    return "''' + prima_parola + '''" in testo
'''

    return {
        "runtime": valida_condizione_sconosciuta(nome_evento, codice_buono_runtime),
        "testo_specifico": valida_condizione_sconosciuta(nome_evento, codice_buono_testo),
        "troppo_generico": valida_condizione_sconosciuta(nome_evento, codice_troppo_generico)
    }