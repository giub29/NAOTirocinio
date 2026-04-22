# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time


class NaoSenses:
    def __init__(self, ip, port=9559):
        self.memory = ALProxy("ALMemory", ip, port)
        self.ultimo_timestamp_audio = 0
        self.contatore_battiti = 0
        self.ultimo_battito_rilevato = 0
        self.finestra_ascolto = 1.5  # Tempo per finire di contare i battiti
        self.ultimo_urto = 0

        try:
            self.sonar = ALProxy("ALSonar", ip, port)
            self.sonar.subscribe("SensiAnima")
        except:
            pass

    def ottieni_report_semantico(self):
        eventi = []
        tempo_attuale = time.time()

        # 1. RICONOSCIMENTO VOLTI
        dati_volto = self.memory.getData("FaceDetected")
        nome_riconosciuto = "Sconosciuto"
        if dati_volto and len(dati_volto) > 1:
            for volto in dati_volto[1]:
                if len(volto) > 1 and len(volto[1]) >= 2:
                    if volto[1][2] != "": nome_riconosciuto = volto[1][2]
            if nome_riconosciuto != "Sconosciuto":
                eventi.append(u"Riconosco {}.".format(nome_riconosciuto))
            else:
                eventi.append(u"Vedo un volto ignoto.")

        # 2. GESTIONE BATTITI
        dati_audio = self.memory.getData("SoundDetected")
        if dati_audio and len(dati_audio) > 0:
            timestamp_audio = dati_audio[0][0] + dati_audio[0][1] * 1e-6
            if timestamp_audio > self.ultimo_timestamp_audio:
                self.ultimo_timestamp_audio = timestamp_audio
                self.contatore_battiti += 1
                self.ultimo_battito_rilevato = tempo_attuale

        if self.contatore_battiti > 0 and (tempo_attuale - self.ultimo_battito_rilevato > self.finestra_ascolto):
            eventi.append(u"Sento {} battiti di mani.".format(self.contatore_battiti))
            self.contatore_battiti = 0

        # 3. SONAR (Bolla di sicurezza allargata a 0.70m per anticipare gli incastri laterali)
        dist_l = self.memory.getData("Device/SubDeviceList/US/Left/Sensor/Value")
        dist_r = self.memory.getData("Device/SubDeviceList/US/Right/Sensor/Value")
        if dist_l < 0.65 and dist_r < 0.65:
            eventi.append(u"Ostacolo frontale molto vicino.")
        elif dist_l < 0.70:
            eventi.append(u"Ostacolo a sinistra.")
        elif dist_r < 0.70:
            eventi.append(u"Ostacolo a destra.")

        # 4. TESTA E BRACCIA LATERALI
        if self.memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value") > 0:
            eventi.append(u"Sento una carezza sulla testa.")

        mano_sx = self.memory.getData("Device/SubDeviceList/LHand/Touch/Back/Sensor/Value")
        mano_dx = self.memory.getData("Device/SubDeviceList/RHand/Touch/Back/Sensor/Value")
        if mano_sx > 0 or mano_dx > 0:
            if tempo_attuale - self.ultimo_urto > 5:
                lato = "sinistra" if mano_sx > 0 else "destra"
                eventi.append(u"URTO LATERALE a {}! Braccio bloccato.".format(lato))
                self.ultimo_urto = tempo_attuale

        # 5. PARAURTI TATTILI
        lb_left = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value")
        lb_right = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value")
        rb_left = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value")
        rb_right = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value")

        if lb_left > 0 or lb_right > 0 or rb_left > 0 or rb_right > 0:
            if tempo_attuale - self.ultimo_urto > 5:
                eventi.append(u"URTO TATTILE! Ostacolo ai piedi.")
                self.ultimo_urto = tempo_attuale

        # 6. PERICOLO CADUTA
        peso_sx = self.memory.getData("Device/SubDeviceList/LFoot/FSR/TotalWeight/Sensor/Value")
        peso_dx = self.memory.getData("Device/SubDeviceList/RFoot/FSR/TotalWeight/Sensor/Value")
        peso_totale = peso_sx + peso_dx

        if peso_totale < 0.4:
            if tempo_attuale - self.ultimo_urto > 4:
                eventi.append(u"PERICOLO CADUTA! Pavimento mancante o sollevamento.")
                self.ultimo_urto = tempo_attuale

        # 7. MONITORAGGIO BATTERIA
        carica = self.memory.getData("Device/SubDeviceList/Battery/Charge/Sensor/Value") * 100
        eventi.append(u"La mia batteria è al {}%.".format(int(carica)))

        return u"REPORT: " + u" ".join(eventi)