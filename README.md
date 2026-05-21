# NAOTirocinio

Sistema autonomo per robot NAO, pensato per esplorazione di laboratorio, interazione sociale, riconoscimento volti, gestione della sicurezza e apprendimento progressivo di nuove condizioni comportamentali tramite LLM.

Il progetto non si limita a chiedere decisioni al modello: costruisce una rappresentazione strutturata degli eventi, valuta condizioni Python gia' apprese, puo' generarne di nuove in modo controllato, ne conserva i metadati e isola quelle incoerenti o difettose.

## Panoramica

Flusso principale:

```text
Sensori NAO
  -> report semantico + eventi strutturati
  -> soul.py
  -> safety immediata / gestione volti / navigazione laboratorio
  -> autonomy_supervisor
  -> condizioni generate oppure generazione LLM controllata
  -> validazione decisione
  -> esecuzione azioni
  -> memoria e metadati
```

Funzioni principali:

- pattugliamento autonomo del laboratorio con comando `vai` o `cammina`;
- lettura continua di testa, mani e bumper dei piedi per non perdere tocchi brevi;
- riconoscimento di volti noti e apprendimento di volti ignoti;
- gestione di ostacoli, urti e pericolo caduta;
- costruzione di eventi strutturati come `ostacolo_destra`, `carezza_testa`, `volto_ignoto`, `camminando`;
- estrazione prudente di eventi sconosciuti dal testo sensoriale, con memoria di ricorrenza prima della generazione;
- generazione autonoma di condizioni Python in `behaviors/generated_conditions`;
- quarantena, validazione, rifiuto e riparazione delle condizioni generate;
- memoria persistente in `data/memoria.json`;
- heartbeat e integrazione con Choregraphe/NAOqi tramite ALMemory;
- bootstrap da robot e watchdog lato PC per avvio autonomo.

## Struttura

```text
NAOTirocinio/
|-- soul.py                         # ciclo principale
|-- sensi.py                        # sensori, report semantico, eventi recenti
|-- start_nao_autonomo.py           # helper avvio diretto multipiattaforma
|-- start_nao_autonomo.bat          # helper Windows per avvio watchdog
|-- start_nao_autonomo.sh           # helper Linux/NAO per avvio diretto
|-- start_pc_autostart_server.bat   # avvio server autostart PC
|-- AVVIO_AUTONOMO_NAO.md           # note operative per bootstrap autonomo
|
|-- core/
|   |-- memory_manager.py           # memoria persistente
|   |-- robot_state.py              # stato interno sintetico del robot
|   `-- goal_manager.py             # obiettivo corrente
|
|-- modules/
|   |-- hardware_control.py         # corpo, motori, LED, movimento, foto
|   |-- voice_interaction.py        # sintesi vocale
|   |-- vision_perception.py        # volti e tracking
|   `-- system_manager.py           # NAOqi, ALMemory, comandi Choregraphe
|
|-- behaviors/
|   |-- action_behavior.py          # validazione ed esecuzione azioni
|   |-- autonomy_supervisor.py      # regia dell'autonomia
|   |-- condition_generator.py      # generazione e validazione condizioni
|   |-- condition_manager.py        # caricamento ed esecuzione condizioni
|   |-- condition_memory.py         # metadati e affidabilita condizioni
|   |-- condition_repair.py         # rigenerazione condizioni rifiutate
|   |-- event_novelty_memory.py     # memoria ricorrenza eventi sconosciuti
|   |-- face_behavior.py            # gestione volti noti/ignoti
|   |-- lab_patrol_behavior.py      # navigazione laboratorio
|   |-- llm_behavior.py             # chiamate OpenAI per decisioni/visione
|   |-- safety_behavior.py          # emergenze e ostacoli durante cammino
|   |-- unknown_event_extractor.py  # estrazione eventi candidati da testo sensoriale
|   |-- event_novelty_memory.json   # stato persistente delle novita osservate
|   |-- generated_conditions/       # condizioni attive
|   |-- quarantine_conditions/      # condizioni in validazione
|   |-- rejected_conditions/        # condizioni scartate
|   `-- condition_metadata/         # metadati delle condizioni
|
|-- scripts/
|   |-- nao_autonomous_bootstrap.py # script da eseguire sul NAO
|   |-- pc_autostart_server.py      # server HTTP locale per avviare watchdog
|   `-- autonomous_watchdog.py      # controlla heartbeat e riavvia soul.py
|
`-- data/
    `-- memoria.json                # memoria del robot
```

## Componenti

### `soul.py`

E' il ciclo principale del sistema. Inizializza corpo, voce, vista, sistema e sensi; aggiorna heartbeat; legge input da tastiera o da Choregraphe; prepara il runtime per l'autonomia; decide se usare safety, navigazione laboratorio, condizioni generate o decisione LLM generale.

Comandi riconosciuti:

- `vai` / `cammina`: avvia pattugliamento e missione laboratorio;
- `stop` / `fermati` / `ferma`: ferma il robot;
- `status`: pubblica stato attivo e risponde a voce;
- `registra volto` / `impara volto`: forza apprendimento volto;
- `spegni`, `chiudi`, `esci`, `shutdown`, `spegni programma`: termina il sistema autonomo;
- in `MODALITA_TEST`, `test condizione <nome>` esegue una condizione specifica.

Se `ABILITA_VOCE_COMANDI=1`, `voice_interaction.py` abilita anche il riconoscimento vocale semplice per `vai`, `cammina`, `fermati`, `stop` e `stato`.

### `sensi.py`

Produce il report semantico `REPORT: ...` e mantiene una memoria breve degli eventi. Il monitor dei tocchi gira in thread separato per registrare eventi anche mentre il ciclo principale e' occupato da voce, LLM o altre operazioni lente.

Eventi gestiti:

- volti riconosciuti o ignoti;
- carezza sulla testa;
- tocco mano sinistra, mano destra o entrambe;
- bumper dei piedi e urti frontali/laterali;
- sonar sinistro/destro/frontale;
- rumori improvvisi, colpi singoli e battiti;
- rischio caduta o sollevamento;
- batteria.

### `autonomy_supervisor.py`

E' il punto di ingresso dell'autonomia appresa. Riceve `mondo` e `stato_runtime`, costruisce una firma della situazione e decide se:

- usare una condizione gia' generata;
- dare priorita a una situazione composta;
- generare una nuova condizione;
- forzare una generazione legata alla safety;
- non fare nulla e lasciare la decisione al comportamento LLM generale.

Usa cooldown e memoria dell'ultimo mondo generato per evitare duplicati e chiamate LLM troppo ravvicinate.

Quando il report contiene testo sensoriale nuovo ma non ancora coperto da eventi noti, il supervisore puo' arricchire la firma tramite `unknown_event_extractor.py`. La prima osservazione resta solo in memoria; l'evento diventa candidato alla generazione solo quando supera la soglia di ricorrenza registrata in `event_novelty_memory.json`.

### Eventi sconosciuti e novita

`unknown_event_extractor.py` trasforma concetti nuovi presenti nel report in eventi candidati, per esempio `porta_aperta_laboratorio`, senza chiamare LLM, senza modificare condizioni e senza eseguire azioni sul robot.

Il filtro e' volutamente conservativo:

- ignora parole banali gia' usate nei report, come `report`, `vedo`, `fermo`, `camminando`;
- non ricrea eventi gia' noti come `carezza_testa`, `volto_ignoto` o `ostacolo_destra`;
- scarta descrizioni troppo neutre se isolate, ad esempio solo `tavolo` o `sedia`;
- privilegia parole interessanti come `porta`, `bottiglia`, `telefono`, `fumo`, `acqua`, `grido`;
- mantiene al massimo tre esempi recenti per ogni novita.

`event_novelty_memory.py` registra quante volte un evento sconosciuto e' stato visto. Con la soglia attuale (`SOGLIA_OCCORRENZE_GENERAZIONE = 2`), una novita osservata una sola volta viene ricordata ma non genera condizioni; dalla seconda osservazione puo' diventare generabile, se non e' gia' stata marcata come generata.

### Condizioni autonome

Una condizione generata e' un file Python con due funzioni:

```python
def condizione(mondo, stato_runtime):
    return True

def comportamento():
    return {
        "azioni": [
            {"tipo": "parla", "testo": "Ho capito la situazione."}
        ],
        "memoria": []
    }
```

Il generatore:

1. chiede codice Python al LLM;
2. salva il file in `quarantine_conditions`;
3. blocca import, I/O, `exec`, `eval`, cicli e codice fuori funzione;
4. aggiunge una `condizione()` automatica se il LLM produce solo `comportamento()`;
5. sostituisce trigger troppo generici con trigger specifici quando possibile;
6. valida il modulo;
7. valida la coerenza semantica fra evento e azioni;
8. promuove in `generated_conditions` oppure sposta in `rejected_conditions`;
9. salva metadati in `condition_metadata`.

Durante l'estrazione eventi, `condition_generator.py` usa lo stesso arricchimento degli eventi sconosciuti del supervisore. Gli eventi noti non vengono sovrascritti; le novita servono solo a produrre trigger piu specifici quando sono diventate abbastanza ricorrenti.

Il manager carica le condizioni attive con priorita alle condizioni piu specifiche, composte e `durante_cammino`. Una condizione troppo generica viene ignorata quando il runtime richiede una condizione specifica.

### Metadati e riparazione

`condition_memory.py` crea e aggiorna file `.meta.json` con:

- mondo di origine;
- eventi attivi;
- stato robot di origine;
- numero di attivazioni;
- errori runtime;
- rifiuti;
- esiti di riparazione.

Se una condizione genera errori o produce decisioni incoerenti, `condition_manager.py` la sposta in `rejected_conditions` e prova a rigenerarla tramite `condition_repair.py`, se e' disponibile `OPENAI_API_KEY` e se il cooldown lo permette.

### Navigazione laboratorio

`lab_patrol_behavior.py` gestisce il pattugliamento quando `missione_laboratorio` e `in_pattugliamento` sono attivi.

Comportamento:

- ostacolo a destra: guarda a destra e corregge la traiettoria;
- ostacolo a sinistra: guarda a sinistra e corregge la traiettoria;
- ostacolo frontale: prova una micro-schivata;
- evento safety grave: prova a liberarsi, poi si ferma se resta bloccato.

### Safety

La safety ha priorita sul resto. In caso di urti, pericolo caduta o eventi fisici sensibili durante il cammino, il robot puo' fermarsi subito, parlare, aggiornare lo stato runtime e tentare una generazione safety dedicata.

Regole importanti:

- da fermo non parte in esplorazione autonoma solo perche vede qualcosa;
- durante cammino gli ostacoli laterali sono preferibilmente gestiti con micro-correzioni;
- pericolo reale o urto ai piedi richiedono arresto;
- le condizioni generate vengono validate anche rispetto al contesto di movimento.

## LLM e API

Il progetto usa chiamate HTTP verso OpenAI in `behaviors/llm_behavior.py` e `behaviors/condition_generator.py`.

Variabile richiesta:

```bash
OPENAI_API_KEY=...
```

Modelli attualmente usati nel codice:

- `gpt-4o-mini` per decisioni dell'anima;
- `gpt-4o-mini` con immagine per osservazione/autonomia visiva.

Se la chiave non e' presente, la generazione di condizioni viene saltata e il sistema continua con le condizioni esistenti e le logiche locali.

## Avvio

### Avvio manuale

```bash
cd NAOTirocinio
export NAO_AUTONOMOUS_LIFE=1
export SKIP_AUTONOMOUS_LIFE_CONFIG=1
python soul.py
```

Prima dell'avvio verificare:

- IP del robot in `soul.py` (`IP_ROBOT`);
- rete tra PC e NAO;
- SDK NAOqi disponibile nell'ambiente Python usato;
- `NAO_AUTONOMOUS_LIFE=1` e `SKIP_AUTONOMOUS_LIFE_CONFIG=1` nel ramo attuale, dove la configurazione diretta di `NaoSystem` e' saltata;
- `OPENAI_API_KEY`, se si vogliono usare decisioni LLM e generazione condizioni.

### Avvio autonomo

Componenti coinvolti:

- `scripts/nao_autonomous_bootstrap.py`: gira sul robot, scrive stato in ALMemory e chiama il PC;
- `scripts/pc_autostart_server.py`: espone endpoint locali `/ping`, `/robot`, `/status` e `/start`;
- `scripts/autonomous_watchdog.py`: avvia `soul.py`, controlla `runtime/heartbeat.txt`, scrive `runtime/soul_onboard.log` e riavvia il processo se si blocca;
- `start_pc_autostart_server.bat`: helper per avviare il server PC.

Per i dettagli operativi consultare `AVVIO_AUTONOMO_NAO.md`.

## Runtime e stato

`stato_runtime` contiene flag e memoria breve usati dal ciclo principale, ad esempio:

- `attesa_nome`;
- `riprendi_dopo_nome`;
- `missione_laboratorio`;
- `in_pattugliamento`;
- `comando_stop_immediato`;
- `controllo_manuale`;
- `mantieni_pattugliamento`;
- `eventi`;
- `eventi_reali`;
- `evento_strutturato`;
- `ultimo_evento_reale_tempo`;
- `volti_salutati`.

`costruisci_evento_strutturato()` converte report e runtime in una firma stabile:

```python
{
    "tipo": "ostacolo",
    "direzione": "destra",
    "categoria": "spaziale",
    "gravita": "media",
    "camminando": True,
    "eventi_core": ["ostacolo_destra"],
    "evento_composto": True
}
```

Questa firma permette al supervisore di distinguere meglio eventi sociali, spaziali, audio, sistema e safety.

## Azioni supportate

Le decisioni devono essere dizionari con lista `azioni`. Azioni principali:

- `parla`;
- `cammina`;
- `gira`;
- `fermati`;
- `posa`;
- `guarda`;
- `occhi`;
- `animazione`;
- `apprendi_volto`;
- `foto`.

`action_behavior.py` valida numeri, tipi azione e limiti prima di inviare i comandi ai moduli hardware.

## Memoria

La memoria fisica e' salvata in `data/memoria.json`.

Struttura tipica:

```json
{
  "ricordi_recenti": [
    {
      "timestamp": "2026-05-18 15:30:00",
      "contenuto": "NAO ha salutato una persona nota."
    }
  ],
  "fatti_importanti": {
    "nome_utente": "Marco"
  }
}
```

Le decisioni LLM possono aggiungere elementi a `memoria`; `soul.py` mantiene al massimo gli ultimi 20 ricordi recenti.

## Logging e debug

Il logging e' configurato in `soul.py`. Se disponibile, usa `colorlog`; altrimenti usa logging standard.

Logger ridotti a warning per contenere il rumore:

- `WATCHDOG`;
- `behaviors.autonomy_supervisor`;
- `behaviors.condition_generator`;
- `behaviors.safety_behavior`;
- `behaviors.condition_manager`.

Per debug piu dettagliato:

- impostare `DEBUG_STATO = True` in `soul.py`;
- impostare `self.debug_sensori = True` in `sensi.py`;
- usare `MODALITA_TEST = True` per test manuali di condizioni.
- controllare `runtime/soul_onboard.log` quando il sistema viene avviato dal watchdog.

## Note operative

- Le condizioni generate sono codice eseguibile: devono passare sempre da quarantena e validazione.
- Non modificare a mano `generated_conditions` senza controllare anche i relativi metadati.
- I file in `rejected_conditions` sono utili per capire cosa e' stato scartato.
- Le cartelle runtime/quarantena/rejected possono essere create automaticamente.
- L'avvio autonomo dipende dagli IP configurati tramite `NAO_IP`, `NAO_ROBOT_IP` e `PC_IP` in `scripts/nao_autonomous_bootstrap.py`.

## Stato del progetto

Versione documentata: sistema con supervisore autonomo, eventi strutturati, memoria delle novita sensoriali, condizioni generate, navigazione laboratorio, riparazione condizioni, comandi vocali opzionali e bootstrap/watchdog.

Ultimo aggiornamento README: 2026-05-21.
