# -*- coding: utf-8 -*-
import time
import logging

logger = logging.getLogger(__name__)

COOLDOWN_CONTATTO_FERMO = 8.0
COOLDOWN_URTO_MOVIMENTO = 5.0
COOLDOWN_PERICOLO_CADUTA = 8.0
COOLDOWN_OSTACOLO_CAMMINO = 3.0


def _reset_sicurezza(stato_runtime):
    stato_runtime["attesa_nome"] = False
    stato_runtime["riprendi_dopo_nome"] = False


def _in_cooldown(stato_runtime, chiave, cooldown):
    adesso = time.time()
    ultimo = stato_runtime.get(chiave, 0)
    delta = adesso - ultimo

    if delta < cooldown:
        logger.info(u"[SAFETY] Evento ignorato per cooldown: {} delta={:.1f}s".format(
            chiave,
            delta
        ))
        return True

    stato_runtime[chiave] = adesso
    logger.info(u"[SAFETY] Evento accettato: {}".format(chiave))
    return False


def gestisci_emergenza(mondo, corpo, voce, stato_runtime):
    robot_in_movimento = (
        stato_runtime.get("in_pattugliamento", False) or
        corpo.sta_camminando()
    )

    if u"URTO TATTILE" in mondo or u"URTO LATERALE" in mondo:
        corpo.fermati()
        _reset_sicurezza(stato_runtime)

        if robot_in_movimento:
            if _in_cooldown(
                stato_runtime,
                "ultimo_urto_movimento_tempo",
                COOLDOWN_URTO_MOVIMENTO
            ):
                return True

            corpo.cammina(-0.1, 0.0)
            time.sleep(0.6)

            corpo.gira(0.15)
            time.sleep(0.6)

            corpo.fermati()
            voce.parla(u"Ho sentito un ostacolo, mi sposto.")

        else:
            if _in_cooldown(
                stato_runtime,
                "ultimo_contatto_fermo_tempo",
                COOLDOWN_CONTATTO_FERMO
            ):
                return True

            voce.parla(u"Ho sentito un contatto. Resto fermo.")

        stato_runtime["ultimo_evento_fisico_gestito_tempo"] = time.time()
        return True

    if u"PERICOLO CADUTA" in mondo:
        if _in_cooldown(
            stato_runtime,
            "ultimo_pericolo_caduta_tempo",
            COOLDOWN_PERICOLO_CADUTA
        ):
            return True

        corpo.fermati()
        stato_runtime["in_pattugliamento"] = False
        _reset_sicurezza(stato_runtime)

        corpo.vai_in_posa("Stand")
        voce.parla(u"Mi fermo, rischio di cadere.")

        stato_runtime["ultimo_evento_fisico_gestito_tempo"] = time.time()
        return True

    return False


def gestisci_ostacoli_durante_cammino(mondo, corpo, stato_runtime):
    robot_in_pattugliamento = stato_runtime.get("in_pattugliamento", False)
    robot_sta_camminando = corpo.sta_camminando()

    if not robot_in_pattugliamento and not robot_sta_camminando:
        return False

    if (
        u"Ostacolo frontale molto vicino" in mondo or
        u"Vedo qualcosa vicino" in mondo
    ):
        if _in_cooldown(
            stato_runtime,
            "ultimo_ostacolo_frontale_cammino_tempo",
            COOLDOWN_OSTACOLO_CAMMINO
        ):
            return True

        corpo.fermati()
        time.sleep(0.2)

        corpo.cammina(-0.1, 0.0)
        time.sleep(0.6)

        corpo.gira(0.18)
        time.sleep(0.7)

        corpo.fermati()
        time.sleep(0.2)

        if stato_runtime.get("in_pattugliamento", False):
            corpo.cammina(0.25, 0.0)

        stato_runtime["ultimo_evento_fisico_gestito_tempo"] = time.time()
        return True

    if u"Ostacolo a sinistra" in mondo:
        if _in_cooldown(
            stato_runtime,
            "ultimo_ostacolo_laterale_cammino_tempo",
            COOLDOWN_OSTACOLO_CAMMINO
        ):
            return True

        corpo.imposta_colore_occhi("red")
        corpo.cammina(0.25, -0.12)

        stato_runtime["ultimo_evento_fisico_gestito_tempo"] = time.time()
        return True

    if u"Ostacolo a destra" in mondo:
        if _in_cooldown(
            stato_runtime,
            "ultimo_ostacolo_laterale_cammino_tempo",
            COOLDOWN_OSTACOLO_CAMMINO
        ):
            return True

        corpo.imposta_colore_occhi("red")
        corpo.cammina(0.25, 0.12)

        stato_runtime["ultimo_evento_fisico_gestito_tempo"] = time.time()
        return True

    return False