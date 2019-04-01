from models.encoders import *
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
import torch
import numpy as np
import torch.nn as nn

class DAMICClustering(nn.Module):
    """
        Clustering network for DAMIC
        Each cluster is reprensented by an autoencoder
        A convolutional network give us p(c=i|x:theta)
    """
    def __init__(self, n_clusters):
        super().__init__()
        self.n_clusters = n_clusters
        self.autoencoders = np.array([])
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        for i in range(n_clusters):
            encoding_model = CVAE(latent_dim=10).to(device)
            self.autoencoders = np.append(self.autoencoders, np.array([encoding_model]))
        self.clustering_network = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1),  # input is b, 3, 32, 32
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Conv2d(64, 64, kernel_size=4, stride=2, padding=1),  # input is b, 3, 32, 32
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Conv2d(64, 32, kernel_size=3, stride=1, padding=1),  # b, 32, 8,8
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=4, stride=2, padding=1),  # b, 32, 8,8
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Conv2d(32, 16, kernel_size=3, stride=1, padding=1),  # b, 16,4,4
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.Conv2d(16, 16, kernel_size=4, stride=2, padding=1),  # b, 16,4,4
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.Linear(16 * 4 * 4, 17),
            nn.Softmax()
        )
        
    def init_autoencoder(self, data, index):
        """ using data, we will train the auto encoder for cluster index """
        print("not implemented yet")
            
    def train(self, data):
        print("not implemented yet")
        """
        if type(data) is torch.Tensor:
            data = data.detach().cpu().numpy()
        self.kmeans.fit(data)
        return self.kmeans
        """

    def predict_cluster(self, data):
        # TODO : final hard clustering is made by ĉ = argmax p(c|x,theta) see p3
        print("not implemented yet")
        """
        if type(data) is torch.Tensor:
            data = data.detach().cpu().numpy()
        return self.kmeans.predict(data)
        """
    
    def forward(self, x):
        clustering_network_output = self.clustering_network(x)
        autoencoders_loss = np.array(self.n_clusters)
        for i in range(self.n_clusters):
            encoded_decoded_x = self.autoencoders[i](x)
            current_loss = self.loss_fct(encoded_decoded_x, x)
            autoencoders_loss[i] = np.exp(-current_loss)
        clustering_network_loss = np.exp(clustering_network_output) / np.sum(np.exp(clustering_network_output))
        encoder_and_network_loss = np.log(np.sum(clustering_network_loss * autoencoders_loss))
        return clustering_network_output, encoder_and_network_loss

    
class KMeansClustering:
    """clustering with K-means"""
    def __init__(self, n_clusters, seed):
        self.kmeans = KMeans(init="k-means++", n_clusters=n_clusters, n_init=5, max_iter=1000, random_state=seed,
                             n_jobs=-1)
        self.n_clusters = n_clusters

    def train(self, data):
        if type(data) is torch.Tensor:
            data = data.detach().cpu().numpy()
        self.kmeans.fit(data)
        return self.kmeans

    def predict_cluster(self, data):
        if type(data) is torch.Tensor:
            data = data.detach().cpu().numpy()
        return self.kmeans.predict(data)


class GMMClustering:
    """clustering with gaussian mixture model"""
    def __init__(self, n_clusters, seed):
        self.gmm = GaussianMixture(n_components=n_clusters, random_state=seed)
        self.n_clusters = n_clusters

    def train(self, data):
        if type(data) is torch.Tensor:
            data = data.detach().cpu().numpy()
        self.gmm.fit(data)
        return self.gmm

    def predict_cluster(self, data):
        if type(data) is torch.Tensor:
            data = data.detach().cpu().numpy()
        return self.gmm.predict(data)
