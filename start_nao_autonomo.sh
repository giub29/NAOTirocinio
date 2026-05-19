#!/bin/bash

cd /home/nao/NAOTirocinio || exit 1

export NAO_IP=172.16.165.86
export NAO_AUTONOMOUS_LIFE=1
export CHOREGRAPHE_BOOT=1
export SKIP_AUTONOMOUS_LIFE_CONFIG=1

python start_nao_autonomo.py