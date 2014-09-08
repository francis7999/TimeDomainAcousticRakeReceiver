
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy.linalg import toeplitz
from scipy.io import wavfile
from scipy.signal import resample,fftconvolve

import pyroomacoustics as pra

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
room_dim = [4, 6]

# the good source is fixed for all 
good_source = [1, 4.5]       # good source
normal_interferer = [2.8, 4.3]   # interferer
hard_interferer = [1.5, 3]   # interferer in direct path
normal_interferer = hard_interferer

# microphone array design parameters
mic1 = [2, 1.5]         # position
M = 8                    # number of microphones
d = 0.08                # distance between microphones
phi = 0.                # angle from horizontal
max_order_design = 1    # maximum image generation used in design
shape = 'Linear'        # array shape
Lg_t = 0.05             # Filter size in seconds
Lg = np.ceil(Lg_t*Fs)   # Filter size in samples

# define the FFT length
N = 1024

'''
We create a new Beamformer class for Rake MVDR in time-domain
'''
class RakeMVDR_TD(pra.Beamformer):

    def computeWeights(self, sources, interferers, R_n, epsilon=1e-2):

        dist_mat = pra.distance(self.R, sources)
        s_time = dist_mat / pra.c
        s_dmp = 1./(4*np.pi*dist_mat)

        dist_mat = pra.distance(self.R, interferers)
        i_time = dist_mat / pra.c
        i_dmp = 1./(4*np.pi*dist_mat)

        offset = np.maximum(s_dmp.max(), i_dmp.max())/(np.pi*self.Fs*epsilon)
        t_min = np.minimum(s_time.min(), i_time.min()) - offset
        t_max = np.maximum(s_time.max(), i_time.max()) + offset

        s_time -= t_min
        i_time -= t_min
        Lh = int((t_max - t_min)*float(self.Fs))

        # the channel matrix
        Lg = self.Lg
        L = self.Lg + Lh - 1
        H = np.zeros((Lg*self.M, 2*L))

        for r in np.arange(M):

            hs = pra.lowPassDirac(s_time[r,:,np.newaxis], s_dmp[r,:,np.newaxis], self.Fs, Lh).sum(axis=0)
            row = np.pad(hs, ((0,L-len(hs))), mode='constant')
            col = np.pad(hs[:1], ((0, Lg-1)), mode='constant')
            H[r*Lg:(r+1)*Lg,0:L] = toeplitz(col, row)

            hi = pra.lowPassDirac(i_time[r,:,np.newaxis], i_dmp[r,:,np.newaxis], self.Fs, Lh).sum(axis=0)
            row = np.pad(hi, ((0,L-len(hi))), mode='constant')
            col = np.pad(hi[:1], ((0, Lg-1)), mode='constant')
            H[r*Lg:(r+1)*Lg,L:2*L] = toeplitz(col, row)

        # the constraint vector
        h = H[:,Lh-1]

        # We first assume the sample are uncorrelated
        Ryy = np.dot(H, H.T) + R_n

        # Compute the TD filters
        Ryy_inv = np.linalg.inv(Ryy)
        g_temp = np.dot(Ryy_inv, h)
        g = g_temp/np.inner(h, g_temp)
        self.filters = g.reshape((M,Lg))


# create a microphone array
if shape is 'Circular':
    R = pra.circular2DArray(mic1, M, phi, d*M/(2*np.pi)) 
else:
    R = pra.linear2DArray(mic1, M, phi, d) 
mics = RakeMVDR_TD(R, Fs, N, Lg=Lg)

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

# compute beamforming filters
good_sources = room1.sources[0].getImages(max_order=max_order_design)
bad_sources = room1.sources[1].getImages(max_order=max_order_design)
mics.computeWeights(good_sources, bad_sources, sigma2_n*np.eye(mics.Lg*mics.M))
mics.weightsFromFilters()

# process the signal
output = mics.process()

# save to output file
inp = pra.normalize(pra.highpass(mics.signals[mics.M/2], Fs))
out = pra.normalize(pra.highpass(output, Fs))

wavfile.write('output_samples/input.wav', Fs, inp)
wavfile.write('output_samples/output.wav', Fs, out)

'''
Plot Stuff
'''
# plot the room and beamformer
room1.plot(img_order=np.minimum(room1.max_order, 1), 
        freq=freq)

# plot the beamforming weights
plt.figure()
mics.plot()

# plot before/after processing
plt.figure()
pra.comparePlot(inp, out, Fs)

# plot angle/frequency plot
plt.figure()
mics.plot_beam_response()

plt.show()
