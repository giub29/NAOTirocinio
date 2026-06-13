#!/bin/bash

cd /data/home/nao/NAOTirocinio || exit 1

export NAO_IP=127.0.0.1
export NAO_AUTONOMOUS_LIFE=1
export CHOREGRAPHE_BOOT=1
export SKIP_AUTONOMOUS_LIFE_CONFIG=1
if [ -z "$OPENAI_API_KEY" ]; then
  echo "OPENAI_API_KEY non impostata: continuo senza generazione LLM remota."
fi

python start_nao_autonomo.py
