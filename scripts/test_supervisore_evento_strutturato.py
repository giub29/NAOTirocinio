# -*- coding: utf-8 -*-

from behaviors.condition_generator import (
    estrai_eventi,
    costruisci_evento_strutturato
)

from behaviors.autonomy_supervisor import costruisci_firma_situazione


casi = [
    u"REPORT: Ostacolo a destra. STO CAMMINANDO.",
    u"REPORT: Ostacolo frontale. STO CAMMINANDO.",
    u"REPORT: Sento una carezza sulla testa. SONO FERMO.",
    u"REPORT: SONO FERMO."
]


if __name__ == "__main__":
    for mondo in casi:
        stato_runtime = {}

        stato_runtime["eventi"] = estrai_eventi(mondo, stato_runtime)
        stato_runtime["evento_strutturato"] = costruisci_evento_strutturato(
            mondo,
            stato_runtime
        )

        firma = costruisci_firma_situazione(mondo, stato_runtime)

        print("\nMONDO:")
        print(mondo.encode("utf-8"))

        print("EVENTO STRUTTURATO:", firma.get("evento_strutturato"))
        print("EVENTI MULTIPLI:", firma.get("eventi_multipli"))
        print("HA NOVITA RUNTIME:", firma.get("ha_novita_runtime"))
        print("BANALE:", firma.get("banale"))