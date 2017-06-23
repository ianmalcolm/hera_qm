import numpy as np

np.random.seed(0)


def noise(size):
    sig = 1. / np.sqrt(2)
    return np.random.normal(scale=sig, size=size) + 1j * np.random.normal(scale=sig, size=size)


def real_noise(size):
    sig = 1.
    return np.random.normal(scale=sig, size=size)