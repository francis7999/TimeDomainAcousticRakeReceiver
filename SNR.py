
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.linalg import toeplitz
from scipy.io import wavfile
from scipy.signal import resample,fftconvolve

import pyroomacoustics as pra
import TDBeamformers as tdb

# Beam pattern figure properties
freq=[800, 1600]
figsize=(1.88,2.24)
xlim=[-4,8]
ylim=[-4.9,9.4]

# Some simulation parameters
Fs = 8000
t0 = 1./(Fs*np.pi*1e-2)  # starting time function of sinc decay in RIR response
absorption = 0.90
max_order_sim = 10
sigma2_n = 1e-7

# Room 1 : Shoe box
room_dim = np.array([4, 6])

# the good source is fixed for all 
good_source = [1, 4.5]       # good source
normal_interferer = [2.8, 4.3]   # interferer
hard_interferer = [1.5, 3]   # interferer in direct path
#normal_interferer = hard_interferer

# microphone array design parameters
mic1 = [2, 1.5]         # position
M = 8                    # number of microphones
d = 0.08                # distance between microphones
phi = 0.                # angle from horizontal
max_order_design = 1    # maximum image generation used in design
shape = 'Linear'        # array shape
Lg_t = 0.03             # Filter size in seconds
Lg = np.ceil(Lg_t*Fs)   # Filter size in samples

# define the FFT length
N = 1024

# create a microphone array
if shape is 'Circular':
    R = pra.circular2DArray(mic1, M, phi, d*M/(2*np.pi)) 
else:
    R = pra.linear2DArray(mic1, M, phi, d) 
mics = tdb.RakeMVDR_TD(R, Fs, N, Lg=Lg)

# The first signal (of interest) is singing
rate1, signal1 = wavfile.read('samples/singing_'+str(Fs)+'.wav')
signal1 = np.array(signal1, dtype=float)
signal1 = pra.normalize(signal1)
signal1 = pra.highpass(signal1, Fs)
delay1 = 0.

# the second signal (interferer) is some german speech
rate2, signal2 = wavfile.read('samples/german_speech_'+str(Fs)+'.wav')
signal2 = np.array(signal2, dtype=float)
signal2 = pra.normalize(signal2)
signal2 = pra.highpass(signal2, Fs)
delay2 = 1.

# create the room with sources and mics
room1 = pra.Room.shoeBox2D(
    [0,0],
    room_dim,
    Fs,
    t0 = t0,
    max_order=max_order_sim,
    absorption=absorption,
    sigma2_awgn=sigma2_n)

# add mic and good source to room
room1.addSource(good_source, signal=signal1, delay=delay1)
room1.addMicrophoneArray(mics)

# add interferer
room1.addSource(normal_interferer, signal=signal2, delay=delay2)

# simulate the acoustic
room1.compute_RIR()
room1.simulate()

max_source = 15
loops = 10
SNR = np.zeros((max_source, loops))

for i in np.arange(max_source):
    for n in np.arange(loops):

        source = np.random.random(2)*room_dim
        interferer = np.random.random(2)*room_dim
        mics = tdb.RakeMaxSINR_TD(R, Fs, N, Lg=Lg)

        room1.addSource(source)
        room1.addSource(interferer)
        room1.addMicrophoneArray(mics)

        room1.compute_RIR()

        # compute beamforming filters
        good_sources = room1.sources[0].getImages(n_nearest=i+1, ref_point=source[:,np.newaxis])
        bad_sources = room1.sources[1].getImages(n_nearest=i+1, ref_point=source[:,np.newaxis])
        SNR[i,n] = mics.computeWeights(good_sources, bad_sources, sigma2_n*np.eye(mics.Lg*mics.M))

plt.figure()
plt.plot(np.arange(max_source)+1, SNR.median())
