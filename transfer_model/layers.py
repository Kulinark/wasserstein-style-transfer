import torch
from torch import nn

import utils


class StyleLayerKernel(nn.Module):
    def __init__(self, cnn_chunk, style_feats, kernel, k):
        super().__init__()

        self.conv = cnn_chunk
        batch_size, channels, height, width = style_feats.shape
        assert batch_size == 1

        style_feats = style_feats.view(channels, height * width).t()
        self.style_feats = torch.tanh(style_feats)
        assert style_feats.requires_grad == False

        self.kernel = kernel
        self.k = k

    def forward(self, inp):
        x, kernel_outs = inp
        feat_maps = self.conv(x)
        batch_size, channels, height, width = feat_maps.shape
        assert batch_size == 1

        cnn_feats = feat_maps.view(channels, height * width).t()
        cnn_feats = torch.tanh(cnn_feats)

        gen_sample, style_sample = utils.sample_k(cnn_feats, self.style_feats, k=self.k)
        kernel_out = self.kernel(gen_sample, style_sample)
        kernel_outs.append(kernel_out)
        return (feat_maps, kernel_outs)


class StyleLayerDisc(nn.Module):
    def __init__(self, cnn_chunk, out_c, k, h_dim=256):
        super().__init__()

        self.conv = cnn_chunk
        self.k = k

        # Discriminator
        self.disc = nn.Sequential(
            nn.Linear(out_c, h_dim),
            nn.ReLU(),
            nn.Linear(h_dim, h_dim),
            nn.ReLU(),
            nn.Linear(h_dim, 1),
        )

    def forward(self, inp):
        x, disc_outs = inp
        # Spatial features
        cnn_feats = self.conv(x)
        bsz, c, h, w = cnn_feats.size()

        # Discriminator
        disc_inp = torch.tanh(cnn_feats.view(c, -1).t())
        disc_inp = utils.sample_k(disc_inp, k=self.k)
        d = self.disc(disc_inp)
        disc_outs.append(torch.mean(d))

        return (cnn_feats, disc_outs)

    def disc_gp(self, x):
        with torch.no_grad():
            # Spatial features
            cnn_feats = self.conv(x)
            bsz, c, h, w = cnn_feats.size()

            # Discriminator
            disc_inp = torch.tanh(cnn_feats.view(c, -1).t())

        # Gradient Penalty
        gp = utils.calc_gradient_penalty(self.disc, disc_inp)

        return cnn_feats, gp

