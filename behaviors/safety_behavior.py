# -*- coding: utf-8 -*-
import time


def gestisci_emergenza(mondo, corpo, voce, stato_runtime):
    if u"URTO TATTILE" in mondo or u"URTO LATERALE" in mondo:
        corpo.fermati()

        stato_runtime["in_pattugliamento"] = False
        stato_runtime["attesa_nome"] = False
        stato_runtime["riprendi_dopo_nome"] = False

        corpo.cammina(-0.1, 0.0)
        time.sleep(0.8)

        corpo.gira(0.15)
        time.sleep(0.8)

        corpo.fermati()
        voce.parla(u"Ho sentito un ostacolo, mi sposto.")

        return True

    if u"PERICOLO CADUTA" in mondo:
        corpo.fermati()

        stato_runtime["in_pattugliamento"] = False
        stato_runtime["attesa_nome"] = False
        stato_runtime["riprendi_dopo_nome"] = False

        corpo.vai_in_posa("Stand")
        voce.parla(u"Mi fermo, rischio di cadere.")

        return True

    return False


def gestisci_ostacoli_durante_cammino(mondo, corpo, stato_runtime):
    if not corpo.sta_camminando() and not stato_runtime["in_pattugliamento"]:
        return False

    if u"Ostacolo frontale molto vicino" in mondo:
        corpo.cammina(-0.1, 0.0)
        time.sleep(0.6)

        corpo.gira(0.15)
        time.sleep(0.6)

        corpo.fermati()
        time.sleep(0.2)

        corpo.cammina(0.3, 0.0)
        return True

    elif u"Ostacolo a sinistra" in mondo:
        corpo.cammina(0.3, -0.08)
        return True

    elif u"Ostacolo a destra" in mondo:
        corpo.cammina(0.3, 0.08)
        return True

    return False