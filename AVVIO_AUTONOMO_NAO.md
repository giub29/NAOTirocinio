# Avvio autonomo NAO

## Obiettivo

Rendere il robot NAO indipendente dall'avvio manuale del progetto da VS Code e dal PC.

Il PC serve solo per sviluppo, debug o stop manuale quando ci si collega al robot. In uso normale NAO deve avere solo:

- il progetto copiato sul robot;
- il bootstrap configurato in autoload;
- connessione WiFi funzionante, necessaria per eventuali chiamate OpenAI.

Il sistema segue questa catena:

```text
Accensione NAO
   |
autoload.ini avvia scripts/nao_autonomous_bootstrap.py
   |
NAO avvia scripts/autonomous_watchdog.py localmente
   |
Il watchdog avvia soul.py
   |
Il sistema autonomo resta attivo
```

## Componenti

- `scripts/nao_autonomous_bootstrap.py`: gira sul NAO, scrive lo stato in `ALMemory` e avvia il watchdog locale.
- `scripts/autonomous_watchdog.py`: gira sul NAO, avvia `soul.py`, controlla `runtime/heartbeat.txt` e riavvia il processo in caso di crash o blocco.
- `start_nao_autonomo.sh` e `start_nao_autonomo.py`: helper per avvio diretto in ambiente Linux/NAO.
- `scripts/pc_autostart_server.py` e `start_pc_autostart_server.bat`: fallback/debug da PC, non necessari per l'avvio autonomo reale.
- `start_nao_autonomo.bat`: helper Windows per test da PC.

Il bootstrap non invia piu' `START` come comando di cammino. All'accensione il sistema parte, resta in ascolto e reagisce agli eventi reali, per esempio i tocchi, senza iniziare automaticamente la pattuglia. Per camminare serve ancora un comando esplicito `vai`/`cammina` o `VAI`/`CAMMINA` via `ALMemory`.

## Configurazione rete

Controllare questi valori prima dell'avvio:

- Su NAO, `NAO_IP` viene impostato a `127.0.0.1` dal bootstrap.
- Il WiFi deve dare accesso a internet se si vogliono usare visione LLM, generazione condizioni o riparazione condizioni.
- `OPENAI_API_KEY` deve essere disponibile su NAO, preferibilmente in `/data/home/nao/NAOTirocinio/config/openai_api_key.txt`.
- Gli IP del PC non sono necessari in modalita' onboard.

Il fallback PC resta disponibile solo impostando `BOOTSTRAP_MODE=pc` oppure `BOOTSTRAP_MODE=auto`.

## Avvio lato PC opzionale

Da Windows, solo per debug/fallback:

```bat
start_pc_autostart_server.bat
```

Lo script imposta:

```bat
NAO_AUTONOMOUS_LIFE=1
NAO_PYTHON=C:\Python27\python.exe
NAO_ROBOT_IP=172.16.165.86
NAO_ROBOT_PORT=9559
```

`NAO_PYTHON` deve puntare all'interprete Python con SDK NAOqi disponibile.

Nel ramo attuale `soul.py` salta temporaneamente la creazione di `NaoSystem`; per questo, quando si avvia il watchdog dal PC, e' opportuno avere anche:

```bat
set CHOREGRAPHE_BOOT=1
set SKIP_AUTONOMOUS_LIFE_CONFIG=1
```

Endpoint esposti dal server:

- `http://127.0.0.1:8765/ping`: verifica che il server PC sia attivo.
- `http://127.0.0.1:8765/robot`: verifica la raggiungibilita' del robot su porta NAOqi.
- `http://127.0.0.1:8765/status`: indica se il watchdog e' gia' in esecuzione.
- `http://127.0.0.1:8765/start`: avvia il watchdog se il robot e' raggiungibile.

## Avvio lato NAO indipendente

Il bootstrap da configurare in autoload e':

```text
/data/home/nao/NAOTirocinio/scripts/nao_autonomous_bootstrap.py
```

All'avvio lo script:

1. scrive `AutonomousSystem/Status = BOOTSTRAP_STARTED` in `ALMemory`;
2. lascia `AutonomousSystem/Command` vuoto e scrive `AutonomousSystem/BootstrapCommand = START`;
3. imposta `NAO_IP=127.0.0.1`, `CHOREGRAPHE_BOOT=1` e `SKIP_AUTONOMOUS_LIFE_CONFIG=1`;
4. carica `OPENAI_API_KEY` da file locale se presente;
5. avvia `scripts/autonomous_watchdog.py` direttamente sul robot;
6. aggiorna `AutonomousSystem/Status` con `WATCHDOG_ONBOARD_STARTED` oppure `WATCHDOG_ONBOARD_START_FAILED`.

Il log lato NAO viene scritto in:

```text
/home/nao/autonomous_bootstrap.log
```

Il log del watchdog onboard viene scritto in:

```text
runtime/watchdog_onboard.log
```

## Watchdog

Il watchdog avvia `soul.py` dalla root del progetto e scrive stdout/stderr in:

```text
runtime/soul_onboard.log
```

Controlla:

- processo `soul.py` terminato o crashato;
- heartbeat non aggiornato in `runtime/heartbeat.txt`.

Parametri principali in `scripts/autonomous_watchdog.py`:

- `WATCHDOG_TIMEOUT_HEARTBEAT`, default `180`
- `WATCHDOG_CONTROLLO_INTERVALLO`, default `3`
- `WATCHDOG_MAX_RIAVVII_CONSECUTIVI`, default `0`, cioe' nessun limite
- `WATCHDOG_PAUSA_RIAVVIO_BASE`, default `10`
- `WATCHDOG_PAUSA_RIAVVIO_MAX`, default `60`

Di default il watchdog non si ferma dopo un numero fisso di riavvii: resta vivo finche' viene fermato localmente.

## Variabili utili

- `NAO_IP`: IP usato da `soul.py` per connettersi al robot.
- `BOOTSTRAP_MODE=onboard`: default, avvio completamente locale sul robot.
- `BOOTSTRAP_MODE=pc`: usa il vecchio server PC.
- `BOOTSTRAP_MODE=auto`: prova prima onboard, poi fallback PC.
- `NAO_AUTONOMOUS_LIFE=1`: mantiene AutonomousLife gestito da NAOqi.
- `CHOREGRAPHE_BOOT=1`: disabilita l'input da tastiera nel thread di input.
- `SKIP_AUTONOMOUS_LIFE_CONFIG=1`: evita di riconfigurare AutonomousLife dal codice; nel ramo attuale e' necessario quando `NaoSystem` non viene inizializzato.
- `ABILITA_VOCE_COMANDI=1`: abilita i comandi vocali semplici `vai`, `cammina`, `fermati`, `stop`, `stato`.
- `OPENAI_API_KEY`: abilita decisioni LLM e generazione/riparazione condizioni.

## File di stato runtime

Durante l'esecuzione il sistema crea e mantiene:

- `runtime/heartbeat.txt`: aggiornato dal process `soul.py` per indicare che il sistema e' attivo.
- `runtime/soul_onboard.log`: log stdout/stderr del processo principale.
- `behaviors/event_system/world_model_memory.json`: modello persistente del mondo con credenze sullo stato di oggetti e ambienti.
- `runtime/evidence/`: cartella con evidenze e ipotesi temporanee relative ad anomalie rilevate e osservazioni mirate.
- `foto/`: cartella unica per tutte le immagini acquisite a runtime, incluse foto di volti sconosciuti, curiosita' autonoma e osservazioni mirate.

Il watchdog resta attivo e riavvia `soul.py` senza limite predefinito. Per imporre un limite, impostare `WATCHDOG_MAX_RIAVVII_CONSECUTIVI` a un valore maggiore di zero prima di avviarlo.

## Comandi da Choregraphe

`soul.py` legge `AutonomousSystem/Command` da `ALMemory`.

Comandi gestiti:

- `STOP`: ferma subito il cammino.
- `START`: comando di bootstrap; non avvia il pattugliamento.
- `STATUS`: fa rispondere il robot con lo stato.
- `SAY_HELLO`: invia un saluto.
- `VAI`: avvia il pattugliamento.
- `CAMMINA`: avvia il pattugliamento.
- `SHUTDOWN`: attualmente viene ignorato per sicurezza dal thread Choregraphe.

`soul.py` pubblica anche:

- `AutonomousSystem/Heartbeat`
- `AutonomousSystem/Status`
- `AutonomousSystem/LastEvent`

## Avvio diretto

Per test locali su Windows:

```bat
start_nao_autonomo.bat
```

Per test in ambiente Linux/NAO:

```bash
./start_nao_autonomo.sh
```

Questi helper lanciano direttamente il watchdog.

## Checklist rapida

1. Il progetto e' in `/data/home/nao/NAOTirocinio`.
2. `scripts/nao_autonomous_bootstrap.py` e' configurato in autoload.
3. NAO e' collegato al WiFi.
4. Se serve LLM, `config/openai_api_key.txt` esiste sul robot.
5. Dopo l'accensione, `/home/nao/autonomous_bootstrap.log` contiene `WATCHDOG_ONBOARD_STARTED`.
6. `runtime/heartbeat.txt` viene aggiornato mentre `soul.py` gira.
7. Un tocco su testa/mano genera una reazione senza PC acceso.

## Diagnostica

- Watchdog onboard non parte: leggere `/home/nao/autonomous_bootstrap.log` e `runtime/watchdog_onboard.log`.
- Watchdog parte ma `soul.py` crasha: leggere `runtime/soul_onboard.log`.
- Bootstrap NAO non parte: leggere `/home/nao/autonomous_bootstrap.log`.
- Comandi vocali assenti: verificare `ABILITA_VOCE_COMANDI=1` e disponibilita' di `ALSpeechRecognition`.
