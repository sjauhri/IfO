#!/bin/bash
python3 models/tips_lunarlandercont.py --mode=train --input_file=demonstration/expert_obs/LunarLanderContinuous-v2.pkl --result_dir=results/tips/lunarlandercont/ --session_dir=session/tips/lunarlandercont/ --maxEpisodes=50 --numExperiments=1 --runAgent --learnFDM #--usePrevSession --prev_session_dir=prev_sessions/tips/lunarlandercont/