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
Contiene i moduli che gestiscono gli eventi:
- eventi noti;
- eventi scoperti autonomamente;
- registro eventi;
- memoria di ricorrenza;
- simulazione prima della generazione reale.

## generated_conditions
Contiene le condizioni valide e promosse.

## quarantine_conditions
Contiene condizioni temporanee non ancora validate.

## rejected_conditions
Contiene condizioni rifiutate dal validatore.

## Flusso autonomo
Percezione → evento → firma situazione → ricerca condizione → simulazione → validazione → generazione → promozione → esecuzione → memoria → eventuale rifiuto/riparazione.