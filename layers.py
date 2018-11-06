from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division

import torch.nn as nn


class Identity(nn.Module):

    def __init__(self):
        super(Identity, self).__init__()

    def forward(self, x):
        return x


class GatedConv2d(nn.Module):

    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1, dilation=1,
                 activation=None, local_condition=False, condition_channels=1):
        super().__init__()

        self.activation = activation
        self.sigmoid = nn.Sigmoid()

        self.local_condition = local_condition

        if not local_condition:
            self.conv_features = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, dilation)
            self.conv_gate = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, dilation)
        else:
            # Because the conditioning data needs to be incorporated into the bias, bias is set to false
            self.conv_features = nn.Conv2d(in_channels, out_channels, kernel_size, stride,
                                           padding, dilation, bias=False)
            self.conv_gate = nn.Conv2d(in_channels, out_channels, kernel_size, stride,
                                       padding, dilation, bias=False)
            self.cond_features = nn.Conv1d(condition_channels, out_channels, kernel_size=1, bias=False)
            self.cond_gate = nn.Conv1d(condition_channels, out_channels, kernel_size=1, bias=False)

    def forward(self, x, c=None):
        """
        hi = σ(Wg,i ∗ xi + V^T g,ic) * activation(Wf,i ∗ xi + V^Tf,ic)
        Args:
            x: input tensor, [B, C, H, W]
            c: extra conditioning data.  Must be a 3D-tensor.
            In cases where c encodes spatial or sequential information (such as a sequence of linguistic features),
             the matrix products are replaced with convolutions.

        Returns:
            layer activations, hi
        """
        features = self.conv_features(x)
        gate = self.conv_gate(x)

        if self.local_condition:
            # features += self.cond_features(c)
            features += self.cond_features(c)[..., None].expand_as(features)
            gate += self.cond_gate(c)[..., None].expand_as(gate)

        if self.activation is not None:
            features = self.activation(features)

        gate = self.sigmoid(gate)

        return features * gate


class GatedConvTranspose2d(nn.Module):

    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1, output_padding=0, dilation=1,
                 activation=None, local_condition=False, condition_channels=1):
        super().__init__()

        self.activation = activation
        self.sigmoid = nn.Sigmoid()

        self.local_condition = local_condition

        if not local_condition:
            self.conv_features = nn.ConvTranspose2d(in_channels, out_channels, kernel_size, stride,
                                                    padding, output_padding, dilation=dilation)
            self.conv_gate = nn.ConvTranspose2d(in_channels, out_channels, kernel_size, stride,
                                                padding, output_padding, dilation=dilation)
        else:
            # Because the conditioning data is incorporated into the bias, bias is set to false
            self.conv_features = nn.ConvTranspose2d(in_channels, out_channels, kernel_size, stride,
                                                    padding, output_padding, dilation=dilation, bias=False)
            self.conv_gate = nn.ConvTranspose2d(in_channels, out_channels, kernel_size, stride,
                                                padding, output_padding, dilation=dilation, bias=False)
            self.cond_features = nn.Conv1d(condition_channels, out_channels, kernel_size=1, bias=False)
            self.cond_gate = nn.Conv1d(condition_channels, out_channels, kernel_size=1, bias=False)

    def forward(self, x, c=None):
        """
        hi = σ(Wg,i ∗ xi + V^T g,ic) * activation(Wf,i ∗ xi + V^Tf,ic)
        Args:
            x: input tensor, [B, C, H, W]
            c: extra conditioning data.  Must be a 3D-tensor.
            In cases where c encodes spatial or sequential information (such as a sequence of linguistic features),
             the matrix products are replaced with convolutions.

        Returns:
            layer activations, hi
        """
        features = self.conv_features(x)
        gate = self.conv_gate(x)

        if self.local_condition:
            features += self.cond_features(c)[..., None].expand_as(features)
            gate += self.cond_gate(c)[..., None].expand_as(gate)

        if self.activation is not None:
            features = self.activation(features)

        gate = self.sigmoid(gate)

        return features * gate


class ResidualBLock(nn.Module):

    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1,
                 dilation=(1, 1), residual=True):
        super().__init__()

        conv1_padding = padding * dilation[0]    # ensure the dilation does not affect the output size
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size,
                               stride=stride, padding=conv1_padding, dilation=dilation[0])
        self.bn1 = nn.BatchNorm2d(out_channels)

        conv2_padding = padding * dilation[1]
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=kernel_size,
                               stride=stride, padding=conv2_padding, dilation=dilation[1])
        self.bn2 = nn.BatchNorm2d(out_channels)

        self.relu = nn.ReLU()

        self.downsample = None
        if stride != 1 or in_channels != out_channels:
            self.downsample = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, stride),
                nn.BatchNorm2d(out_channels)
            )

        self.stride = stride
        self.residual = residual

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(residual)

        if self.residual:
            out += residual
        out = self.relu(out)

        return out


class GatedResidualBLock(nn.Module):

    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1,
                 dilation=(1, 1), residual=True, activation=None, local_condition=False,
                 condition_channels=1):
        super().__init__()

        conv1_padding = padding * dilation[0]    # ensure the dilation does not affect the output size
        self.conv1 = GatedConv2d(in_channels, out_channels, kernel_size=kernel_size,
                                 stride=stride, padding=conv1_padding, dilation=dilation[0],
                                 activation=activation, local_condition=local_condition,
                                 condition_channels=condition_channels)

        self.bn1 = nn.BatchNorm2d(out_channels)

        conv2_padding = padding * dilation[1]
        self.conv2 = GatedConv2d(out_channels, out_channels, kernel_size=kernel_size,
                                 stride=stride, padding=conv2_padding, dilation=dilation[1],
                                 activation=activation, local_condition=local_condition,
                                 condition_channels=condition_channels)
        self.bn2 = nn.BatchNorm2d(out_channels)
        
        self.relu = nn.ReLU()

        self.downsample = None
        if stride != 1 or in_channels != out_channels:
            self.downsample = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, stride),
                nn.BatchNorm2d(out_channels)
            )

        self.stride = stride
        self.residual = residual

    def forward(self, x, c=None):
        residual = x

        out = self.conv1(x, c)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out, c)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(residual)

        if self.residual:
            out += residual
        out = self.relu(out)

        return out


class ConditionalBatchNorm2d(nn.Module):

    def __init__(self, num_features, num_classes):
        super().__init__()
        self.num_features = num_features
        self.bn = nn.BatchNorm2d(num_features, affine=False)
        self.embed = nn.Embedding(num_classes, num_features * 2)
        self.embed.weight.data[:, :num_features].normal_(1, 0.02)  # Initialise scale at N(1, 0.02)
        self.embed.weight.data[:, num_features:].zero_()    # Initialise bias at 0

    def forward(self, x, y):
        out = self.bn(x)
        gamma, beta = self.embed(y).chunk(2, 1)
        out = gamma.view(-1, self.num_features, 1, 1) * out + beta.view(-1, self.num_features, 1, 1)

        return out