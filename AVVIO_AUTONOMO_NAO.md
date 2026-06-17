# Avvio autonomo NAO

## Obiettivo

Rendere il robot NAO indipendente dall'avvio manuale del progetto da VS Code.

Il sistema segue questa catena:

```text
Accensione PC
   |
Avvio automatico server PC
   |
Accensione NAO
   |
autoload.ini avvia scripts/nao_autonomous_bootstrap.py
   |
NAO contatta il server PC
   |
Il server verifica che NAO sia raggiungibile
   |
Il server avvia scripts/autonomous_watchdog.py
   |
Il watchdog avvia soul.py
   |
Il sistema autonomo resta attivo
```

## Componenti

- `scripts/nao_autonomous_bootstrap.py`: gira sul NAO, scrive lo stato in `ALMemory`, chiama il PC su `/ping` e poi su `/start`.
- `scripts/pc_autostart_server.py`: gira sul PC, espone gli endpoint HTTP locali e avvia il watchdog.
- `scripts/autonomous_watchdog.py`: gira sul PC, avvia `soul.py`, controlla `runtime/heartbeat.txt` e riavvia il processo in caso di crash o blocco.
- `start_pc_autostart_server.bat`: helper Windows per avviare il server PC.
- `start_nao_autonomo.bat`: helper Windows per avviare direttamente il watchdog.
- `start_nao_autonomo.sh` e `start_nao_autonomo.py`: helper per avvio diretto in ambiente Linux/NAO.

## Configurazione IP

Controllare questi valori prima dell'avvio:

- IP robot usato da `soul.py`: variabile `NAO_IP`, default `172.16.165.86`.
- IP robot atteso dal server PC: `NAO_ROBOT_IP` in `start_pc_autostart_server.bat`, default `172.16.165.86`.
- IP PC chiamato dal NAO: `PC_IP` in `scripts/nao_autonomous_bootstrap.py`, attualmente `172.16.165.75`.
- Porta server PC: `PC_PORT` in `scripts/nao_autonomous_bootstrap.py`, default `8765`.
- Porta NAOqi: `NAO_ROBOT_PORT`, default `9559`.

Se cambia rete o indirizzo DHCP, aggiornare sia il lato PC sia il lato NAO.

## Avvio lato PC

Da Windows:

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

## Avvio lato NAO

Il bootstrap da configurare in autoload e':

```text
/home/nao/NAOTirocinio/scripts/nao_autonomous_bootstrap.py
```

All'avvio lo script:

1. scrive `AutonomousSystem/Status = BOOTSTRAP_STARTED` in `ALMemory`;
2. scrive `AutonomousSystem/Command = START`;
3. chiama il PC su `/ping`;
4. se il PC risponde, chiama `/start`;
5. aggiorna `AutonomousSystem/Status` con `WATCHDOG_STARTED`, `PC_NOT_AVAILABLE` o `WATCHDOG_START_FAILED`.

Il log lato NAO viene scritto in:

```text
/home/nao/autonomous_bootstrap.log
```

## Watchdog

Il watchdog avvia `soul.py` dalla root del progetto e scrive stdout/stderr in:

```text
runtime/soul_onboard.log
```

Controlla:

- processo `soul.py` terminato o crashato;
- heartbeat non aggiornato in `runtime/heartbeat.txt` per piu' di 60 secondi.

Parametri principali in `scripts/autonomous_watchdog.py`:

- `TIMEOUT_HEARTBEAT = 60`
- `CONTROLLO_INTERVALLO = 2`
- `MAX_RIAVVII_CONSECUTIVI = 5`
- `PAUSA_RIAVVIO_BASE = 5`
- `PAUSA_RIAVVIO_MAX = 60`

Dopo troppi riavvii consecutivi il watchdog si ferma, per evitare loop incontrollati.

## Variabili utili

- `NAO_IP`: IP usato da `soul.py` per connettersi al robot.
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

## Comandi da Choregraphe

`soul.py` legge `AutonomousSystem/Command` da `ALMemory`.

Comandi gestiti:

- `STOP`: ferma subito il cammino.
- `START`: avvia il pattugliamento, come `VAI`.
- `STATUS`: fa rispondere il robot con lo stato.
- `SAY_HELLO`: invia un saluto.
- `VAI`: avvia il pattugliamento.
- `CAMMINA`: avvia il pattugliamento.
- `SHUTDOWN`: attualmente viene ignorato per sicurezza dal thread Choregraphe.

`soul.py` pubblica anche:

- `AutonomousSystem/Heartbeat`
- `AutonomousSystem/Status`
- `AutonomousSystem/LastEvent`

## Avvio diretto senza server PC

Per test locali su Windows:

```bat
start_nao_autonomo.bat
```

Per test in ambiente Linux/NAO:

```bash
./start_nao_autonomo.sh
```

Questi helper saltano il server autostart e lanciano direttamente il watchdog.

## Checklist rapida

1. PC e NAO sono sulla stessa rete.
2. `NAO_ROBOT_IP` punta al robot.
3. `PC_IP` in `scripts/nao_autonomous_bootstrap.py` punta al PC.
4. `NAO_PYTHON` punta a Python 2.7 con NAOqi.
5. Il server PC risponde su `/ping`.
6. `/robot` restituisce `ROBOT_REACHABLE`.
7. `/start` restituisce `WATCHDOG_STARTED` o `WATCHDOG_ALREADY_RUNNING`.
8. `runtime/heartbeat.txt` viene aggiornato mentre `soul.py` gira.

## Diagnostica

- Server PC non raggiungibile: controllare firewall, IP del PC e porta `8765`.
- Robot non raggiungibile: controllare `NAO_ROBOT_IP`, rete e porta `9559`.
- Watchdog parte ma `soul.py` crasha: leggere `runtime/soul_onboard.log`.
- Bootstrap NAO non parte: leggere `/home/nao/autonomous_bootstrap.log`.
- Comandi vocali assenti: verificare `ABILITA_VOCE_COMANDI=1` e disponibilita' di `ALSpeechRecognition`.
