# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time


class NaoSenses:
    def __init__(self, ip, port=9559):
        self.memory = ALProxy("ALMemory", ip, port)

        self.ultimo_volto_nome = None
        self.ultimo_volto_tempo = 0
        self.durata_memoria_volto = 8.0

        try:
            self.face_detection = ALProxy("ALFaceDetection", ip, port)
            self.face_detection.subscribe("SensiFaceDetection", 500, 0.0)
            print("--- FACE DETECTION ATTIVA ---")
        except Exception as e:
            print("--- ERRORE FACE DETECTION: {} ---".format(e))

        self.ultimo_timestamp_audio = 0
        self.contatore_battiti = 0
        self.ultimo_battito_rilevato = 0
        self.finestra_ascolto = 1.5
        self.ultimo_urto = 0

        try:
            self.sonar = ALProxy("ALSonar", ip, port)
            self.sonar.subscribe("SensiAnima")
        except:
            pass

    def _leggi_volto(self):
        try:
            dati_volto = self.memory.getData("FaceDetected")
        except:
            dati_volto = None

        if not dati_volto:
            return None

        if not isinstance(dati_volto, list):
            return None

        if len(dati_volto) <= 1:
            return None

        volti = dati_volto[1]

        if not volti or not isinstance(volti, list):
            return None

        nome_riconosciuto = None

        for volto in volti:
            try:
                info_extra = volto[1]

                if len(info_extra) > 2 and info_extra[2]:
                    nome_riconosciuto = info_extra[2]
                    break

            except:
                pass

        if nome_riconosciuto:
            return nome_riconosciuto

        return "Sconosciuto"

    def ottieni_report_semantico(self):
        eventi = []
        tempo_attuale = time.time()

        # 1. RICONOSCIMENTO VOLTI CON MEMORIA TEMPORANEA
        volto_corrente = self._leggi_volto()

        # Se riconosco un nome vero, aggiorno la memoria.
        # Se vedo solo "Sconosciuto", non cancello subito l'ultimo volto noto.
        if volto_corrente and volto_corrente != "Sconosciuto":
            self.ultimo_volto_nome = volto_corrente
            self.ultimo_volto_tempo = tempo_attuale

        volto_noto_recente = (
            self.ultimo_volto_nome and
            tempo_attuale - self.ultimo_volto_tempo <= self.durata_memoria_volto
        )

        if volto_noto_recente:
            eventi.append(u"Riconosco {}.".format(self.ultimo_volto_nome))
        elif volto_corrente == "Sconosciuto":
            eventi.append(u"Vedo un volto ignoto.")

        # 2. GESTIONE BATTITI
        try:
            dati_audio = self.memory.getData("SoundDetected")
        except:
            dati_audio = None

        if dati_audio and len(dati_audio) > 0:
            timestamp_audio = dati_audio[0][0] + dati_audio[0][1] * 1e-6
            if timestamp_audio > self.ultimo_timestamp_audio:
                self.ultimo_timestamp_audio = timestamp_audio
                self.contatore_battiti += 1
                self.ultimo_battito_rilevato = tempo_attuale

        if self.contatore_battiti > 0 and (tempo_attuale - self.ultimo_battito_rilevato > self.finestra_ascolto):
            eventi.append(u"Sento {} battiti di mani.".format(self.contatore_battiti))
            self.contatore_battiti = 0

        # 3. SONAR
        try:
            dist_l = self.memory.getData("Device/SubDeviceList/US/Left/Sensor/Value")
            dist_r = self.memory.getData("Device/SubDeviceList/US/Right/Sensor/Value")

            if dist_l < 0.65 and dist_r < 0.65:
                eventi.append(u"Ostacolo frontale molto vicino.")
            elif dist_l < 0.70:
                eventi.append(u"Ostacolo a sinistra.")
            elif dist_r < 0.70:
                eventi.append(u"Ostacolo a destra.")
        except:
            pass

        # 4. TESTA E MANI
        try:
            head_front = self.memory.getData("Device/SubDeviceList/Head/Touch/Front/Sensor/Value")
            head_middle = self.memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value")
            head_rear = self.memory.getData("Device/SubDeviceList/Head/Touch/Rear/Sensor/Value")

            if head_front > 0 or head_middle > 0 or head_rear > 0:
                eventi.append(u"Sento una carezza sulla testa.")

            mano_sx_back = self.memory.getData("Device/SubDeviceList/LHand/Touch/Back/Sensor/Value")
            mano_sx_left = self.memory.getData("Device/SubDeviceList/LHand/Touch/Left/Sensor/Value")
            mano_sx_right = self.memory.getData("Device/SubDeviceList/LHand/Touch/Right/Sensor/Value")

            mano_dx_back = self.memory.getData("Device/SubDeviceList/RHand/Touch/Back/Sensor/Value")
            mano_dx_left = self.memory.getData("Device/SubDeviceList/RHand/Touch/Left/Sensor/Value")
            mano_dx_right = self.memory.getData("Device/SubDeviceList/RHand/Touch/Right/Sensor/Value")

            mano_sx_toccata = mano_sx_back > 0 or mano_sx_left > 0 or mano_sx_right > 0
            mano_dx_toccata = mano_dx_back > 0 or mano_dx_left > 0 or mano_dx_right > 0

            if mano_sx_toccata and mano_dx_toccata:
                eventi.append(u"Sento un tocco su entrambe le mani.")
            elif mano_sx_toccata:
                eventi.append(u"Sento un tocco sulla mano sinistra.")
            elif mano_dx_toccata:
                eventi.append(u"Sento un tocco sulla mano destra.")

        except:
            pass

        # 5. PARAURTI TATTILI / BUMPER PIEDI
        try:
            lb_left = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value")
            lb_right = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value")
            rb_left = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value")
            rb_right = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value")

            piede_sx_toccato = lb_left > 0 or lb_right > 0
            piede_dx_toccato = rb_left > 0 or rb_right > 0

            if piede_sx_toccato or piede_dx_toccato:
                if tempo_attuale - self.ultimo_urto > 2:
                    if piede_sx_toccato and piede_dx_toccato:
                        eventi.append(u"URTO TATTILE! Ostacolo frontale ai piedi.")
                    elif piede_sx_toccato:
                        eventi.append(u"URTO TATTILE! Ostacolo a sinistra. Piede sinistro premuto.")
                    elif piede_dx_toccato:
                        eventi.append(u"URTO TATTILE! Ostacolo a destra. Piede destro premuto.")

                    self.ultimo_urto = tempo_attuale

        except Exception as e:
            print("[DEBUG BUMPER ERROR] {}".format(e))

        # 6. PERICOLO CADUTA
        try:
            peso_sx = self.memory.getData("Device/SubDeviceList/LFoot/FSR/TotalWeight/Sensor/Value")
            peso_dx = self.memory.getData("Device/SubDeviceList/RFoot/FSR/TotalWeight/Sensor/Value")
            peso_totale = peso_sx + peso_dx

            if peso_totale < 0.8:
                if tempo_attuale - self.ultimo_urto > 4:
                    eventi.append(u"PERICOLO CADUTA! Pavimento mancante o sollevamento.")
                    self.ultimo_urto = tempo_attuale
        except:
            pass

        # 7. BATTERIA
        try:
            carica = self.memory.getData("Device/SubDeviceList/Battery/Charge/Sensor/Value") * 100
            eventi.append(u"La mia batteria è al {}%.".format(int(carica)))
        except:
            pass

        return u"REPORT: " + u" ".join(eventi)