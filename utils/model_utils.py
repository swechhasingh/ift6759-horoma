import numpy as np
from torch.utils.data import DataLoader, SubsetRandomSampler
from copy import deepcopy
import torch.nn.functional as F
import torch.nn as nn
import torch
from utils.utils import __compute_metrics


def get_ae_dataloaders(traindata, batch_size, split):
    """get dataloaders for train and valid sets"""
    indices = list(range(len(traindata)))
    np.random.shuffle(indices)
    n_train = int(split * len(indices))
    train_loader = DataLoader(traindata, batch_size=batch_size, sampler=SubsetRandomSampler(indices[:n_train]))
    valid_loader = DataLoader(traindata, batch_size=batch_size, sampler=SubsetRandomSampler(indices[n_train:]))

    return train_loader, valid_loader


def get_cae_dataloaders(traindata, valid_data, batch_size):
    """get dataloaders for train and valid sets"""
    train_loader = DataLoader(traindata, batch_size=batch_size, shuffle=True)
    valid_loader = DataLoader(valid_data, batch_size=batch_size)
    return train_loader, valid_loader


def loss_function(recon_x, x, mu, logvar):
    MSE = F.mse_loss(recon_x.view(-1, 32 * 32 * 3),
                     x.view(-1, 32 * 32 * 3), reduction='sum')

    # see Appendix B from VAE paper:
    # Kingma and Welling. Auto-Encoding Variational Bayes. ICLR, 2014
    # https://arxiv.org/abs/1312.6114
    # 0.5 * sum(1 + log(sigma^2) - mu^2 - sigma^2)
    KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    return MSE + KLD


def encode_dataset(model, data, batch_size, device, is_unlabeled=True):
    """encode data using model (model must provide an encode function)"""

    full_loader = DataLoader(data, batch_size=batch_size)
    tensors = []
    with torch.no_grad():
        if is_unlabeled:
            for batch_idx, inputs in enumerate(full_loader):
                if isinstance(inputs, (tuple, list)):
                    inputs = inputs[0]
                inputs = inputs.to(device)
                tensors.append(model.encode(inputs))
        else:
            for batch_idx, (inputs, labels) in enumerate(full_loader):
                inputs = inputs.to(device)
                tensors.append(model.encode(inputs))

    return torch.cat(tensors, dim=0)


def _train_one_epoch(model, train_loader, optimizer, epoch, device, experiment):
    """
    Train one epoch for the model

    :param model: model on which we do the training
    :param train_loader: dataloader
    :param optimizer: optimizer
    :param epoch: number of epoch
    :param device: cpu or cuda
    :param experiment: comet experiment to log results
    :return: loss for this epoch
    """
    model.train()

    running_loss = 0.0

    for batch_idx, inputs in enumerate(train_loader):
        if isinstance(inputs, (tuple, list)):
            inputs = inputs[0]
        inputs = inputs.to(device)
        optimizer.zero_grad()
        if model.is_variational:
            pred, mu, logvar = model(inputs)
            if model.calculate_own_loss:
                loss = mu
            else:
                loss = loss_function(pred, inputs, mu, logvar)
        else:
            outputs = model(inputs)
            criterion = nn.MSELoss(reduction='sum')
            loss = criterion(outputs, inputs)
        loss.backward()
        optimizer.step()
        running_loss += loss.item()
        if batch_idx % 10 == 0:
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(epoch, batch_idx * len(inputs),
                                                                           len(train_loader) *
                                                                           len(inputs),
                                                                           100. * batch_idx /
                                                                           len(train_loader),
                                                                           loss.item() / len(inputs)))

    train_loss = running_loss / len(train_loader.dataset)
    experiment.log_metric("Train loss", train_loss, step=epoch)
    return train_loss


def _train_one_epoch_classifier(model, train_loader, optimizer, epoch, device, experiment):
    """
    Train one epoch for a model of type classifier

    :param model: model on which we do the training
    :param train_loader: dataloader
    :param optimizer: optimizer
    :param epoch: number of epoch
    :param device: cpu or cuda
    :param experiment: comet experiment to log results
    :return: loss for this epoch
    """
    model.train()
    running_loss = 0.0

    for batch_idx, data in enumerate(train_loader):
        inputs, labels = data
        labels = labels.long()
        labels = labels.squeeze()

        inputs = inputs.to(device)
        labels = labels.to(device)
        labels[labels < 0] = 0
        labels[labels > 16] = 16

        optimizer.zero_grad()
        outputs = model(inputs)
        criterion = nn.CrossEntropyLoss()
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        if batch_idx % 10 == 0:
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(epoch, batch_idx * len(inputs),
                                                                           len(train_loader) * len(inputs),
                                                                           100. * batch_idx / len(train_loader),
                                                                           loss.item() / len(inputs)))
    model.status = "Conv net pretrain done"
    train_loss = running_loss / len(train_loader)
    experiment.log_metric("Conv classifier pretrain loss", train_loss, step=epoch)
    return train_loss


def _train_one_epoch_damic(model, train_loader, optimizer, epoch, device, experiment):
    """
    Train one epoch for a Damic model

    :param model: model on which we do the training
    :param train_loader: dataloader
    :param optimizer: optimizer
    :param epoch: number of epoch
    :param device: cpu or cuda
    :param experiment: comet experiment to log results
    :return: loss for this epoch
    """
    model.train()
    running_loss = 0.0
    print("====== TRAINING DAMIC")
    for batch_idx, data in enumerate(train_loader):
        inputs, _ = data
        current_batch_size = inputs.shape[0]
        inputs = inputs.to(device)

        optimizer.zero_grad()

        conv_net_class_predictions, ae_reconstruction = model.train_damic(inputs, current_batch_size)
        criterion_ae = nn.MSELoss()

        loss_autoencoders = torch.FloatTensor(17, len(inputs)).zero_().to(device)
        for i in range(17):
            loss_autoencoder = criterion_ae(inputs, ae_reconstruction[i].to(device))
            loss_autoencoders[i] = -(loss_autoencoder / 2.0)

        loss_autoencoders = loss_autoencoders.transpose(0, 1)

        # Calculate loss given the formula (3) p2 from 'Deep clustering based on a mixture of autoencoders paper'
        exp_loss_autoencoders = loss_autoencoders.exp()
        total_loss_per_class = conv_net_class_predictions * exp_loss_autoencoders
        total_loss = total_loss_per_class.sum(dim=1)
        total_loss_log = total_loss.log()
        total_loss_log_sum = total_loss_log.sum()

        # Simultaneously train all the autoencoders and the convolutional network
        total_loss_log_sum.backward()
        optimizer.step()

        running_loss += total_loss_log_sum.item()

    train_loss = running_loss / len(train_loader)
    experiment.log_metric("DAMIC train loss", train_loss, step=epoch)
    return train_loss


def _test(model, test_loader, epoch, device, experiment):
    """ Compute reconstruction loss of model over given dataset. Model is an autoencoder"""

    test_loss = 0
    test_size = 0

    with torch.no_grad():
        for inputs in test_loader:
            if isinstance(inputs, (tuple, list)):
                inputs = inputs[0]

            inputs = inputs.to(device)
            # ConvAe is variational
            if model.is_variational:
                output, mu, logvar = model(inputs)
                if model.calculate_own_loss:
                    test_loss += mu
                else:
                    test_loss += loss_function(output,
                                               inputs, mu, logvar).item()
                test_size += len(inputs)
            else:
                output = model(inputs)
                criterion = nn.MSELoss(reduction='sum')
                test_loss += criterion(output, inputs).item()
                test_size += len(inputs)

    test_loss /= test_size
    experiment.log_metric("Validation loss", test_loss, step=epoch)
    return test_loss


def _test_classifier(model, test_loader, epoch, device, experiment):
    """ Compute cross entropy loss over given test_loader """

    test_loss = 0
    test_size = 0

    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs = inputs.to(device)
            labels = labels.long()
            labels = labels.squeeze()
            labels = labels.to(device)
            outputs = model(inputs)
            criterion = nn.CrossEntropyLoss()
            test_loss += criterion(outputs, labels).item()
            test_size += len(inputs)

    test_loss /= test_size
    experiment.log_metric("Conv classifier pretrain validation loss", test_loss, step=epoch)
    return test_loss


def train_network(model, train_loader, test_loader, optimizer, n_epochs, device, experiment, train_classifier=False, train_damic=False,
                  folder_save_model="../experiment_models/", pth_filename_save_model=""):
    """
    Train a network

    :param model: model on which we do the training
    :param train_loader: dataloader with training samples
    :param test_loader: dataloader with test samples
    :param optimizer: optimizer
    :param n_epochs: number of epoch
    :param device: cpu or cuda
    :param experiment: comet experiment to log results
    :param train_classifier: if True we train a classifier
    :param train_classifier: if True we train a Damic model
    :param experiment: comet experiment to log results
    :param folder_save_model: folder where to save the best model
    :param pth_filename_save_model: name of the pth file for the best model
    :return: best model after the training
    """
    best_loss = np.inf
    key = experiment.get_key()
    best_model = None

    for epoch in range(n_epochs):
        if train_damic:
            train_loss = _train_one_epoch_damic(model, train_loader, optimizer, epoch, device, experiment)
            valid_loss = _test_classifier(model, test_loader, epoch, device, experiment)
        elif train_classifier:
            train_loss = _train_one_epoch_classifier(model, train_loader, optimizer, epoch, device, experiment)
            valid_loss = _test_classifier(model, test_loader, epoch, device, experiment)
        else:
            train_loss = _train_one_epoch(model, train_loader, optimizer, epoch, device, experiment)
            valid_loss = _test(model, test_loader, epoch, device, experiment)

        try:
            if valid_loss < best_loss:
                if pth_filename_save_model == "":
                    pth_filename = folder_save_model + str(key) + '.pth'
                else:
                    pth_filename = folder_save_model + pth_filename_save_model + '.pth'
                torch.save({
                    "epoch": epoch,
                    "optimizer": optimizer.state_dict(),
                    "model": model.state_dict(),
                    "loss": valid_loss
                }, pth_filename)
                best_loss = valid_loss
                best_model = deepcopy(model)  # Keep best model thus far
        except FileNotFoundError as e:
            print(
                "Directory for logging experiments does not exist. Launch script from repository root.")
            raise e

        print("Training loss after {} epochs: {:.6f}".format(epoch, train_loss))
        print("Validation loss after {} epochs: {:.6f}".format(epoch, valid_loss))

    # Return best model
    return best_model


def loop_over_unlabeled_data(data, batch_size):
    """Infiinte dataloader for unlabeled data"""
    data_loader = DataLoader(data, batch_size=batch_size, shuffle=True)
    while True:
        for batch in iter(data_loader):
            yield batch


def loop_over_labeled_data(data, batch_size):
    """Infiinte dataloader for labeled data"""
    data_loader = DataLoader(data, batch_size=batch_size, shuffle=True)
    while True:
        for batch in iter(data_loader):
            yield batch


def _train_one_epoch_unlabeled(model, train_data, optimizer, batch_size, n_unlabeled_batch, epoch, device, experiment):
    """Train one epoch of unlabeled data.
    :param model: CAE model
    :param train_data: train dataset
    :param optimizer: unsupervised optimizer
    :param batch_size: batch size
    :param n_unlabeled_batch: number of unlabeled batches
    :param epoch: epoch number
    :param device: device
    :param experiment: cometml experiment
    """
    model.train()

    running_loss = 0.0
    criterion = nn.MSELoss(reduction='sum')
    n_total = 0.0

    for batch_idx, inputs in enumerate(loop_over_unlabeled_data(train_data, batch_size)):

        if batch_idx < n_unlabeled_batch:
            inputs = inputs.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, inputs)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            n_total += len(inputs)
            if batch_idx % 10 == 0:
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(epoch, batch_idx,
                                                                               n_unlabeled_batch,
                                                                               100. * batch_idx /
                                                                               n_unlabeled_batch,
                                                                               loss.item() / len(inputs)))
        else:
            break
    train_loss = running_loss / n_total
    experiment.log_metric("Autoencoder train loss", train_loss, step=epoch)
    print("Autoencoder Training loss after {} epochs: {:.6f}".format(epoch, train_loss))
    return model


def _train_one_epoch_labeled(encoding_model, classifier_model, train_data, optimizer, batch_size, n_labeled_batch, epoch, device, experiment):
    """Train one epoch of labeled data.
    :param encoding_model: CAE model
    :param classifier_model: MLP model
    :param train_data: train dataset
    :param optimizer: unsupervised optimizer
    :param batch_size: batch size
    :param n_labeled_batch: number of labeled batches
    :param epoch: epoch number
    :param device: device
    :param experiment: cometml experiment
    """
    encoding_model.train()
    classifier_model.train()

    running_loss = 0.0
    criterion = nn.CrossEntropyLoss(reduction="sum")
    n_total = 0.0

    pred_labels = []
    true_labels = []

    for batch_idx, (inputs, targets) in enumerate(loop_over_labeled_data(train_data, batch_size)):

        if batch_idx < n_labeled_batch:
            inputs = inputs.to(device)
            targets = targets.squeeze().to(device).long()

            optimizer.zero_grad()
            # encode the inputs
            inp_encodings = encoding_model.encode(inputs)
            outputs = classifier_model(inp_encodings)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            true_labels.append(targets)
            pred_labels.append(torch.argmax(outputs, dim=1))
            running_loss += loss.item()
            n_total += len(inputs)
            if batch_idx % 10 == 0:
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(epoch, batch_idx,
                                                                               n_labeled_batch,
                                                                               100. * batch_idx /
                                                                               n_labeled_batch,
                                                                               loss.item() / len(inputs)))
        else:
            break
    train_loss = running_loss / n_total

    true_labels = torch.cat(true_labels, dim=0).cpu().detach().numpy()
    pred_labels = torch.cat(pred_labels, dim=0).cpu().detach().numpy()

    train_accuracy, train_f1, __train_f1 = __compute_metrics(
        true_labels, pred_labels)

    experiment.log_metric("Classifier train loss", train_loss, step=epoch)
    experiment.log_metric('Train accuracy', train_accuracy, step=epoch)
    experiment.log_metric('Train f1-score', train_f1, step=epoch)
    print("Classifier Train loss after {} epochs: {:.6f}".format(epoch, train_loss))
    print("Epoch {}: Supervised Train accuracy {:.3f}| f1-score {:.3f}".format(epoch, train_accuracy, train_f1))
    return encoding_model, classifier_model, train_accuracy, train_f1


def _test_semisupervised(encoding_model, classifier_model, test_loader, epoch, device, experiment):
    """ Validation of semisupervised task
    :param encoding_model: CAE model
    :param classifier_model: MLP model
    :param test_loader: test data loader
    :param epoch: epoch number
    :param device: device
    :param experiment: cometml experiment
    """
    encoding_model.eval()
    classifier_model.eval()

    test_unsup_loss = 0.0
    test_sup_loss = 0.0

    unsup_criterion = nn.MSELoss(reduction='sum')
    classification_criterion = nn.CrossEntropyLoss(reduction="sum")

    pred_labels = []
    true_labels = []

    with torch.no_grad():
        for batch_idx, (inputs, targets) in enumerate(test_loader):
            inputs = inputs.to(device)
            targets = targets.squeeze().to(device).long()
            out_decoder = encoding_model(inputs)
            # encoder ouput (latent representation)
            inp_encodings = encoding_model.encode(inputs)
            pred_targets = classifier_model(inp_encodings)

            test_unsup_loss += unsup_criterion(out_decoder, inputs).item()
            test_sup_loss += classification_criterion(pred_targets, targets).item()

            true_labels.append(targets)
            pred_labels.append(torch.argmax(pred_targets, dim=1))

    test_unsup_loss /= len(test_loader.dataset)
    test_sup_loss /= len(test_loader.dataset)

    true_labels = torch.cat(true_labels, dim=0).cpu().detach().numpy()
    pred_labels = torch.cat(pred_labels, dim=0).cpu().detach().numpy()

    valid_accuracy, valid_f1, __valid_f1 = __compute_metrics(
        true_labels, pred_labels)

    experiment.log_metric("Autoencoder Validation loss", test_unsup_loss, step=epoch)
    experiment.log_metric("Supervised Validation loss", test_sup_loss, step=epoch)

    experiment.log_metric('Validation accuracy', valid_accuracy, step=epoch)
    experiment.log_metric('Validation f1-score', valid_f1, step=epoch)

    print("Supervised Validation loss after {} epochs: {:.6f}".format(epoch, test_sup_loss))
    print("Epoch {}: Supervised Validation accuracy {:.3f}| f1-score {:.3f}".format(epoch, valid_accuracy, valid_f1))

    return true_labels, pred_labels, valid_accuracy, valid_f1


def train_semi_supervised_network(encoding_model, classifier_model, train_unlab_data, train_lab_data, valid_loader,
                                  n_epochs, batch_size, lr_unsup, lr_sup, device, n_labeled_batch, n_unlabeled_batch, patience, experiment):
    """Training of semisupervised task
    :param encoding_model: CAE model
    :param classifier_model: MLP model
    :param train_unlab_data: unlabeled train dataset
    :param train_lab_data: labeled train dataset
    :param valid_loader: validation set loader
    :param lr_unsup: unsupervised learning rate
    :param lr_sup: supervised learning rate
    :param batch_size: batch size
    :param n_labeled_batch: number of labeled batches
    :param n_unlabeled_batch: number of unlabeled batches
    :param n_epochs: no. of epochs
    :param patience: patience for early stopping
    :param device: device
    :param experiment: cometml experiment
    """
    best_acc = 0.0
    best_f1 = 0.0
    k = 0
    key = experiment.get_key()

    lr_unsup_encoder = lr_unsup * (len(train_lab_data) / len(train_unlab_data))
    param_unsup = [
        {'params': encoding_model.encoder.parameters(), 'lr': lr_unsup},
        {'params': encoding_model.embedding.parameters(), 'lr': lr_unsup},
        {'params': encoding_model.decode_embedding.parameters(), 'lr': lr_unsup},
        {'params': encoding_model.decoder.parameters(), 'lr': lr_unsup}
    ]
    param_sup = [
        {'params': encoding_model.encoder.parameters(), 'lr': lr_sup},
        {'params': encoding_model.embedding.parameters(), 'lr': lr_sup},
        {'params': classifier_model.parameters(), 'lr': lr_sup}
    ]

    optimizer_unsupervised = torch.optim.Adam(param_unsup, lr=lr_unsup)

    optimizer_supervised = torch.optim.Adam(param_sup)

    unsup_scheduler = torch.optim.lr_scheduler.StepLR(optimizer_unsupervised, step_size=10, gamma=0.5)
    sup_scheduler = torch.optim.lr_scheduler.StepLR(optimizer_supervised, step_size=10, gamma=0.5)
    for epoch in range(n_epochs):
        unsup_scheduler.step()
        sup_scheduler.step()

        encoding_model = _train_one_epoch_unlabeled(encoding_model, train_unlab_data, optimizer_unsupervised,
                                                    batch_size, n_unlabeled_batch, epoch, device, experiment)

        encoding_model, classifier_model, train_accuracy, train_f1 = _train_one_epoch_labeled(encoding_model, classifier_model, train_lab_data,
                                                                                              optimizer_supervised, batch_size, n_labeled_batch,
                                                                                              epoch, device, experiment)

        valid_true_labels, valid_pred_labels, valid_accuracy, valid_f1 = _test_semisupervised(encoding_model, classifier_model,
                                                                                              valid_loader, epoch, device, experiment)

        try:
            # if valid_accuracy > best_acc and valid_f1 > best_f1:
            if valid_f1 > best_f1:
                best_acc = valid_accuracy
                best_f1 = valid_f1
                k = 0
                print("Saving best model....")
                torch.save({
                    "epoch": epoch,
                    "unsup_optimizer": optimizer_unsupervised.state_dict(),
                    "sup_optimizer": optimizer_supervised.state_dict(),
                    "encode_model": encoding_model.state_dict(),
                    "sup_model": classifier_model.state_dict(),
                    "best_acc": valid_accuracy,
                    "best_f1": valid_f1,
                    "train_acc": train_accuracy,
                    "train_f1": train_f1,
                }, "../experiment_models/" + str(key) + '.pth')

                # plot_confusion_matrix(valid_true_labels, valid_pred_labels, classes=np.arange(17),
                #                       title='Confusion matrix for Validation')
            elif k < patience:
                k += 1
            else:
                print("Early stopping......")
                break
        except FileNotFoundError as e:
            print(
                "Directory for logging experiments does not exist. Launch script from repository root.")
            raise e
