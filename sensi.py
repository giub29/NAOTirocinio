# -*- coding: utf-8 -*-
from naoqi import ALProxy
import time
import threading

try:
    unicode
except NameError:
    unicode = str


TESTI_VISIVI_NON_UTILI = [
    "NESSUN_TESTO_VISIBILE",
    "TESTO_NON_LEGGIBILE",
    "CODICE_NON_LEGGIBILE",
    "",
    None
]


def _testo_lower(valore):
    try:
        if isinstance(valore, unicode):
            return valore.lower()
        return unicode(valore or "").lower()
    except:
        return u""


def _contiene(testo, parole):
    for parola in parole:
        if parola in testo:
            return True
    return False


def descrivi_percezione_visiva(descrizione, testo_visivo=None):
    """
    Arricchisce la descrizione visiva con una frase sensoriale utile.

    Non decide cosa fare e non genera condizioni: produce solo un report piu'
    semanticamente leggibile per la pipeline cognitiva.
    """
    descrizione = descrizione or u""
    testo_visivo = testo_visivo or u""

    testo_descrizione = _testo_lower(descrizione)
    testo_ocr = _testo_lower(testo_visivo).strip()

    testo_leggibile = (
        testo_visivo not in TESTI_VISIVI_NON_UTILI
        and testo_ocr not in [
            "nessun_testo_visibile",
            "testo_non_leggibile",
            "codice_non_leggibile"
        ]
    )

    segnala_testo_non_letto = testo_ocr in [
        "testo_non_leggibile",
        "codice_non_leggibile"
    ]

    indicatori_testo = [
        "testo", "scritta", "scritte", "etichetta", "etichette",
        "parole", "lettere", "codice", "istruzioni", "avviso",
        "messaggio", "segni", "scritte non leggibili",
        "dettagli visivi marcati", "superfici"
    ]
    supporti_contenitore = [
        "contenitore", "scatola", "barattolo", "flacone",
        "bottiglia", "pacco", "confezione", "cassetta"
    ]
    supporti_schermo = [
        "monitor", "schermo", "display", "computer", "terminale"
    ]
    supporti_documento = [
        "foglio", "documento", "cartello", "lavagna", "quaderno",
        "libro", "pagina"
    ]

    vede_supporto_testuale = (
        _contiene(testo_descrizione, indicatori_testo)
        or _contiene(testo_descrizione, supporti_contenitore)
        or _contiene(testo_descrizione, supporti_schermo)
        or _contiene(testo_descrizione, supporti_documento)
    )

    if not testo_leggibile and not (
        segnala_testo_non_letto and vede_supporto_testuale
    ):
        return descrizione

    if _contiene(testo_descrizione, supporti_contenitore):
        oggetto = u"un contenitore"
    elif _contiene(testo_descrizione, supporti_schermo):
        oggetto = u"uno schermo o monitor"
    elif _contiene(testo_descrizione, supporti_documento):
        oggetto = u"un supporto scritto"
    elif _contiene(testo_descrizione, [
        "segni", "scritte non leggibili",
        "dettagli visivi marcati", "superfici"
    ]):
        oggetto = u"un possibile supporto visivo"
    else:
        oggetto = u"un elemento"

    frase = (
        u" Vedo {} con possibili segni o scritte non leggibili. "
        u"Potrebbe contenere informazioni operative."
    ).format(oggetto)

    if frase.strip() not in descrizione:
        descrizione += frase

    if testo_leggibile and u"TESTO_VISIBILE:" not in descrizione:
        descrizione += u" TESTO_VISIBILE: {}".format(testo_visivo)

    return descrizione


class NaoSenses:
    def __init__(self, ip, port=9559):
        self.memory = ALProxy("ALMemory", ip, port)

        # Metti True solo per debug. Se lasci True stampa molto.
        self.debug_sensori = False

        # Memoria breve eventi: serve per avere piu' eventi nello stesso REPORT
        self.eventi_recenti = {}
        self.eventi_strutturati = {}
        self.lock_eventi = threading.RLock()
        self.durata_eventi_recenti = 1.2

        self.ultimo_volto_nome = None
        self.ultimo_volto_tempo = 0
        self.durata_memoria_volto = 4.0

        try:
            self.face_detection = ALProxy("ALFaceDetection", ip, port)
            self.face_detection.subscribe("SensiFaceDetection", 500, 0.0)
            print("--- FACE DETECTION ATTIVA ---")
        except Exception as e:
            print("--- ERRORE FACE DETECTION: {} ---".format(e))

        self.ultimo_timestamp_audio = 0
        self.ultimo_evento_audio_tempo = 0
        self.cooldown_audio = 15.0
        self.contatore_battiti = 0
        self.ultimo_battito_rilevato = 0
        self.finestra_ascolto = 1.5
        self.ultimo_urto = 0
        self.ultimo_evento = {}

        # AUDIO / RUMORI
        try:
            self.sound_detection = ALProxy("ALSoundDetection", ip, port)

            # Sensibilità prudente: non troppo bassa per evitare rumore continuo
            self.sound_detection.setParameter("Sensitivity", 0.55)

            self.sound_detection.subscribe("SensiSound")

            print("--- SOUND DETECTION ATTIVA ---")

        except Exception as e:
            print("--- ERRORE SOUND DETECTION: {} ---".format(e))

        try:
            self.sonar = ALProxy("ALSonar", ip, port)
            self.sonar.subscribe("SensiAnima")
        except:
            pass

        # Thread continuo per non perdere tocchi brevi mentre NAO parla o chiama LLM
        self._stop_monitor_tocco = False
        self.thread_tocco = threading.Thread(target=self._monitor_tocchi)
        self.thread_tocco.daemon = True
        self.thread_tocco.start()
        
    def _safe_print(self, testo):
        try:
            if isinstance(testo, unicode):
                print(testo.encode("utf-8"))
            else:
                print(testo)
        except:
            pass

    def _ricorda_evento(self, chiave, testo):
        """
        Salva un evento reale per pochi secondi.
        Non salva mai eventi gia' marcati come recenti.
        """
        if not testo:
            return

        testo = testo.strip()

        # Evita duplicazioni tipo "Evento recente: Evento recente:"
        while testo.lower().startswith("evento recente:"):
            testo = testo.split(":", 1)[1].strip()

        # Non memorizzare marker generici
        if testo == u"INTERAZIONE_UTENTE." or testo == u"INTERAZIONE_UTENTE":
            return

        tempo = time.time()

        self.eventi_recenti[chiave] = {
            "testo": testo,
            "tempo": tempo
        }

        # Evento strutturato per supervisore autonomo
        self.eventi_strutturati[chiave] = {
            "attivo": True,
            "tempo": tempo
        }
        
    def _eventi_recenti_validi(self):
        tempo_attuale = time.time()
        eventi = []
        chiavi_da_eliminare = []

        try:
            with self.lock_eventi:
                for chiave, dati in self.eventi_recenti.items():
                    try:
                        if tempo_attuale - dati["tempo"] <= self.durata_eventi_recenti:

                            # per eventi umani/tattili verifica che siano ancora vivi
                            if chiave in [
                                "mano_destra",
                                "mano_sinistra",
                                "carezza_testa",
                                "entrambe_mani",
                                "rumore_improvviso",
                                "rumore_singolo",
                                "battiti_mani"
                            ]:
                                if self.evento_recente(chiave):
                                    eventi.append(dati["testo"])
                            else:
                                eventi.append(dati["testo"])
                        else:
                            chiavi_da_eliminare.append(chiave)
                    except:
                        chiavi_da_eliminare.append(chiave)

                for chiave in chiavi_da_eliminare:
                    try:
                        del self.eventi_recenti[chiave]
                    except:
                        pass
        except:
            pass

        return eventi
    
    def evento_recente(self, nome_evento, finestra=3.0):
        """
        Ritorna True solo se l'evento è recente.
        Evita che vecchi tocchi/rumori restino attivi per sempre.
        """
        ultimo = self.ultimo_evento.get(nome_evento, 0)

        if not ultimo:
            return False

        return (time.time() - ultimo) <= finestra

    def ottieni_eventi_strutturati(self):
        """
        Restituisce SOLO eventi realmente attivi ora.
        Gli eventi tattili/audio non devono restare appiccicati.
        """
        eventi = {}

        try:
            # Eventi che devono vivere solo pochi secondi
            eventi_temporanei = [
                "mano_destra",
                "mano_sinistra",
                "carezza_testa",
                "entrambe_mani",
                "rumore_improvviso",
                "rumore_singolo",
                "battiti_mani",
                "piede_sinistro",
                "piede_destro",
                "urto_piedi"
            ]

            # Verifica diretta da timestamp
            for nome in eventi_temporanei:
                eventi[nome] = self.evento_recente(nome)

            # Eventi ambientali (sonar, volti, ecc.)
            tempo_attuale = time.time()

            with self.lock_eventi:
                for chiave, dati in self.eventi_recenti.items():

                    # già gestiti sopra
                    if chiave in eventi_temporanei:
                        continue

                    try:
                        if (
                            tempo_attuale - dati["tempo"]
                            <= self.durata_eventi_recenti
                        ):
                            eventi[chiave] = True
                    except:
                        pass

        except:
            pass

        return eventi

    def _monitor_tocchi(self):
        """
        Legge testa, mani e piedi in modo continuo.
        Triggera solo sul FRONTE DI SALITA (sensore passa da inattivo ad attivo).
        Serve per non perdere tocchi brevi e non ripetere lo stesso evento
        mentre il dito resta appoggiato.
        """
        cooldown = 2.5

        # Stato precedente di ogni sensore (per rilevare fronte di salita)
        era_attivo = {
            "carezza_testa": False,
            "mano_sinistra": False,
            "mano_destra": False,
            "entrambe_mani": False,
            "urto_piedi": False,
            "piede_sinistro": False,
            "piede_destro": False,
        }

        while not self._stop_monitor_tocco:
            tempo_attuale = time.time()

            # TESTA
            try:
                head_front  = self.memory.getData("Device/SubDeviceList/Head/Touch/Front/Sensor/Value")
                head_middle = self.memory.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value")
                head_rear   = self.memory.getData("Device/SubDeviceList/Head/Touch/Rear/Sensor/Value")

                testa_toccata = head_front > 0.2 or head_middle > 0.2 or head_rear > 0.2

                # Fronte di salita: era False, ora è True
                if testa_toccata and not era_attivo["carezza_testa"]:
                    if tempo_attuale - self.ultimo_evento.get("carezza_testa", 0) > cooldown:
                        evento = u"Sento una carezza sulla testa."
                        self._ricorda_evento("carezza_testa", evento)
                        self.ultimo_evento["carezza_testa"] = tempo_attuale
                        self._safe_print(u"[TOCCO] " + evento)

                era_attivo["carezza_testa"] = testa_toccata

            except Exception as e:
                print("[DEBUG MONITOR TESTA ERROR] {}".format(e))

            # MANI
            try:
                mano_sx_back  = self.memory.getData("Device/SubDeviceList/LHand/Touch/Back/Sensor/Value")
                mano_sx_left  = self.memory.getData("Device/SubDeviceList/LHand/Touch/Left/Sensor/Value")
                mano_sx_right = self.memory.getData("Device/SubDeviceList/LHand/Touch/Right/Sensor/Value")

                mano_dx_back  = self.memory.getData("Device/SubDeviceList/RHand/Touch/Back/Sensor/Value")
                mano_dx_left  = self.memory.getData("Device/SubDeviceList/RHand/Touch/Left/Sensor/Value")
                mano_dx_right = self.memory.getData("Device/SubDeviceList/RHand/Touch/Right/Sensor/Value")

                # Filtro anti-falso positivo:
                # soglia piu' alta della precedente 0.2, perche' i sensori capacitivi
                # delle mani possono oscillare anche senza contatto reale.
                soglia_mano = 0.55

                # Sul NAO reale funziona stabilmente solo il sensore Back delle mani.
                # I sensori Left/Right restano spesso a 0.0, quindi non posso richiedere 2 zone attive.

                mano_sx_toccata = (
                    mano_sx_back is not None and
                    mano_sx_back > soglia_mano
                )

                mano_dx_toccata = (
                    mano_dx_back is not None and
                    mano_dx_back > soglia_mano
                )

                if mano_sx_toccata and mano_dx_toccata:
                    if not era_attivo["entrambe_mani"]:
                        if tempo_attuale - self.ultimo_evento.get("entrambe_mani", 0) > cooldown:
                            evento = u"Sento un tocco su entrambe le mani."
                            self._ricorda_evento("entrambe_mani", evento)
                            self.ultimo_evento["entrambe_mani"] = tempo_attuale
                            self._safe_print(u"[TOCCO] " + evento)

                    era_attivo["entrambe_mani"] = True
                    era_attivo["mano_sinistra"] = True
                    era_attivo["mano_destra"] = True

                else:
                    era_attivo["entrambe_mani"] = False

                    if mano_sx_toccata and not era_attivo["mano_sinistra"]:
                        if tempo_attuale - self.ultimo_evento.get("mano_sinistra", 0) > cooldown:
                            evento = u"Sento un tocco sulla mano sinistra."
                            self._ricorda_evento("mano_sinistra", evento)
                            self.ultimo_evento["mano_sinistra"] = tempo_attuale
                            self._safe_print(u"[TOCCO] " + evento)

                    era_attivo["mano_sinistra"] = mano_sx_toccata

                    if mano_dx_toccata and not era_attivo["mano_destra"]:
                        if tempo_attuale - self.ultimo_evento.get("mano_destra", 0) > cooldown:
                            evento = u"Sento un tocco sulla mano destra."
                            self._ricorda_evento("mano_destra", evento)
                            self.ultimo_evento["mano_destra"] = tempo_attuale
                            self._safe_print(u"[TOCCO] " + evento)

                    era_attivo["mano_destra"] = mano_dx_toccata

            except Exception as e:
                print("[DEBUG MONITOR MANI ERROR] {}".format(e))

            # PIEDI / BUMPER
            try:
                lb_left  = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value")
                lb_right = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value")
                rb_left  = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value")
                rb_right = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value")

                piede_sx_toccato = lb_left > 0.2 or lb_right > 0.2
                piede_dx_toccato = rb_left > 0.2 or rb_right > 0.2

                if piede_sx_toccato and piede_dx_toccato:
                    if not era_attivo["urto_piedi"]:
                        if tempo_attuale - self.ultimo_evento.get("urto_piedi", 0) > cooldown:
                            evento = u"URTO TATTILE! Ostacolo frontale ai piedi."
                            self._ricorda_evento("urto_piedi", evento)
                            self.ultimo_evento["urto_piedi"] = tempo_attuale
                            self._safe_print(u"[TOCCO] " + evento)
                    era_attivo["urto_piedi"]     = True
                    era_attivo["piede_sinistro"] = True
                    era_attivo["piede_destro"]   = True

                else:
                    era_attivo["urto_piedi"] = False

                    if piede_sx_toccato and not era_attivo["piede_sinistro"]:
                        if tempo_attuale - self.ultimo_evento.get("piede_sinistro", 0) > cooldown:
                            evento = u"URTO TATTILE! Ostacolo a sinistra. Piede sinistro premuto."
                            self._ricorda_evento("piede_sinistro", evento)
                            self.ultimo_evento["piede_sinistro"] = tempo_attuale
                            self._safe_print(u"[TOCCO] " + evento)
                    era_attivo["piede_sinistro"] = piede_sx_toccato

                    if piede_dx_toccato and not era_attivo["piede_destro"]:
                        if tempo_attuale - self.ultimo_evento.get("piede_destro", 0) > cooldown:
                            evento = u"URTO TATTILE! Ostacolo a destra. Piede destro premuto."
                            self._ricorda_evento("piede_destro", evento)
                            self.ultimo_evento["piede_destro"] = tempo_attuale
                            self._safe_print(u"[TOCCO] " + evento)
                    era_attivo["piede_destro"] = piede_dx_toccato

            except Exception as e:
                print("[DEBUG MONITOR PIEDI ERROR] {}".format(e))

            time.sleep(0.05)

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

        if volto_corrente and volto_corrente != "Sconosciuto":
            self.ultimo_volto_nome = volto_corrente
            self.ultimo_volto_tempo = tempo_attuale

        volto_noto_recente = (
            self.ultimo_volto_nome and
            tempo_attuale - self.ultimo_volto_tempo <= self.durata_memoria_volto
        )

        if volto_noto_recente:
            evento = u"Riconosco {}.".format(self.ultimo_volto_nome)
            eventi.append(evento)
            self._ricorda_evento("volto_riconosciuto", evento)

        elif volto_corrente == "Sconosciuto":
            evento = u"Vedo un volto ignoto."
            eventi.append(evento)
            self._ricorda_evento("volto_ignoto", evento)

        # 2. GESTIONE SUONI / BATTITI
        try:
            dati_audio = self.memory.getData("SoundDetected")
        except:
            dati_audio = None

        if dati_audio and len(dati_audio) > 0:
            if self.debug_sensori:
                print("[DEBUG AUDIO] {}".format(dati_audio))
            timestamp_audio = dati_audio[0][0] + dati_audio[0][1] * 1e-6

            if timestamp_audio > self.ultimo_timestamp_audio:

                # Cooldown anti-rumore: evita spam continuo
                if (
                    tempo_attuale - self.ultimo_evento_audio_tempo
                    >= self.cooldown_audio
                ):

                    self.ultimo_evento_audio_tempo = tempo_attuale

                    self.ultimo_timestamp_audio = timestamp_audio
                    self.contatore_battiti += 1
                    self.ultimo_battito_rilevato = tempo_attuale

                    # Se c'e' stato un tocco umano recente,
                    # ignoro il rumore per evitare falsi positivi
                    touch_recenti = [
                        "mano_destra",
                        "mano_sinistra",
                        "entrambe_mani",
                        "carezza_testa"
                    ]

                    ignora_audio = False

                    for ev in touch_recenti:
                        ultimo = self.ultimo_evento.get(ev, 0)

                        if tempo_attuale - ultimo < 3.0:
                            ignora_audio = True
                            break

                    if ignora_audio:
                        pass
                    else:
                        evento = u"Sento un rumore improvviso vicino a me."
                        eventi.append(evento)
                        self._ricorda_evento("rumore_improvviso", evento)

        if self.contatore_battiti > 0 and (tempo_attuale - self.ultimo_battito_rilevato > self.finestra_ascolto):
            if self.contatore_battiti == 1:
                evento = u"Sento un colpo o un rumore singolo."
                self._ricorda_evento("rumore_singolo", evento)
            else:
                evento = u"Sento {} battiti o rumori ravvicinati.".format(self.contatore_battiti)
                self._ricorda_evento("battiti_mani", evento)

            eventi.append(evento)
            self.contatore_battiti = 0

        # 3. SONAR
        try:
            dist_l = self.memory.getData("Device/SubDeviceList/US/Left/Sensor/Value")
            dist_r = self.memory.getData("Device/SubDeviceList/US/Right/Sensor/Value")
            #print("[SONAR] L={} R={}".format(dist_l, dist_r))

            if dist_l < 0.35 and dist_r < 0.35:
                evento = u"Ostacolo frontale molto vicino."
                eventi.append(evento)
                self._ricorda_evento("ostacolo_frontale", evento)

            elif dist_l < 0.35:
                evento = u"Ostacolo a sinistra."
                eventi.append(evento)
                self._ricorda_evento("ostacolo_sinistra", evento)

            elif dist_r < 0.35:
                evento = u"Ostacolo a destra."
                eventi.append(evento)
                self._ricorda_evento("ostacolo_destra", evento)

        except:
            pass

        # 4. PERICOLO CADUTA
        try:
            peso_sx = self.memory.getData("Device/SubDeviceList/LFoot/FSR/TotalWeight/Sensor/Value")
            peso_dx = self.memory.getData("Device/SubDeviceList/RFoot/FSR/TotalWeight/Sensor/Value")
            peso_totale = peso_sx + peso_dx

            if peso_totale < 0.8:
                if tempo_attuale - self.ultimo_urto > 4:
                    evento = u"PERICOLO CADUTA! Pavimento mancante o sollevamento."
                    eventi.append(evento)
                    self._ricorda_evento("pericolo_caduta", evento)
                    self.ultimo_urto = tempo_attuale

        except:
            pass

        # 5. BATTERIA
        try:
            carica = self.memory.getData("Device/SubDeviceList/Battery/Charge/Sensor/Value") * 100
            eventi.append(u"La mia batteria è al {}%.".format(int(carica)))
        except:
            pass

        # 6. FUSIONE EVENTI RECENTI
        # Gli eventi recenti servono come contesto per combinazioni,
        # ma non devono duplicarsi né contenere "Evento recente:" annidati.
        eventi_memoria = self._eventi_recenti_validi()

        for evento in eventi_memoria:
            evento_pulito = evento.strip()
            
            # Non riportare eventi tattili/audio scaduti nel testo:
            eventi_con_scadenza = [
                "mano_destra",
                "mano_sinistra",
                "carezza_testa",
                "entrambe_mani",
                "rumore_improvviso",
                "rumore_singolo",
                "battiti_mani"
            ]

            salta = False

            for nome in eventi_con_scadenza:
                if nome in evento_pulito.lower():
                    if not self.evento_recente(nome):
                        salta = True
                    break

            if salta:
                continue

            if not evento:
                continue

            # Evita "Evento recente: Evento recente: ..."
            while evento_pulito.lower().startswith("evento recente:"):
                evento_pulito = evento_pulito.split(":", 1)[1].strip()

            if "interazione_utente" in evento_pulito.lower():
                continue

            # Non ha senso memorizzare/interpolare marker generici
            if evento_pulito in [u"INTERAZIONE_UTENTE", u"INTERAZIONE_UTENTE."]:
                continue

            frase_recente = u"Evento recente: {}".format(evento_pulito)

            # Evita duplicati sia nella forma normale sia nella forma recente
            if evento_pulito not in eventi and frase_recente not in eventi:
                eventi.append(frase_recente)

        return u"REPORT: " + u" ".join(eventi)
