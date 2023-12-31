# Import Statements:
import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import os
import h5py
import random
import shutil
import PIL
import imageio
import tensorflow.keras.backend as K
from pathlib import Path
from PIL import Image
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras import Model
from tensorflow.keras.layers import Dense, Flatten, Conv2D, MaxPooling2D, Add, Input, Dropout
from tensorflow.keras.layers import BatchNormalization, UpSampling2D, Concatenate, Conv2DTranspose, Activation

###################################################################################################
'''
MODEL DEFINITION:
Modified UNet
'''
# Inspired by https://www.tandfonline.com/doi/full/10.1080/17415977.2018.1518444?af=R and
# https://arxiv.org/ftp/arxiv/papers/1808/1808.10848.pdf
def FD_UNet(input, filters = 32, kernel_size = 3, padding = 'same',
            activation = 'relu', kernel_initializer = 'glorot_normal', prob=0.05):
    shortcut1_1 = input
    out = Conv2D_BatchNorm(input, filters, kernel_size=kernel_size, strides=1, padding=padding,
                           activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    [out, shortcut1_2] = DownBlock(out, filters*2, kernel_size, padding, activation, kernel_initializer, prob)
    [out, shortcut2_1] = DownBlock(out, filters*2*2, kernel_size, padding, activation, kernel_initializer, prob)
    [out, shortcut3_1] = DownBlock(out, filters*2*2*2, kernel_size, padding, activation, kernel_initializer, prob)
    [out, shortcut4_1] = DownBlock(out, filters*2*2*2*2, kernel_size, padding, activation, kernel_initializer, prob)


    out = BridgeBlock(out, filters*2*2*2*2*2, kernel_size, padding, activation, kernel_initializer, prob)

    out = Concatenate()([out, shortcut4_1])
    out = UpBlock(out, filters*2*2*2*2, kernel_size, padding, activation, kernel_initializer, prob)
    out = Concatenate()([out, shortcut3_1])
    out = UpBlock(out, filters*2*2*2, kernel_size, padding, activation, kernel_initializer, prob)
    out = Concatenate()([out, shortcut2_1])
    out = UpBlock(out, filters*2*2, kernel_size, padding, activation, kernel_initializer, prob)
    out = Concatenate()([out, shortcut1_2])

    out = Conv2D_BatchNorm(out, filters, kernel_size=kernel_size, strides=1, padding=padding,
                           activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    out = FD_Block(out, f_in=filters, f_out=filters*2, k=filters//4, kernel_size=kernel_size, padding=padding,
                   activation=activation, kernel_initializer=kernel_initializer, prob=prob)

    # 1x1 Convolution Followed by Identity as Activation:
    out = Conv2D_BatchNorm(out, filters=1, kernel_size=1, strides=1, padding=padding,
                           activation='linear', kernel_initializer=kernel_initializer)
    out = Add()([out, shortcut1_1])
    return out

def DownBlock(input, filters, kernel_size, padding, activation, kernel_initializer, prob):
    #print('DOWN_in: '+str(input.shape))
    ############################################
    # Modified UNet - FD Bridge Block:
    out = FD_Block(input, f_in=filters//2, f_out=filters, k=filters//8, kernel_size=kernel_size, padding=padding,
                   activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    shortcut = out
    out = DownSample(out, filters, kernel_size, strides=2, padding=padding,
                     activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    ############################################
    #print('DOWN_out: '+str(out.shape))
    return [out, shortcut]
def BridgeBlock(input, filters, kernel_size, padding, activation, kernel_initializer, prob):
    #print('Bridge_in: '+str(input.shape))
    #print(filters)
    ############################################
    # Modified UNet - FD Bridge Block:
    out = FD_Block(input, f_in=filters//2, f_out=filters, k=filters//8, kernel_size=kernel_size, padding=padding,
                   activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    out = UpSample(out, filters//2, kernel_size, strides=2,padding=padding,
                   activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    ############################################
    #print('Bridge_out: '+str(out.shape))
    return out
def UpBlock(input, filters, kernel_size, padding, activation, kernel_initializer, prob):
    #print('UP_in: '+str(input.shape))
    #print(filters)
    ############################################
    # Modified UNet - FD Up Block:
    out = Conv2D_BatchNorm(input, filters=filters//2, kernel_size=1, padding=padding,
                           activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    out = FD_Block(out, f_in=filters//2, f_out=filters, k=filters//8, kernel_size=kernel_size, padding=padding,
                   activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    out = UpSample(out, filters//2, kernel_size, strides=2,padding=padding,
                   activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    ############################################
    #print('UP_out: '+str(out.shape))
    return out
###################################################################################################
'''
MODEL FUNCTIONS:
'''
def Conv2D_BatchNorm(input, filters, kernel_size=3, strides=1, padding='same',
                     activation='linear', kernel_initializer='glorot_normal', prob=0.0):
    out = Conv2D(filters=filters, kernel_size=kernel_size,
                 strides=strides, padding=padding,
                 activation='linear',
                 kernel_initializer=kernel_initializer)(input)
    out = Activation(activation)(out)
    out = tf.keras.layers.SpatialDropout2D(prob)(out)
    out = BatchNormalization(axis=-1, momentum=0.99, epsilon=0.001, center=True,
                             scale=True, beta_initializer='zeros', gamma_initializer='ones',
                             moving_mean_initializer='zeros', moving_variance_initializer='ones',
                             beta_regularizer=None, gamma_regularizer=None, beta_constraint=None,
                             gamma_constraint=None)(out)
    return out

def Conv2D_Transpose_BatchNorm(input, filters, kernel_size=3, strides=2, padding='same',
                               activation='relu', kernel_initializer='glorot_normal', prob=0.05):
    # Conv2DTranspose also known as a 2D Deconvolution
    out = Conv2DTranspose(filters, kernel_size, strides=2, padding=padding,
                          activation='linear', kernel_initializer=kernel_initializer)(input)
    out = Activation(activation)(out)
    out = tf.keras.layers.SpatialDropout2D(prob)(out)
    out = BatchNormalization(axis=-1, momentum=0.99, epsilon=0.001, center=True,
                             scale=True, beta_initializer='zeros', gamma_initializer='ones',
                             moving_mean_initializer='zeros', moving_variance_initializer='ones',
                             beta_regularizer=None, gamma_regularizer=None, beta_constraint=None,
                             gamma_constraint=None)(out)
    return out

def DownSample(input, filters, kernel_size=3, strides=2, padding='same',
               activation='linear', kernel_initializer='glorot_normal', prob=0.05):
    out = Conv2D_BatchNorm(input, filters, kernel_size=1, strides=1, padding=padding,
                           activation=activation, kernel_initializer = kernel_initializer, prob=prob)
    out = Conv2D_BatchNorm(out, filters, kernel_size, strides=strides, padding=padding,
                           activation=activation, kernel_initializer = kernel_initializer, prob=prob)
    return out
def UpSample(input, filters, kernel_size=3, strides=2, padding='same',
             activation='linear', kernel_initializer='glorot_normal', prob=0.05):
    out = Conv2D_BatchNorm(input, filters, kernel_size=1, strides=1, padding=padding,
                          activation=activation, kernel_initializer = kernel_initializer, prob=prob)
    out = Conv2D_Transpose_BatchNorm(out, filters, kernel_size, strides=strides, padding=padding,
                                     activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    return out

###################################################################################################
'''
FULLY DENSE BLOCK:
'''
# Inpired by work done in https://arxiv.org/ftp/arxiv/papers/1808/1808.10848.pdf:
def FD_Block(input, f_in, f_out, k, kernel_size=3, padding='same',
             activation='linear', kernel_initializer='glorot_normal', prob=0.05):
    out = input
    for i in range (f_in, f_out, k):
        shortcut = out
        out = Conv2D_BatchNorm(out, filters=f_in, kernel_size=1, strides=1, padding=padding,
                               activation=activation, kernel_initializer = kernel_initializer, prob=prob)
        out = Conv2D_BatchNorm(out, filters=k, kernel_size=kernel_size, strides=1, padding=padding,
                               activation=activation, kernel_initializer = kernel_initializer, prob=prob)
        out = Concatenate()([out, shortcut])
    return out

###################################################################################################
'''
FUNCTION TO INSTANTIATE MODEL:
'''
def getModel(input_shape, filters, kernel_size, padding='same',
             activation='relu', kernel_initializer='glorot_normal', prob=0.05):

    model_inputs = Input(shape=input_shape, name='img')
    model_outputs = FD_UNet(model_inputs, filters=filters, kernel_size=kernel_size, padding=padding,
                            activation=activation, kernel_initializer=kernel_initializer, prob=prob)
    model = Model(model_inputs, model_outputs, name='FD_UNet_Model_Spatial_Dropout')

    return model
getModel.__name__ = 'FD_UNet_Model_Spatial_Dropout'
