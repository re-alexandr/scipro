# -*- coding: utf-8 -*-

from numpy import abs,exp,complex64,pi,arctan2,real,imag,linspace,zeros,diff,sqrt
from scipy import optimize, integrate
from scipy.fftpack import fft, ifft, fftshift, ifftshift, fftfreq
from .scipro import SciPro
import pylab as pl


class Field(SciPro):
    '''
    Field (complex) data,
    yform could be:
        complex [yr] (default)
        alg [yr+j*yi],
        exp [yr*exp(j*yi)]
    param string d: Domain, time or freq
    '''
    def __init__(self, x = None, yr = None, yi = None, yform = None, d='time', cf=0.0):
        self.domain = d
        self.central_freq = cf
        if yr is None and yi is None:
            yi = x[2]
            yr = x[1]
            x = x[0]
            if yform is None:
                yform = 'alg'

        if yform is None:
            yform = 'complex'

        if yform == 'complex':
            SciPro.__init__(self, x, yr, ytype = 'lin', xtype = 'lin', dtype=complex64)
        elif yform == 'alg':
            SciPro.__init__(self, x, yr + 1j*yi, ytype = 'lin', xtype = 'lin', dtype=complex64)
        elif yform == 'exp':
            SciPro.__init__(self, x, yr*exp(1j*yi), ytype = 'lin', xtype = 'lin', dtype=complex64)
        else:
            print('unknown yform')

    def copy(self):
        return Field(self.x.copy(), self.y.copy(), d=self.domain, cf=self.central_freq)

    def phasemerged(self, gap=4./3, shift=0):
        retval = self.abs2()
        retval.y = arctan2(imag(self.y), real(self.y))
        phy = retval.y.copy()
        for i in range(1, len(self.y)):
            if phy[i-1] - phy[i] > gap*pi:
                shift = shift + 2*pi
            elif phy[i-1] - phy[i] < -gap*pi:
                shift = shift - 2*pi
            retval.y[i] += shift
        return retval

    def phase(self):
        retval = self.abs2()
        retval.y = arctan2(imag(self.y), real(self.y))
        return retval

    def instfreq(self):
        retval = self.phasemerged()
        retval.y = diff(retval.y)/(-2*pi*abs(self.x[-1]-self.x[0])/(len(self.x)-1))
        retval.x = retval.x[:-1]
        return retval

    def add_phase(self, ph=[0.]):
        """
        :ph: phase as ph_0 + ph_1*(freq-cf) + ph_2*(freq-cf)**2 ... . *Unit: rad*
        """
        retval = self.copy()
        phase = zeros(self.x.size)
        if self.domain == 'time':
            for i in range(len(ph)):
                phase += ph[i] * self.x**i
        else:
            for i in range(len(ph)):
                phase += ph[i] * (self.x - self.central_freq)**i
        retval.y *= exp(1j*phase)
        return retval

    def add_chirp(self, chirp_val):
        """
        :chirp_val: chirp value. *Unit: rad*
        """
        retval = self.copy()
        retval.y *= exp(1j*retval.x**2*chirp_val)
        return retval

    def chirp(self, pgap = 4./3):
        """
        return: chirp value as a result of parabolic phase fitting
        """
        ffpartph = self.phasemerged(gap = pgap)
        funclinfit = lambda p, x: p[0]+p[1]*x+p[2]*x**2
        func = lambda p, x, y: (funclinfit(p, x)-y)
        p0 = [ ffpartph.y[0], (ffpartph.y[-1]-ffpartph.y[0])/(ffpartph.x[-1]-ffpartph.x[0]), 0.]
        p = optimize.leastsq( 
                func, p0, args=(ffpartph.x, ffpartph.y))
        return p[0][2]

    def power(self):
        '''return the power value of the data'''
        return integrate.trapz(real(self.y * self.y.conjugate()), self.x)

    def normpower(self, pwr=1.):
        '''normalize power of data to pwr'''
        k = pwr/self.power()
        retval = self.copy()
        retval.y = self.y * sqrt(k)
        return retval

    def fft(self, asis=False):
        '''
        Fast Fourier transform
        param bool asis: do not perform normalization (True) or keep total energy (False)

        Note:
            ifftshift is necessary here to align input data in the range of [-T/2:T/2]
            to the DFT range [0:T]. For more details see [1] (fourier.py) and [2] (page 325)
            [1] https://github.com/ncgeib/pypret
            [2] Hansen E.W., Fourier Transforms: Principles and Applications. John Wiley & Sons, Hoboken 2014 (ISBN: 978-1-118-47914-8)
        '''
        if self.domain == 'time':
            retval = self.copy()
            retval.domain = 'freq'
            dt = abs(self.x[-1]-self.x[0])/(len(self.x)-1)
            retval.x = fftshift(fftfreq(self.x.size, dt) + self.central_freq)
            retval.y = fftshift(fft(ifftshift(self.y)))
            if not asis:
                ten = self.power()
                retval = retval.normpower(ten)
        else:
            raise Exception("fft can not be applied to a frequency domain")
        return retval

    def ifft(self, asis=False):
        '''
        inverse Fast Fourier transform
        param bool asis: do not perform normalization (True) or keep total energy (False)

        Note: see explanation about one additional fftshift in self.fft
        '''
        if self.domain == 'freq':
            retval = self.copy()
            retval.domain = 'time'
            fmin = abs(self.x[-1]-self.x[0])/(len(self.x)-1)
            retval.x = linspace(-0.5/fmin, 0.5/fmin, self.x.size, False)
            retval.y = fftshift(ifft(ifftshift(self.y)))
            if not asis:
                ten = self.power()
                retval = retval.normpower(ten)
        else:
            raise Exception("ifft can not be applied to a time domain")
        return retval

    def abs2(self, p = 2):
        rvy = real(self.y * self.y.conjugate())**(p/2.)
        if self.domain == 'time':
            from .oscillogram import Oscillogram
            return Oscillogram(self.x, rvy)
        else:
            from .spectrum import Spectrum
            return Spectrum(self.x, rvy, xtype='freq')

    def plot(self, *arguments, **keywords):
        '''fuction to plot self spectr\nplot(ptype = 'lin', xl = 'Wavelength, nm', yl = 'Intensity, a.u.')'''
        #TODO ptype = log
        #if not keywords.has_key( 'xl'):
        #    keywords['xl'] = 'Wavelength, nm'
        #if not keywords.has_key( 'yl'):
        #    keywords['yl'] = 'Intensity, a.u.'
        if 'pform' in keywords:
            pform = keywords.pop('pform')
        else:
            pform = 'abs'
        if 'pgap' in keywords:
            pgap = keywords.pop('pgap')
        else:
            pgap = 4./3
        if 'pshift' in keywords:
            pshift = keywords.pop('pshift')
        else:
            pshift = 0

        if len(pl.gcf().axes) > 0:
            ax1 = pl.gcf().axes[0]
        else:
            ax1 = pl.axes()
        if len(pl.gcf().axes) > 1:
            ax2 = pl.gcf().axes[1]
        else:
            ax2 = pl.twinx()

        if pform == 'abs':
            # save lines to be able to change it later
            l1, = ax1.plot( self.x, self.abspower().y, *arguments, **keywords)
            ax1.plot( self.x[0], self.abspower().y[0], *arguments, **keywords)
            # plot one point to shift colors
            ax2.plot( self.x[0], self.phase().y[0], *arguments, **keywords)
            l2, = ax2.plot( self.x, self.phasemerged(pgap, pshift).y, *arguments, **keywords)
            ax1.set_ylabel('Intensity, |A|**2')
            ax2.set_ylabel('Phase, rad')
            if self.domain == 'time':
                ax1.set_xlabel('Time, ps')
            else:
                ax1.set_xlabel('Frequency, THz')
            pl.sca(ax1)
        elif pform == 'real':
            super(Field, self).plot(self.x, real(self.y), *arguments, **keywords)
        elif pform == 'imag':
            super(Field, self).plot(self.x, imag(self.y), *arguments, **keywords)
        else:
            print('Unknown type '+type+', use \"abs\",\"real\" or \"imag\"')
        return l1, l2
