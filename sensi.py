# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time

class NaoSenses:
    def __init__(self, ip, port=9559):
        self.memory = ALProxy("ALMemory", ip, port)
        self.ultimo_timestamp_audio = 0
        self.contatore_battiti = 0
        self.ultimo_battito_rilevato = 0
        self.finestra_ascolto = 1.5 # Tempo per finire di contare i battiti
        try:
            self.sonar = ALProxy("ALSonar", ip, port)
            self.sonar.subscribe("SensiAnima")
        except: pass

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

        # 2. GESTIONE BATTITI (Suoni 1-2-3)
        dati_audio = self.memory.getData("SoundDetected")
        if dati_audio and len(dati_audio) > 0:
            # Calcoliamo il timestamp del suono
            timestamp_audio = dati_audio[0][0] + dati_audio[0][1] * 1e-6
            if timestamp_audio > self.ultimo_timestamp_audio:
                self.ultimo_timestamp_audio = timestamp_audio
                self.contatore_battiti += 1
                self.ultimo_battito_rilevato = tempo_attuale

        if self.contatore_battiti > 0 and (tempo_attuale - self.ultimo_battito_rilevato > self.finestra_ascolto):
            eventi.append(u"Sento {} battiti di mani.".format(self.contatore_battiti))
            self.contatore_battiti = 0

        # 3. SONAR (Ostacoli)
        dist_l = self.memory.getData("Device/SubDeviceList/US/Left/Sensor/Value")
        dist_r = self.memory.getData("Device/SubDeviceList/US/Right/Sensor/Value")
        if dist_l < 0.6 and dist_r < 0.6: eventi.append(u"Ostacolo frontale molto vicino.")
        elif dist_l < 0.6: eventi.append(u"Ostacolo a sinistra.")
        elif dist_r < 0.6: eventi.append(u"Ostacolo a destra.")

        # 4. TESTA (Carezza)
        if self.memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value") > 0:
            eventi.append(u"Sento una carezza sulla testa.")

        # 5. PARAURTI TATTILI (Foot Bumpers - Anticollisione di emergenza)
        lb_left = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value")
        lb_right = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value")
        rb_left = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value")
        rb_right = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value")

        if lb_left > 0 or lb_right > 0 or rb_left > 0 or rb_right > 0:
            eventi.append(u"URTO TATTILE! Ostacolo invisibile colpito.")

        return u"REPORT: " + u" ".join(eventi)