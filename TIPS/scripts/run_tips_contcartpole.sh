#!/bin/bash
python3 models/tips_contcartpole.py --mode=train --input_file=demonstration/expert_obs/CartPole-v0.pkl --result_dir=results/tips/contcartpole/ --model_dir=model/tips/contcartpole/ --maxEpochs=50 --numExperiments=1