# -*- coding: utf-8 -*-
import re


def limita_numero(valore, minimo, massimo, default=0.0):
    try:
        valore = float(valore)

        if valore < minimo:
            return minimo

        if valore > massimo:
            return massimo

        return valore

    except:
        return default


def valida_decisione(decisione, mondo):
    azioni_valide = []
    azioni = decisione.get("azioni", [])

    ha_schivata = False

    for az in azioni:
        if az.get("tipo", "") in ["cammina", "gira"]:
            ha_schivata = True
            break

    testo_mondo = mondo.lower()

    evento_safety_cammino = (
        "sto camminando" in testo_mondo and
        (
            "ostacolo" in testo_mondo or
            "urto" in testo_mondo or
            "piede sinistro" in testo_mondo or
            "piede destro" in testo_mondo or
            "pericolo" in testo_mondo
        )
    )

    for az in azioni:
        tipo = az.get("tipo", "")

        if tipo == "parla":
            testo = az.get("testo", "")
            if testo:
                azioni_valide.append({"tipo": "parla", "testo": testo})

        elif tipo == "cammina":
            if "SONO FERMO" in mondo and "L'utente dice" not in mondo and "URTO" not in mondo:
                continue

            x = limita_numero(az.get("x", 0.0), -0.2, 0.2, 0.0)
            g = limita_numero(az.get("g", 0.0), -0.2, 0.2, 0.0)

            azioni_valide.append({
                "tipo": "cammina",
                "x": x,
                "g": g
            })

        elif tipo == "gira":
            if "SONO FERMO" in mondo and "L'utente dice" not in mondo and "URTO" not in mondo:
                continue

            v = limita_numero(az.get("v", 0.0), -0.3, 0.3, 0.0)
            azioni_valide.append({"tipo": "gira", "v": v})

        elif tipo == "fermati":
            azioni_valide.append({"tipo": "fermati"})

        elif tipo == "posa":
            nome = az.get("nome", "Stand")
            if nome in ["Stand", "Crouch", "Sit", "SitRelax"]:
                azioni_valide.append({"tipo": "posa", "nome": nome})

        elif tipo == "guarda":
            x = limita_numero(az.get("x", 0.0), -1.0, 1.0, 0.0)
            y = limita_numero(az.get("y", -0.25), -0.5, -0.1, -0.25)

            azioni_valide.append({
                "tipo": "guarda",
                "x": x,
                "y": y
            })

        elif tipo == "occhi":
            colore = az.get("colore", "white")
            if colore in ["white", "red", "green", "blue", "yellow", "purple", "cyan"]:
                azioni_valide.append({"tipo": "occhi", "colore": colore})

        elif tipo == "animazione":
            path = az.get("path", "")
            if path.startswith("animations/"):
                azioni_valide.append({"tipo": "animazione", "path": path})

        elif tipo == "apprendi_volto":
            nome = az.get("nome", "")
            if nome:
                azioni_valide.append({"tipo": "apprendi_volto", "nome": nome})

        elif tipo == "foto":
            camera_id = int(az.get("camera_id", 0))
            file_foto = az.get("file", "foto.jpg")
            if camera_id in [0, 1]:
                azioni_valide.append({
                    "tipo": "foto",
                    "camera_id": camera_id,
                    "file": file_foto
                })

    if evento_safety_cammino:
        ha_fermati = False

        for azione in azioni_valide:
            if azione.get("tipo") == "fermati":
                ha_fermati = True
                break

        if not ha_fermati:
            azioni_valide.insert(0, {"tipo": "fermati"})

    decisione["azioni"] = azioni_valide
    return decisione


def esegui_decisione(decisione, corpo, voce, vista, sistema, stato_runtime, aggiorna_memoria_callback=None):
    if aggiorna_memoria_callback:
        aggiorna_memoria_callback(decisione)

    azioni = decisione.get("azioni", [])

    ha_schivata = False
    for az in azioni:
        tipo = az.get("tipo", "")

        try:
            if tipo == "parla":
                testo = az.get("testo", "")
                voce.parla(testo)

                if "Ciao" in testo:
                    m = re.search(r'Ciao (.*?)!', testo)
                    if m:
                        stato_runtime["volti_salutati"].append(m.group(1))

                if "ignoto" in testo.lower() or "sconosciuto" in testo.lower():
                    stato_runtime["volti_salutati"].append("Sconosciuto")

            elif tipo == "cammina":
                corpo.cammina(az.get("x", 0.0), az.get("g", 0.0))

            elif tipo == "gira":
                corpo.gira(az.get("v", 0.0))

            elif tipo == "fermati":
                corpo.fermati()

                if (
                    not stato_runtime.get("mantieni_pattugliamento", False) and
                    not ha_schivata
                ):
                    stato_runtime["in_pattugliamento"] = False

            elif tipo == "posa":
                corpo.vai_in_posa(az.get("nome", "Stand"))

            elif tipo == "guarda":
                corpo.guarda(az.get("x", 0.0), az.get("y", -0.25))

            elif tipo == "occhi":
                corpo.imposta_colore_occhi(az.get("colore", "white"))

            elif tipo == "animazione":
                corpo.esegui_animazione(az.get("path", ""))

            elif tipo == "apprendi_volto":
                vista.apprendi_volto(az.get("nome", ""))

            elif tipo == "foto":
                corpo.scatta_foto(
                    camera_id=az.get("camera_id", 0),
                    nome_file=az.get("file", "foto.jpg")
                )

        except Exception as e:
            print(u"[ERRORE AZIONE {}]: {}".format(tipo, str(e)))