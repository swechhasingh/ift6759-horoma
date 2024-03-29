# IFT6759 Winter 2019
## Horoma Project Block 3

Authors:
Benjamin Rosa,
Swechha Swechha,
Timothy Nest


Project Organization
------------

    ├── configs           <- contains config files for the project
    ├── data              <- Datasets used accross the project
    ├── evaluation        <- contains eval.py 
    ├── models            <- all the models architecture
    ├── trainers          <- training scripts for all the models
    ├── utils             <- utilities used int the project
    ├── run.pbs           <- script for training on cluster
    └── README.md         <- The top-level README for developers using this project.

--------

## To run scripts

Add the following command in run.pbs for training
* TransformerNet model
```
s_exec python train_transformer_net.py
```
* CAE-SVM model
```
s_exec python svm_trainer.py
```
* CAE-MLP model
```
s_exec python semisupervised_trainer.py
```
* HALI model
```
s_exec python ali_train.py --config HALI
```
* ALI model
```
s_exec python ali_train.py --config ALI
```
* DAMIC model
```
s_exec python train_damic.py
```
* CVAE model
```
s_exec python train.py --config CVAE_BASE --encoder_path experiment_models/cvae_base.pth
```
* CONV_AE model
```
s_exec python train.py --config CONV_AE --encoder_path experiment_models/conv_ae.pth
```
* Neural Rendering Model
```
s_exec python train_nrm.py
```
--------

DAMIC Trainer Usage
------------

```
usage: trainers/train_damic.py [-h] [--datapath] [--config]

Start a training for a DAMIC model

optional arguments:
  -h, --help            show this help message and exit
  --datapath            which config to load within config.json (CONV_AE, DAMIC or CVAE_BASE)
                          default: Constants._DATAPATH
  --config              which config to load within config.json (CONV_AE, DAMIC or CVAE_BASE)
                          default: DAMIC
  -d DEVICE, --device DEVICE
                        indices of GPUs to enable (default: all)

```

Transformer Net Trainer Usage
------------
```
usage: trainers/train_transformer_net.py [-h] [--batch-size] [--eval-batch-size] [--iters] [--lr] [--momentum]
[--alpha] [--ema_decay] [--xi] [--eps] [--cr_type] [--ip] [--workers] [--seed] [--targets] [--data_dir]
[--checkpoint_dir] [--log-interval] [--chkpt-freq] [--no-entropy] [--reg-vat-var] 

Start a training for a Transformer Net model

optional arguments:
  -h, --help            show this help message and exit
  --batch-size          input batch size for training
                          default: 16
  --eval-batch-size     input batch size for evaluation
                          default: 8
  --iters               number of iterations to train
                          default: 10 000
  --lr                  learning rate
                          default: 0.001
  --momentum            SGD momentum
                          default: 0.9
  --alpha               regularization coefficient
                          default: 0.01
  --ema_decay           decay for exponential moving average
                          default: 0.999
  --xi                  hyperparameter of VAT
                          default: 5.0
  --eps                 hyperparameter of VAT
                          default: 1.0
  --workers             number of CPU
                          default: 8
  --seed                 random seed
                          default: 1
  --targets              list of targets to use for training
                          default: ['tree_class']
  --data_dir             directory where to find the data
                          default:"/rap/jvb-000-aa/COURS2019/etudiants/data/horoma"
  --checkpoint_dir       directory where to checkpoints the models
                          default:"./transformer_net_models/"
  --log-interval         how many batches to wait before logging training status
                          default: 10
  --chkpt-freq           how many batches to wait before performing checkpointing
                          default: 100
  --no-entropy           enables Entropy based regularization
                          default: False
  --reg-vat-var          Assumed variance of the predicted Gaussian for regression tasks
                          default: 0.1


```

ALI/HALI Usage
------------

```
usage: trainers/ali_train.py [-h] [--datapath] [--config]

To start training an ALI-based model, be sure to specify encode=true and cluster=false.

This will save models for each epoch of unlabeled training in the experiment folder.

To evaluate, specify encode=false and cluster=true.

optional arguments:
  -h, --help            show this help message and exit

  --config              which config to load within config.json (HALI, ALI)
                          default: DAMIC

```

## Github conventions
* Each feature must have his own branch for development
  * git checkout -b nameOfTheNewBranch
* When changes are made, push is only made to the feature's branch
  * git add .
  * git commit -m "Relevant message regarding the changes"
  * git checkout master
  * git pull --rebase
  * git checkout nameOfTheNewBranch
  * git merge master
  * Fix conflicts if there is any
  * git push origin nameOfTheNewBranch
* Once the changes in a personal branch are ready, do a pull request for the master branch
  * go to the github page of the project https://github.com/swechhachoudhary/ift6759-horoma
  * select your branch using the drop down button
  * click on create pull request
  * put master branch as the head
  * confirm the creation of the pull request
