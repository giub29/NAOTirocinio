# NAO Robot Soul - Sistema di Controllo Autonomo

Sistema intelligente di controllo per il robot umanoide NAO, sviluppato per fornire capacità autonome di navigazione, riconoscimento volti e interazione con l'ambiente.

---

## 📋 Sommario

- [Panoramica](#panoramica)
- [Architettura](#architettura)
- [Struttura del Progetto](#struttura-del-progetto)
- [Moduli Principali](#moduli-principali)
- [Funzioni Chiave](#funzioni-chiave)
- [Installazione](#installazione)
- [Uso](#uso)
- [Configurazione](#configurazione)

---

## 🎯 Panoramica

NAO Soul è un sistema completo di controllo per il robot NAO che integra:

- **Riconoscimento Volti**: Identifica persone note e impara nuovi volti
- **Memoria Persistente**: Mantiene ricordi di interazioni e fatti importanti
- **Sistema LLM**: Utilizza modelli di linguaggio per decisioni intelligenti
- **Sicurezza**: Gestisce automaticamente situazioni di emergenza e ostacoli
- **Interazione Naturale**: Comunica tramite voce e gesti

### Flusso Operativo Principale

```
Sensori → Analisi Ambiente → Decisione LLM → Azioni Robot → Memoria
   ↑                                                              ↓
   └─────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architettura

### Componenti Principali

```
soul.py (Ciclo Principale)
├── Hardware Control
│   ├── corpo (Movimento, motori, LED)
│   ├── voce (Sintesi vocale)
│   └── vista (Riconoscimento volti)
├── Sensori
│   ├── mondo (Report semantico ambientale)
│   └── ostacoli
├── Comportamenti
│   ├── Sicurezza (Gestione emergenze)
│   ├── LLM (Decisioni intelligenti)
│   ├── Azioni (Esecuzione comandi)
│   └── Memoria (Persistenza dati)
└── Stato Runtime
    ├── Volti riconosciuti
    ├── Stato pattugliamento
    └── Input utente
```

---

## 📁 Struttura del Progetto

```
NAOTirocinio/
├── soul.py                    # Ciclo principale del robot
├── hardware_control.py        # Interfaccia motori e attuatori
├── sensi.py                   # Lettura sensori
├── voice_interaction.py       # Sintesi vocale e audio
├── vision_perception.py       # Riconoscimento e tracking volti
├── system_manager.py          # Gestione sistema robot
├── stop.py                    # Arresto di emergenza
├── test.py                    # Suite di test
├── memoria.json               # Memoria persistente
├── README.md                  # Questo file
│
├── behaviors/                 # Moduli comportamentali
│   ├── __init__.py
│   ├── action_behavior.py     # Validazione e esecuzione azioni
│   ├── face_behavior.py       # Gestione riconoscimento volti
│   ├── llm_behavior.py        # Integrazione LLM per decisioni
│   └── safety_behavior.py     # Gestione emergenze e sicurezza
│
└── core/                      # Moduli core
    ├── __init__.py
    ├── goal_manager.py        # Gestione obiettivi
    ├── memory_manager.py      # Persistenza memoria
    └── robot_state.py         # Stato del robot
```

---

## 🔑 Moduli Principali

### 1. **soul.py** - Ciclo Principale
Gestisce il flusso principale del robot, coordinando sensori, decisioni e azioni.

**Componenti Chiave:**

| Sezione | Descrizione |
|---------|-------------|
| **Costanti** | Timeout, messaggi, angoli di sguardo |
| **Variabili Globali** | Stato runtime, memoria, input utente |
| **Funzioni Helper** | Operazioni atomiche su sensori/attuatori |
| **main()** | Loop principale del robot |

---

## 📝 Funzioni Chiave

### Gestione Memoria

#### `aggiorna_memoria_da_decisione(decisione: Dict) → None`
**Scopo**: Aggiorna la memoria del robot in base alla decisione dell'LLM

**Elabora**:
- Ricordi recenti (ultimi 20)
- Fatti importanti su persone/oggetti
- Salva persistentemente su disco

```python
# Esempio di struttura memoria
{
    "ricordi_recenti": [
        {"timestamp": "2024-01-15 10:30:45", "contenuto": "..."}
    ],
    "fatti_importanti": {
        "nome_utente": "Marco",
        "colore_preferito": "blu"
    }
}
```

---

### Gestione Volti

#### `gestisci_volto_durante_cammino(mondo, corpo, voce, vista) → bool`
**Scopo**: Gestisce il riconoscimento di volti durante il movimento del robot

**Comportamento**:

```
Volto Riconosciuto?
├─ SÌ: Saluta → Registra → Continua
└─ NO (Ignoto)
   ├─ Robot in Movimento? → Ferma e Verifica
   ├─ Falso Positivo? → Ignora
   ├─ Instabile? → Attendi
   └─ Stabile → Chiedi Nome → Apprendi
```

**Funzioni Helper**:
- `_estrai_nome_riconosciuto()`: Estrae nome dal report
- `_saluta_volto_conosciuto()`: Interazione con persona nota
- `_attendi_stabilita_volto()`: Filtro per stabilità
- `_chiedi_nome_volto_ignoto()`: Richiesta interattiva

---

### Gestione Input Nome

#### `gestisci_input_nome(corpo, voce, vista) → bool`
**Scopo**: Processa l'input dell'utente per il riconoscimento di volti ignoti

**Comandi Riconosciuti**:
- `"nome Mario"` / `"mi chiamo Mario"` → Apprende volto
- `"vai"`, `"cammina"` → Errore (attesa nome)
- `"stop"`, `"fermati"` → Annulla operazione
- Invio vuoto → Continua senza memorizzare

**Flow**:
```
Input Validazione
├─ Vuoto → Continua
├─ Comando Stop → Ferma
├─ Comando Movimento → Avviso
├─ Nome Corto (<2 char) → Riprova
└─ Nome Valido
   ├─ Apprendi Volto
   ├─ Registra Nome
   └─ Riprendi Cammino se Necessario
```

---

### Ciclo Principale

#### `main() → None`
**Scopo**: Loop principale che coordina tutti i sistemi

**Fasi Ciclo**:

1. **Lettura Sensori**: `mondo = sensi.ottieni_report_semantico()`
2. **Aggiornamento Stato**: `stato_robot = aggiorna_stato_robot(...)`
3. **Gestione Emergenze**: Ostacoli, pericoli, collisioni
4. **Processamento Input**: Comandi utente
5. **Normalizzazione Mondo**: Riduzione rumore sensori
6. **Valutazione Interazione**: Priorità attività
7. **Pulizia Ambiente**: Rimozione ridondanze
8. **Elaborazione Decisione LLM**: Genera azioni
9. **Esecuzione**: Applica azioni al robot
10. **Memoria**: Salva stato

**Timing**:
- Ciclo: 100ms
- Timeout Inerzia: 30s (attiva iniziativa autonoma)
- Stabilità Volto: 2s

---

### Funzioni Helper del Ciclo

| Funzione | Descrizione |
|----------|-------------|
| `_inizializza_robot()` | Setup iniziale (motori, posa, tracking) |
| `_processa_input_utente()` | Estrae comandi da input |
| `_normalizza_mondo_fermo()` | Filtra messaggi quando fermo |
| `_processa_batteria()` | Evita ripetizione report batteria |
| `_valuta_interazione_reale()` | Distingue rumore da input valido |
| `_gestisci_iniziativa_robot()` | Scatta foto e analizza autonomamente |
| `_pulisci_mondo_da_volti_salutati()` | Rimuove ridondanze |
| `_aggiungi_stato_movimento()` | Informa LLM se robot in movimento |
| `_elabora_decisione()` | Chiama LLM e esegue azioni |
| `_riprendi_cammino_automatico()` | Continua pattugliamento se interrotto |

---

## ⚙️ Costanti Configurabili

```python
# Timeout e Durate
TEMPO_STABILITA_VOLTO = 2.0              # Secondi per stabilità volto
TEMPO_ATTESA_VOLTO_NOTO = 5.0           # Ricorda volti noti per N secondi
TEMPO_INERZIA_INIZIATIVA = 30           # Secondi prima di iniziativa autonoma
LUNGHEZZA_MAX_RICORDI = 20              # Numero ricordi salvati
LUNGHEZZA_MIN_NOME = 2                  # Minimo caratteri nome
VELOCITA_CAMMINO = 0.3                  # Velocità base movimento

# Angoli Sguardo (radianti)
ANGOLO_SGUARDO_VOLTO = (0.0, -0.45)     # Guarda volto direttamente
ANGOLO_SGUARDO_NEUTRO = (0.0, -0.35)    # Sguardo neutro
ANGOLO_SGUARDO_LEGGERO = (0.0, -0.1)    # Sguardo leggermente più alto
ANGOLO_SGUARDO_INIZIATIVA = (0.0, -0.2) # Sguardo esplorativo
```

---

## 🔧 Installazione

### Prerequisiti
- Python 2.7+ (per NAO Pepper) o Python 3.x
- Connessione di rete al robot
- Librerie NAO SDK installate

### Setup

```bash
# Clona il repository
git clone <repository_url> NAOTirocinio
cd NAOTirocinio

# Installa dipendenze (se necessario)
pip install -r requirements.txt

# Configura IP robot in soul.py
IP_ROBOT = "172.16.165.86"  # Modifica con IP del tuo robot

# Configura API Key OpenAI
export OPENAI_API_KEY="your-api-key"
```

---

## 🚀 Uso

### Avvio del Robot

```bash
python soul.py
```

### Comandi Interattivi

Durante l'esecuzione puoi:

```
Riconoscimento Volti:
  "nome Marco"          # Insegna il volto di Marco
  "mi chiamo Giulia"    # Insegna il volto di Giulia
  [INVIO]               # Continua senza memorizzare

Movimento:
  "vai"                 # Inizia pattugliamento
  "cammina"             # Continua cammino
  "stop"                # Ferma robot
  "fermati"             # Ferma e annulla

Altro:
  Ctrl+C                # Arresto di emergenza
```

### Output Log

Il robot registra gli eventi in console:

```
INFO:soul:Connessione al robot: 172.16.165.86
INFO:soul:Robot inizializzato
INFO:soul:Sistemi pronti
INFO:soul:SENSORI: Vedo un volto ignoto. SONO FERMO.
INFO:soul:Volto riconosciuto: Marco
INFO:soul:STATO: allegro
INFO:soul:OBIETTIVO: salutare
INFO:soul:Arresto richiesto dall'utente
INFO:soul:Sistema spento correttamente
```

---

## 🐛 Debugging

### Attivazione Debug Stato

```python
DEBUG_STATO = True  # In soul.py, riga ~36
```

Output dettagliato:
```
DEBUG:soul:STATO ROBOT: {"mondo": "...", "obiettivo": "...", ...}
DEBUG:soul:OBIETTIVO: salutare persone
DEBUG:soul:Volto ignoto durante movimento, fermo il robot
```

### Log Livelli

```python
# Configurazione logging
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG, INFO, WARNING, ERROR
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

---

## 📊 Flusso Dati - Esempio Completo

```
CICLO 1: Volto Ignoto Rilevato
├─ Sensori: "Vedo un volto ignoto"
├─ Stato: Nessun volto noto recentemente
├─ Corpo: Fermo il robot e guardo il volto
├─ Voce: "Non ti conosco. Come ti chiami?"
├─ Attesa: input_ricevuto = True
└─ Memoria: primo_ignoto_tempo = now

CICLO 2: Stabilità Verificata (dopo 2 secondi)
├─ Verifico: stabilità OK
├─ Voce: Stessa domanda
├─ Foto: Scatto immagine per archivio
└─ Stato: attesa_nome = True

CICLO 3-N: In Attesa Input Utente
├─ Loop fino a input_ricevuto = True
└─ Non elaboro LLM, attendo nome

CICLO N+1: Input Ricevuto "nome Marco"
├─ Estraggo nome: "Marco"
├─ Valido (>2 char): SÌ
├─ Vista: apprendi_volto("Marco")
├─ Voce: "Ti ho memorizzato, Marco!"
├─ Memoria: salva nome in fatti_importanti
├─ Stato: attesa_nome = False
└─ Movimento: Riprendi cammino se era in pattugliamento

CICLO N+2: Normale
├─ Sensori: Altro mondo
├─ LLM: Elabora decisione
├─ Azioni: Esegui
└─ Memoria: Aggiorna ricordi
```

---

## 🔐 Sicurezza e Limitazioni

### Gestione Emergenze (automatica)
- **Collisioni**: Ferma immediato se urto rilevato
- **Pericolo**: Posa difensiva se minaccia rilevata
- **Ostacoli**: Evita e agira intorno

### Limitazioni Attuali
- ⚠️ Un solo utente alla volta
- ⚠️ Riconoscimento volti limitato a 30-40 persone
- ⚠️ Memoria locale (no cloud sync)
- ⚠️ Velocità movimento fissa (0.3)

---

## 📚 Risorse Correlate

- [NAO SDK Documentation](https://developer.softbankrobotics.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/)
- [Progetto Core](./core/)
- [Moduli Comportamenti](./behaviors/)

---

## 🤝 Contributi

Per miglioramenti o bug fix:
1. Crea una branch feature: `git checkout -b feature/miglioria`
2. Commit: `git commit -m "Descrizione cambio"`
3. Push: `git push origin feature/miglioria`
4. Pull Request

---

## 📝 Note Tecniche

### Variabili Globali

| Variabile | Tipo | Descrizione |
|-----------|------|-------------|
| `messaggio_utente` | str | Ultimo input utente |
| `input_ricevuto` | bool | Flag nuovo input |
| `memoria_fisica` | dict | Memoria persistente |
| `stato_robot` | dict | Stato attuale robot |
| `stato_runtime` | dict | Flag runtime (volti salutati, pattuglia, etc) |
| `corpo_globale` | NaoBody | Riferimento corpo per helper functions |

### Type Hints

Il codice usa type hints Python per chiarezza:
```python
def gestisci_volto_durante_cammino(
    mondo: str, 
    corpo: NaoBody, 
    voce: NaoVoice, 
    vista: NaoVision
) -> bool:
    """Docstring con type hints"""
    pass
```

### Logging Strutturato

```python
logger.info(f"Volto riconosciuto: {nome}")           # Informazioni
logger.debug("Volto ancora instabile")               # Debug dettagliato
logger.warning("Elementi memoria non è lista")       # Avvertenze
logger.error(f"Errore: {e}", exc_info=True)         # Errori con traceback
```

---

## 📞 Supporto

Per problemi o domande:
- Controlla i log (attiva DEBUG_STATO)
- Verifica connessione IP robot
- Assicurati API key sia valida
- Consulta la documentazione NAO SDK

---

**Ultima Modifica**: 2024  
**Versione**: 2.0 (Rifattorizzata)  
**Stato**: Produzione
