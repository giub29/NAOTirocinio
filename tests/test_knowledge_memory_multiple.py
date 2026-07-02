# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import re
import shutil
import sys
import tempfile
import unittest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class KnowledgeMemoryMultipleTest(unittest.TestCase):

    def setUp(self):
        import behaviors.event_system.knowledge_memory as knowledge_memory

        self.knowledge_memory = knowledge_memory
        self.original_data_dir = knowledge_memory.DATA_DIR
        self.original_memory_path = knowledge_memory.MEMORY_PATH
        self.tmpdir = tempfile.mkdtemp()
        knowledge_memory.DATA_DIR = self.tmpdir
        knowledge_memory.MEMORY_PATH = os.path.join(
            self.tmpdir,
            "knowledge_memory.json"
        )

    def tearDown(self):
        self.knowledge_memory.DATA_DIR = self.original_data_dir
        self.knowledge_memory.MEMORY_PATH = self.original_memory_path
        shutil.rmtree(self.tmpdir)

    def _count_generated_conditions(self):
        path = os.path.join(
            BASE_DIR,
            "behaviors",
            "condition_system",
            "generated_conditions"
        )
        return len([
            nome for nome in os.listdir(path)
            if nome.endswith(".py")
        ])

    def test_mondo_con_piu_segnali_produce_piu_ipotesi(self):
        mondo = (
            "REPORT: OCR testo leggibile con orario aperto oggi. "
            "Accesso riservato: vietato entrare senza autorizzazione. "
            "Seguire il percorso verso uscita. Attenzione pavimento "
            "bagnato. Servizio disponibile con pagamento."
        )

        ipotesi = self.knowledge_memory.costruisci_ipotesi_multiple_da_evento(
            "informazione_operativa",
            mondo
        )
        concetti = set([i.get("concetto") for i in ipotesi])
        campi_obbligatori = [
            "concetto",
            "ipotesi",
            "evidenze",
            "affordance",
            "funzione_probabile",
            "utilita_contestuale",
            "conseguenze_possibili",
            "fiducia",
            "origine"
        ]

        self.assertGreaterEqual(len(ipotesi), 4)
        self.assertIn("fonte_informativa", concetti)
        self.assertIn("riferimento_temporale", concetti)
        self.assertIn("vincolo_o_regola", concetti)
        self.assertIn("possibile_rischio", concetti)

        for voce in ipotesi:
            for campo in campi_obbligatori:
                self.assertIn(campo, voce)

    def test_ipotesi_non_dipendono_da_parole_oggetto_hardcoded(self):
        parole_non_semantiche = [
            "elemento_alpha",
            "elemento_beta",
            "elemento_gamma",
            "elemento_delta"
        ]
        segnali = (
            "testo leggibile orario aperto attenzione accesso vietato "
            "seguire percorso servizio pagamento"
        )
        mondo_con_oggetti = (
            "vedo " + " ".join(parole_non_semantiche) + " " + segnali
        )
        mondo_generico = "vedo elementi ambientali " + segnali

        ipotesi_oggetti = self.knowledge_memory.costruisci_ipotesi_multiple_da_evento(
            "informazione_operativa",
            mondo_con_oggetti
        )
        ipotesi_generiche = self.knowledge_memory.costruisci_ipotesi_multiple_da_evento(
            "informazione_operativa",
            mondo_generico
        )

        concetti_oggetti = set([i.get("concetto") for i in ipotesi_oggetti])
        concetti_generici = set([i.get("concetto") for i in ipotesi_generiche])

        self.assertEqual(concetti_generici, concetti_oggetti)
        self.assertGreater(len(concetti_generici), 1)

    def test_salva_ipotesi_semantica_conserva_nuovi_campi(self):
        ipotesi = {
            "concetto": "indicazione_operativa",
            "ipotesi": "la scena suggerisce un'azione possibile",
            "evidenze": ["seguire", "percorso"],
            "affordance": ["seguire una procedura"],
            "funzione_probabile": "guidare un comportamento operativo",
            "utilita_contestuale": "aiuta a pianificare",
            "conseguenze_possibili": ["azione piu' mirata"],
            "fiducia": 0.42,
            "origine": "informazione_operativa"
        }

        salvata = self.knowledge_memory.salva_ipotesi_semantica(
            ipotesi,
            "mondo di test"
        )

        self.assertEqual(salvata["affordance"], ipotesi["affordance"])
        self.assertEqual(
            salvata["funzione_probabile"],
            ipotesi["funzione_probabile"]
        )
        self.assertEqual(
            salvata["utilita_contestuale"],
            ipotesi["utilita_contestuale"]
        )
        self.assertEqual(
            salvata["conseguenze_possibili"],
            ipotesi["conseguenze_possibili"]
        )

    def test_supervisore_resta_compatibile_con_vecchia_funzione(self):
        import behaviors.autonomy_supervisor as supervisor

        prima = self._count_generated_conditions()
        original_multiple = supervisor.costruisci_ipotesi_multiple_da_evento
        original_single = supervisor.costruisci_ipotesi_da_evento
        original_save = supervisor.salva_ipotesi_semantica

        chiamate = {"single": 0, "save": 0}

        def costruisci_singola(evento, mondo):
            chiamate["single"] += 1
            return {
                "concetto": "fonte_informativa",
                "ipotesi": "compatibilita' vecchia",
                "evidenze": ["testo"],
                "fiducia": 0.3,
                "origine": evento
            }

        def salva_fake(ipotesi, mondo=None):
            chiamate["save"] += 1
            return dict(ipotesi)

        try:
            supervisor.costruisci_ipotesi_multiple_da_evento = None
            supervisor.costruisci_ipotesi_da_evento = costruisci_singola
            supervisor.salva_ipotesi_semantica = salva_fake

            stato_runtime = {
                "eventi": {"informazione_operativa": True},
                "eventi_reali": {},
                "evento_strutturato": {}
            }
            salvate = supervisor.salva_conoscenza_semantica_da_evento(
                "OCR testo leggibile",
                stato_runtime
            )
        finally:
            supervisor.costruisci_ipotesi_multiple_da_evento = original_multiple
            supervisor.costruisci_ipotesi_da_evento = original_single
            supervisor.salva_ipotesi_semantica = original_save

        dopo = self._count_generated_conditions()

        self.assertEqual(chiamate["single"], 1)
        self.assertEqual(chiamate["save"], 1)
        self.assertEqual(len(salvate), 1)
        self.assertEqual(prima, dopo)

    def test_osservazione_ripetuta_rafforza_fiducia_e_conferme(self):
        mondo = (
            "REPORT: OCR testo leggibile. Seguire percorso verso uscita. "
            "Accesso riservato e servizio disponibile."
        )
        ipotesi = self.knowledge_memory.costruisci_ipotesi_multiple_da_evento(
            "informazione_operativa",
            mondo
        )
        scelta = [
            i for i in ipotesi
            if i.get("concetto") == "indicazione_operativa"
        ][0]
        salvata = self.knowledge_memory.salva_ipotesi_semantica(
            scelta,
            mondo
        )

        esito = self.knowledge_memory.aggiorna_ipotesi_da_osservazione(
            mondo,
            evento="informazione_operativa"
        )
        aggiornata = self.knowledge_memory.elenco_conoscenze()[0]

        self.assertGreater(esito["confermate"], 0)
        self.assertGreater(aggiornata["fiducia"], salvata["fiducia"])
        self.assertEqual(aggiornata["conferme"], 1)

    def test_nuove_evidenze_vengono_fuse_senza_duplicati(self):
        ipotesi = {
            "concetto": "indicazione_operativa",
            "ipotesi": "la scena suggerisce un'azione possibile",
            "evidenze": ["seguire"],
            "affordance": ["seguire una procedura"],
            "funzione_probabile": "guidare un comportamento operativo",
            "utilita_contestuale": "trasforma osservazioni in possibili azioni",
            "conseguenze_possibili": ["azione piu' mirata"],
            "fiducia": 0.40,
            "origine": "informazione_operativa"
        }
        self.knowledge_memory.salva_ipotesi_semantica(
            ipotesi,
            "REPORT: seguire indicazione"
        )

        self.knowledge_memory.aggiorna_ipotesi_da_osservazione(
            "REPORT: testo leggibile. Seguire istruzioni e premere conferma.",
            evento="informazione_operativa"
        )
        voce = [
            v for v in self.knowledge_memory.elenco_conoscenze()
            if v.get("concetto") == "indicazione_operativa"
        ][0]

        self.assertIn("seguire", voce["evidenze"])
        self.assertIn("premere", voce["evidenze"])
        self.assertEqual(
            len(voce["evidenze"]),
            len(set(voce["evidenze"]))
        )

    def test_conoscenza_stabile_diventa_true_oltre_soglia(self):
        ipotesi = {
            "concetto": "indicazione_operativa",
            "ipotesi": "la scena suggerisce un'azione possibile",
            "evidenze": ["seguire"],
            "affordance": ["seguire una procedura"],
            "funzione_probabile": "guidare un comportamento operativo",
            "utilita_contestuale": "trasforma osservazioni in possibili azioni",
            "conseguenze_possibili": ["azione piu' mirata"],
            "fiducia": 0.58,
            "origine": "informazione_operativa"
        }
        self.knowledge_memory.salva_ipotesi_semantica(
            ipotesi,
            "REPORT: seguire indicazione"
        )

        mondo = "REPORT: testo leggibile. Seguire percorso verso uscita."
        self.knowledge_memory.aggiorna_ipotesi_da_osservazione(
            mondo,
            evento="informazione_operativa"
        )
        self.knowledge_memory.aggiorna_ipotesi_da_osservazione(
            mondo,
            evento="informazione_operativa"
        )
        voce = self.knowledge_memory.elenco_conoscenze()[0]

        self.assertTrue(voce["conoscenza_stabile"])
        self.assertTrue(self.knowledge_memory.ipotesi_pronta_per_condizione(voce))

    def test_aggiornamento_supervisore_non_genera_condizioni(self):
        import behaviors.autonomy_supervisor as supervisor

        prima = self._count_generated_conditions()
        original_multiple = supervisor.costruisci_ipotesi_multiple_da_evento
        original_save = supervisor.salva_ipotesi_semantica
        original_update = supervisor.aggiorna_ipotesi_da_osservazione

        try:
            supervisor.costruisci_ipotesi_multiple_da_evento = (
                self.knowledge_memory.costruisci_ipotesi_multiple_da_evento
            )
            supervisor.salva_ipotesi_semantica = (
                self.knowledge_memory.salva_ipotesi_semantica
            )
            supervisor.aggiorna_ipotesi_da_osservazione = (
                self.knowledge_memory.aggiorna_ipotesi_da_osservazione
            )

            stato_runtime = {
                "eventi": {"informazione_operativa": True},
                "eventi_reali": {},
                "evento_strutturato": {}
            }
            supervisor.salva_conoscenza_semantica_da_evento(
                "REPORT: OCR testo leggibile. Seguire percorso verso uscita.",
                stato_runtime
            )
        finally:
            supervisor.costruisci_ipotesi_multiple_da_evento = original_multiple
            supervisor.salva_ipotesi_semantica = original_save
            supervisor.aggiorna_ipotesi_da_osservazione = original_update

        dopo = self._count_generated_conditions()

        self.assertEqual(prima, dopo)
        self.assertIn("aggiornamento_conoscenza_semantica", stato_runtime)
        self.assertIn("confermate", stato_runtime["aggiornamento_conoscenza_semantica"])

    def test_recupera_conoscenza_stabile_rilevante(self):
        ipotesi = {
            "concetto": "indicazione_operativa",
            "ipotesi": "la scena suggerisce un'azione possibile",
            "evidenze": ["seguire", "premere"],
            "affordance": ["seguire una procedura"],
            "funzione_probabile": "guidare un comportamento operativo",
            "utilita_contestuale": "trasforma osservazioni in possibili azioni",
            "conseguenze_possibili": ["azione piu' mirata"],
            "fiducia": 0.82,
            "origine": "informazione_operativa",
            "conoscenza_stabile": True
        }
        salvata = self.knowledge_memory._costruisci_voce_salvata(
            ipotesi,
            "REPORT: seguire e premere"
        )
        salvata["conferme"] = 2
        salvata["conoscenza_stabile"] = True
        self.knowledge_memory._salva_memoria({"ipotesi": [salvata]})

        recuperate = (
            self.knowledge_memory.recupera_conoscenze_stabili_rilevanti(
                "REPORT: testo leggibile. Seguire istruzioni e premere.",
                evento="informazione_operativa"
            )
        )

        self.assertEqual(len(recuperate), 1)
        self.assertEqual(recuperate[0]["concetto"], "indicazione_operativa")
        self.assertGreater(recuperate[0]["punteggio_rilevanza"], 0)

    def test_supervisore_espone_conoscenze_semantiche_attive(self):
        import behaviors.autonomy_supervisor as supervisor

        ipotesi = {
            "concetto": "indicazione_operativa",
            "ipotesi": "la scena suggerisce un'azione possibile",
            "evidenze": ["seguire", "premere"],
            "affordance": ["seguire una procedura"],
            "funzione_probabile": "guidare un comportamento operativo",
            "utilita_contestuale": "trasforma osservazioni in possibili azioni",
            "conseguenze_possibili": ["azione piu' mirata"],
            "fiducia": 0.82,
            "origine": "informazione_operativa",
            "conoscenza_stabile": True
        }
        salvata = self.knowledge_memory._costruisci_voce_salvata(
            ipotesi,
            "REPORT: seguire e premere"
        )
        salvata["conferme"] = 2
        salvata["conoscenza_stabile"] = True
        self.knowledge_memory._salva_memoria({"ipotesi": [salvata]})

        prima = self._count_generated_conditions()
        original_retrieve = supervisor.recupera_conoscenze_stabili_rilevanti
        original_update = supervisor.aggiorna_ipotesi_da_osservazione
        original_save = supervisor.salva_ipotesi_semantica

        try:
            supervisor.recupera_conoscenze_stabili_rilevanti = (
                self.knowledge_memory.recupera_conoscenze_stabili_rilevanti
            )
            supervisor.aggiorna_ipotesi_da_osservazione = (
                self.knowledge_memory.aggiorna_ipotesi_da_osservazione
            )
            supervisor.salva_ipotesi_semantica = (
                self.knowledge_memory.salva_ipotesi_semantica
            )

            stato_runtime = {
                "eventi": {"informazione_operativa": True},
                "eventi_reali": {},
                "evento_strutturato": {
                    "eventi_core": ["informazione_operativa"]
                }
            }
            firma = {
                "eventi": {"informazione_operativa": True},
                "eventi_attivi": {}
            }
            conoscenze = supervisor.recupera_conoscenze_semantiche_attive(
                "REPORT: testo leggibile. Seguire istruzioni e premere.",
                stato_runtime,
                firma=firma
            )
        finally:
            supervisor.recupera_conoscenze_stabili_rilevanti = original_retrieve
            supervisor.aggiorna_ipotesi_da_osservazione = original_update
            supervisor.salva_ipotesi_semantica = original_save

        dopo = self._count_generated_conditions()

        self.assertEqual(prima, dopo)
        self.assertEqual(len(conoscenze), 1)
        self.assertIn("conoscenze_semantiche_attive", stato_runtime)
        self.assertEqual(
            stato_runtime["conoscenze_semantiche_attive"][0]["concetto"],
            "indicazione_operativa"
        )

    def test_codice_senza_riferimenti_a_oggetti_specifici(self):
        proibite = [
            "lava" + "gna",
            "orolo" + "gio",
            "moni" + "tor",
            "por" + "ta",
            "car" + "tello"
        ]
        file_da_controllare = [
            os.path.join(
                BASE_DIR,
                "behaviors",
                "event_system",
                "knowledge_memory.py"
            ),
            os.path.join(
                BASE_DIR,
                "behaviors",
                "autonomy_supervisor.py"
            )
        ]

        for path in file_da_controllare:
            with open(path, "r") as f:
                contenuto = f.read().lower()
            for parola in proibite:
                self.assertIsNone(
                    re.search(r"\b" + re.escape(parola) + r"\b", contenuto)
                )


if __name__ == "__main__":
    unittest.main()
