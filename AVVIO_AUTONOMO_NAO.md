# Avvio autonomo NAO

## Obiettivo

Rendere il robot NAO indipendente dall'avvio manuale del progetto da VS Code.

Il sistema deve poter seguire questa catena:

```text
Accensione PC
   ↓
Avvio automatico server PC
   ↓
Accensione NAO
   ↓
autoload.ini avvia autonomous_bootstrap.py
   ↓
NAO contatta il server PC
   ↓
Il server verifica che NAO sia raggiungibile
   ↓
Il server avvia autonomous_watchdog.py
   ↓
Il watchdog avvia soul.py
   ↓
Il sistema autonomo resta attivo