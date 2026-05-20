#!/bin/bash

cd /data/home/nao/NAOTirocinio || exit 1

export NAO_IP=172.16.165.86
export NAO_AUTONOMOUS_LIFE=1
export CHOREGRAPHE_BOOT=1
export SKIP_AUTONOMOUS_LIFE_CONFIG=1
export OPENAI_API_KEY="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"

python start_nao_autonomo.py