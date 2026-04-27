# -*- coding: utf-8 -*-
from naoqi import ALProxy
import json
import os

class NaoSystem:
    def __init__(self, ip, port=9559):
        # Proxy di gestione sistema
        self.system = ALProxy("ALSystem", ip, port)
        self.conn_manager = ALProxy("ALConnectionManager", ip, port)
        self.life = ALProxy("ALAutonomousLife", ip, port)
        self.battery = ALProxy("ALBattery", ip, port)
        self.percorso_memoria = "memoria.json"

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
        """Restituisce la percentuale e avvisa se è bassa"""
        carica = self.battery.getBatteryCharge()
        if carica < 15:
            return "ATTENZIONE: Batteria critica ({}%)!".format(carica)
        return "Batteria: {}%".format(carica)

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