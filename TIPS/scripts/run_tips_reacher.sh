#!/bin/bash
python3 models/tips_reacher.py --mode=train --input_file=demonstration/expert_obs/Reacher-v2.pkl --result_dir=results/tips/reacher/ --session_dir=session/tips/reacher/ --maxEpochs=50 --numExperiments=1
