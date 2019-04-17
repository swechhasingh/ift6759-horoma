#!/bin/bash

# PROJECT_PATH will be changed to the master branch of your repo. Make sure it contains `evaluation/eval.py`
PROJECT_PATH='/rap/jvb-000-aa/COURS2019/etudiants/submissions/b3phot5/code'

RESULTS_DIR='.'#'/rap/jvb-000-aa/COURS2019/etudiants/ift6759/projects/horoma/evaluation'
DATA_DIR='/rap/jvb-000-aa/COURS2019/etudiants/data/horoma/'

cd $PROJECT_PATH/evaluation
s_exec python eval.py --dataset_dir=$DATA_DIR --results_dir=$RESULTS_DIR