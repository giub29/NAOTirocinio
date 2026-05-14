# -*- coding: utf-8 -*-
from naoqi import ALProxy
import json
import os
import time

class NaoSystem:
    def __init__(self, ip, port=9559):
        # Proxy di gestione sistema
        self.system = ALProxy("ALSystem", ip, port)
        self.conn_manager = ALProxy("ALConnectionManager", ip, port)
        self.life = ALProxy("ALAutonomousLife", ip, port)
        self.battery = ALProxy("ALBattery", ip, port)
        self.percorso_memoria = "memoria.json"
        self.memory = ALProxy("ALMemory", ip, port)

    def configura_autonomous_life_da_env(self):
        """
        Attiva AutonomousLife SOLO se richiesto
        tramite variabile ambiente.

        Default:
            non cambia nulla.

        Attivazione:
            NAO_AUTONOMOUS_LIFE=1
        """

        try:
            valore = os.environ.get(
                "NAO_AUTONOMOUS_LIFE",
                ""
            ).strip().lower()

            attivo = valore in (
                "1",
                "true",
                "yes",
                "on",
                "si",
                "sì"
            )

            if not attivo:
                print(
                    "[SYSTEM] AutonomousLife disattivato "
                    "(default sicuro)."
                )
                return False

            stato_corrente = self.life.getState()

            print(
                "[SYSTEM] Stato AutonomousLife corrente: {}".format(
                    stato_corrente
                )
            )

            if stato_corrente != "solitary":

                self.life.setState("solitary")

                print(
                    "[SYSTEM] AutonomousLife impostato "
                    "su solitary."
                )

            else:

                print(
                    "[SYSTEM] AutonomousLife già attivo."
                )

            return True

        except Exception as errore:

            print(
                "[SYSTEM] Errore AutonomousLife: {}".format(
                    errore
                )
            )

            return False
    
    def ottieni_info_sistema(self):
        """Restituisce nome del robot e versione software"""
        nome = self.system.robotName()
        versione = self.system.systemVersion()
        return "Robot: {} | Versione: {}".format(nome, versione)

    def controlla_connessione(self):
        """Verifica se il robot è online e la forza del segnale"""
        stato = self.conn_manager.state()
        return "Stato Rete: " + stato

    def set_vita_autonoma(self, stato):
        """Attiva o disattiva la vita autonoma (solitary o disabled)"""
        nuovo_stato = "solitary" if stato else "disabled"
        self.life.setState(nuovo_stato)

    def controlla_batteria(self):
        """
        Restituisce una frase semantica sulla batteria.
        Deve essere leggibile da soul.py e dal supervisore autonomo.
        """
        try:
            carica = self.battery.getBatteryCharge()
        except Exception:
            return ""

        if carica <= 15:
            return "La mia batteria è critica: {}%.".format(carica)

        if carica <= 25:
            return "La mia batteria è bassa: {}%.".format(carica)

        return "La mia batteria è al {}%.".format(carica)

    def spegni_robot(self):
        """Spegne il robot via software (usare con cautela!)"""
        print("Spegnimento del sistema in corso...")
        self.system.shutdown()

    def leggi_memoria(self):
        """Carica i dati dal file JSON"""
        if not os.path.exists(self.percorso_memoria):
            return {}
        with open(self.percorso_memoria, 'r') as f:
            return json.load(f)

    def salva_ricordo(self, categoria, info):
        """Aggiunge un'informazione alla memoria e salva su file"""
        dati = self.leggi_memoria()

        if categoria == "fatti":
            dati["fatti_importanti"].update(info)
        elif categoria == "ricordi":
            dati["ricordi_recenti"].append(info)
            # Teniamo solo gli ultimi 5 ricordi per non appesantire il prompt
            dati["ricordi_recenti"] = dati["ricordi_recenti"][-5:]

        with open(self.percorso_memoria, 'w') as f:
            json.dump(dati, f, indent=4)
        print(u"--- MEMORIA AGGIORNATA: " + str(info) + " ---")

    # ALMEMORY - COLLEGAMENTO CON CHOREGRAPHE
    def scrivi_memoria_naoqi(self, chiave, valore):
        """
        Scrive un valore nella memoria interna di NAO.
        Questo permette a Choregraphe, soul.py e watchdog
        di comunicare tra loro.
        """
        try:
            self.memory.insertData(chiave, valore)
            return True
        except Exception as errore:
            print("[SYSTEM] Errore scrittura ALMemory: {}".format(errore))
            return False

    def leggi_memoria_naoqi(self, chiave, valore_default=""):
        """
        Legge un valore dalla memoria interna di NAO.
        Se la chiave non esiste restituisce valore_default.
        """
        try:
            return self.memory.getData(chiave)
        except Exception:
            return valore_default

    def heartbeat(self):
        """
        Segnale periodico che dice:
        soul.py è vivo e sta funzionando.

        Il watchdog può leggere questo valore per capire
        se il sistema è bloccato o crashato.
        """
        return self.scrivi_memoria_naoqi(
            "AutonomousSystem/Heartbeat",
            time.time()
        )

    def pubblica_stato_autonomo(self, stato):
        """
        Pubblica lo stato corrente del sistema autonomo.
        Esempi:
        BOOT
        RUNNING
        ERROR
        REPAIRING
        WAITING_EVENT
        """
        return self.scrivi_memoria_naoqi(
            "AutonomousSystem/Status",
            stato
        )

    def pubblica_evento_corrente(self, evento):
        """
        Pubblica l'ultimo evento percepito dal robot.
        Serve per rendere visibile a Choregraphe cosa
        sta rilevando soul.py.
        """
        return self.scrivi_memoria_naoqi(
            "AutonomousSystem/LastEvent",
            evento
        )

    def leggi_comando_choregraphe(self):
        """
        Legge eventuali comandi inviati da Choregraphe.
        """
        return self.leggi_memoria_naoqi(
            "AutonomousSystem/Command",
            ""
        )

    def pulisci_comando_choregraphe(self):
        """
        Cancella il comando dopo averlo eseguito,
        evitando che venga ripetuto all'infinito.
        """
        return self.scrivi_memoria_naoqi(
            "AutonomousSystem/Command",
            ""
        )