# Sistema autonomo NAO

## condition_system
Contiene i moduli che gestiscono le condizioni:
- generazione tramite LLM;
- validazione;
- promozione;
- rifiuto;
- memoria;
- riparazione.

## event_system
Contiene i moduli che gestiscono gli eventi e il modello del mondo:
- eventi noti;
- eventi scoperti autonomamente;
- registro eventi;
- memoria di ricorrenza;
- simulazione prima della generazione reale.

### world_model_memory.py
Mantiene un modello persistente del mondo che trasforma osservazioni ripetute in credenze stabili. Per ogni entità osservata (oggetto, spazio, dispositivo):
- conta le osservazioni dello stato per stabilire il "normale" (stato_normale);
- registra lo stato corrente e calcola il livello di fiducia;
- rileva anomalie quando lo stato corrente diverge significativamente dal normale;
- mantiene evidenze recenti e feedback da osservazioni mirate;
- supporta "active perception" per confermare o smentire variazioni sospette.

Le credenze sono salvate in `world_model_memory.json` e non interferiscono con il generatore di condizioni, che rimane libero di decidere cosa fare con le anomalie rilevate.

### active_perception_planner.py
Pianifica osservazioni mirate per validare ipotesi di variazione nel mondo. Quando un'anomalia viene rilevata, la percezione mirata verifica se la variazione è reale o temporanea prima di considerarla degna di attenzione del sistema autonomo.

## generated_conditions
Contiene le condizioni valide e promosse.

## quarantine_conditions
Contiene condizioni temporanee non ancora validate.

## rejected_conditions
Contiene condizioni rifiutate dal validatore.

## Flusso autonomo
Percezione → evento → firma situazione → [world model aggiorna credenze] → ricerca condizione → simulazione → validazione → generazione → promozione → esecuzione → memoria → eventuale rifiuto/riparazione.