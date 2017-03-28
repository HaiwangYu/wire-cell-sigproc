#!/usr/bin/env python
import units
import response

import numpy
import matplotlib.pyplot as plt

def fine_response(rflist_fine, regions = None, shaped=False):
    '''
    Plot fine response functions
    '''
    if regions is None:
        regions = sorted(set([x.region for x in rflist_fine]))
    nregions = len(regions)
    impacts = sorted(set([x.impact for x in rflist_fine]))

    fig, axes = plt.subplots(nregions, 3, sharex=True)

    byplane = response.group_by(rflist_fine, 'plane')

    for iplane, plane_rfs in enumerate(byplane):
        print 'plane %d, %d regions' % (iplane, len(plane_rfs))
        byregion = response.group_by(plane_rfs,'region')

        byregion = [lst for lst in byregion if lst[0].region in regions]

        for iregion, region_rfs in enumerate(byregion):
            region_rfs.sort(key=lambda x: x.impact)
            first = region_rfs[0]

            ax = axes[iregion][iplane]
            ax.set_title('region %d' % (first.region,))
            print "plane=%s, region=%d, impacts: " % (first.plane,first.region),
            for rf in region_rfs:
                if shaped:
                    rf = rf.shaped()
                times = numpy.linspace(*rf.domainls)/units.us
                ax.plot(times, rf.response)
                print "[%f] " % rf.impact,
            print
    
    
def average_shaping(rflist_avg, gain_mVfC=14, shaping=2.0*units.us, nbins=5000):
    '''
    Plot average field responses and with electronics shaping.
    '''
    byplane = response.group_by(rflist_avg, 'plane')
    nfields = len(byplane[0])
    main_field = [rf for rf in byplane[2] if rf.region == 0][0]
    main_field_sum = numpy.max(numpy.abs(main_field.response))
    main_shaped = main_field.shaped(gain_mVfC, shaping, nbins)
    main_shaped_sum = numpy.max(numpy.abs(main_shaped.response))
    rat = main_shaped_sum / main_field_sum


    fig, axes = plt.subplots(nfields, 3, sharex=True)

    for iplane, plane_frs in enumerate(byplane):
        plane_frs.sort(key=lambda x: x.region)

        for ifr, fr in enumerate(plane_frs):
            ax = axes[ifr][iplane]
            ax.set_title('plane %s, region %d' % (fr.plane, fr.region,))

            sh = fr.shaped(gain_mVfC, shaping, nbins)
            ax.plot(fr.times/units.us, fr.response*rat)
            ax.plot(sh.times/units.us, sh.response)
        
    
    


def electronics():
    '''
    Plot electronics response functions
    '''
    fig, axes = plt.subplots(4,1, sharex=True)

    want_gains = [1.0, 4.7, 7.8, 14.0, 25.0]

    engs = numpy.vectorize(response.electronics_no_gain_scale) # by time
    def engs_maximum(gain, shaping=2.0*units.us):
        resp = engs(numpy.linspace(0,10*units.us, 100), gain, shaping)
        return numpy.max(resp)
    engs_maximum = numpy.vectorize(engs_maximum) # by gain
                     
    gainpar = numpy.linspace(0,300,6000)
    for ishaping, shaping in enumerate([0.5, 1.0, 2.0, 3.0]):
        gain = engs_maximum(gainpar, shaping*units.us)
        slope, inter = numpy.polyfit(gainpar, gain, 1)
        hits = list()
        for wg in want_gains:
            amin = numpy.argmin(numpy.abs(gain-wg))
            hits.append((gainpar[amin], gain[amin]))
        hits = numpy.asarray(hits).T

        ax = axes[ishaping]
        ax.set_title("shaping %.1f" % shaping)
        ax.plot(gainpar, gain)
        ax.scatter(hits[0], hits[1], alpha=0.5)
        for hit in hits.T:
            p,g = hit
            ax.text(p,g, "%.2f"%p, verticalalignment='top', horizontalalignment='center')
            ax.text(p,g, "%.2f"%g, verticalalignment='bottom', horizontalalignment='center')
            ax.text(250,10, "%f slope" % slope, verticalalignment='top', horizontalalignment='center')
            ax.text(250,10, "%f mV/fC/par" % (1.0/slope,), verticalalignment='bottom', horizontalalignment='center')



def field_response_spectra(frses):
    uvw='UVW'
    fig, axes = plt.subplots(3, 2, sharex=True, sharey=True)

    for ind,frs in enumerate(frses):
        ax = axes[ind,0]
        im1 = ax.imshow(numpy.absolute(frs), aspect='auto')
        ax.set_title('%s response amp' % uvw[ind])

        ax = axes[ind,1]
        im2 = ax.imshow(numpy.angle(frs), aspect='auto')
        ax.set_title('%s response phase' % uvw[ind])

    fig.colorbar(im1, ax=axes[:,0].tolist())
    fig.colorbar(im2, ax=axes[:,1].tolist())



def plane_impact_blocks(pibs):
    '''
    Make a "contact sheet" of different responses on wires nearest a
    path.  Wire 0 is the wire most nearest.  Each thumbnail shows
    responses as a function of wire and time and thumbnails are
    organized in rows of the same impact position and columns of the
    same plane.

    Note, for the upper-most and lower-most impacts each neighboring wires there are impacts which start at
    the same point
    '''

    uvw='uvw'
    times, regions = numpy.meshgrid(
        numpy.linspace(pibs.tmin, pibs.tmax, pibs.ntbins),
        numpy.linspace(pibs.region_keys[0], pibs.region_keys[-1], len(pibs.region_keys)))
    times /= units.us

    #xylim = (times.min(), times.max(), regions.min(), regions.max())
    xylim = (60, 90, -10, 10)

    impact_keys = list(pibs.impact_keys)
    impact_keys.reverse()

    fig, axes = plt.subplots(len(impact_keys), 3, sharex=True, sharey=True)
    plt.subplots_adjust(left=0.05, right=0.95,
                        bottom=0.02, top=0.98,
                        wspace=0.2, hspace=0.2)

    minres = [numpy.min(pibs.response(p, 0.0, 0)) for p in 'uvw']
    maxres = [numpy.max(pibs.response(p, 0.0, 0)) for p in 'uvw']
    print minres, maxres


    for iplane, plane in enumerate(pibs.plane_keys):
        plane_axes = list()
        ims = list()
        for iimpact, impact in enumerate(impact_keys):

            block = pibs.region_block(plane, impact)
            ax = axes[iimpact,iplane]
            plane_axes.append(ax)
            im = ax.pcolormesh(times, regions, block)
            ims.append(im)

            ax.set_title('%s-plane, impact %0.1f' % (plane, impact))
            if impact == impact_keys[-1]:
                ax.set_xlabel('time [us]')
            ax.set_ylabel('wire')
            ax.axis(xylim)

            fig.colorbar(im, ax=[ax])
    
    
def plane_impact_blocks_full(pibs):
    '''
    Make a plot for each plane of the response on its central wire due
    to paths a all impacts running through the wire regions.

    Note, the two impacts at the boundary between two wire regions are
    explicitly shown.  Each can be considered epsilon over the line of
    symmetry.
    '''

    region_keys = list(pibs.region_keys)
    nregions = len(region_keys)
    print '%d regions: %s' % (nregions, region_keys)

    impact_keys = list(pibs.impact_keys) # put positive numbers on top
    nimpacts = len(impact_keys)
    print '%d impacts: %s' % (nimpacts, impact_keys)
    
    print "t=(%f,%f)" % (pibs.tmin, pibs.tmax)
    times, regions = numpy.meshgrid(
        numpy.linspace(pibs.tmin, pibs.tmax, pibs.ntbins),
        numpy.linspace(impact_keys[0]+region_keys[0],
                       impact_keys[-1]+region_keys[-1],
                       nimpacts*nregions))
    times /= units.us
    xylim = (times.min(), times.max(), regions.min(), regions.max())
    print 'limits: ', xylim

    fig, axes = plt.subplots(3, 1, sharex=True, sharey=True)

    for iplane, plane in enumerate(pibs.plane_keys):

        block = numpy.zeros((nregions*nimpacts, pibs.ntbins))
        print '%s-plane shapes: times=%s regions=%s block=%s ' % (plane, times.shape, regions.shape, block.shape)

        for iregion, region in enumerate(region_keys):
            for iimpact, impact in enumerate(impact_keys):
                row = nimpacts * iregion + iimpact
                block[row] = pibs.response(plane,impact,-region)

        ax = axes[iplane]
        im = ax.pcolormesh(times, regions, block)
        #im = ax.imshow(block, extent=xylim, aspect='auto', interpolation="nearest")
        ax.axis(xylim)
        ax.set_title('%s-plane' % plane)
        ax.set_xlabel('time [us]')
        ax.set_ylabel('impact position [pitch]')
        fig.colorbar(im, ax=[ax])
    

#
# stuff below may be bit rotted
# 


def response_by_wire_region(rflist_averages):
    '''
    Plot response functions as 1D graphs.
    '''
    one = rflist_averages[0]
    byplane = response.group_by(rflist_averages, 'plane')

    nwires = map(len, byplane)
    print "%d planes, nwires: %s" % (len(nwires), str(nwires))
    nwires = min(nwires)

    region0s = response.by_region(rflist_averages)
    shaped0s = [r.shaped() for r in region0s]

    central_sum_field = sum(region0s[2].response)
    central_sum_shape = sum(shaped0s[2].response)


    fig, axes = plt.subplots(nwires, 2, sharex=True)

    for wire_region in range(nwires):
        axf = axes[wire_region][0]
        axf.set_title('Wire region %d (field)' % wire_region)
        axs = axes[wire_region][1]
        axs.set_title('Wire region %d (shaped)' % wire_region)

        for iplane in range(3):
            field_rf = byplane[iplane][wire_region]
            shape_rf = field_rf.shaped()
            
            field = field_rf.response
            shape = shape_rf.response
            field /= central_sum_field
            shape /= central_sum_shape
            
            ftime = 1.0e6*numpy.linspace(*field_rf.domainls)
            stime = 1.0e6*numpy.linspace(*shape_rf.domainls)

            axf.plot(ftime, field)
            axs.plot(stime, shape)

def response_averages_colz(avgtriple, time):
    '''
    Plot averages as 2D colz type plot
    '''
    use_imshow = False
    mintbin=700
    maxtbin=850
    nwires = avgtriple[0].shape[0]
    maxwires = nwires//2    
    minwires = -maxwires
    mintime = time[mintbin]
    maxtime = time[maxtbin-1]
    ntime = maxtbin-mintbin
    deltatime = (maxtime-mintime)/ntime

    x,y = numpy.meshgrid(numpy.linspace(mintime, maxtime, ntime),
                          numpy.linspace(minwires, maxwires, nwires))
    x *= 1.0e6                  # put into us

    print x.shape, mintbin, maxtbin, mintime, maxtime, nwires, minwires, maxwires

    fig = plt.figure()
    cmap = 'seismic'

    toplot=list()
    for iplane in range(3):
        avg = avgtriple[iplane]
        main = avg[:,mintbin:maxtbin]
        edge = avg[:,maxtbin:]
        ped = numpy.sum(edge) / (edge.shape[0] * edge.shape[1])
        toplot.append(main - ped)

    maxpix = max(abs(numpy.min(avgtriple)), numpy.max(avgtriple))
    clim = (-maxpix/2.0, maxpix/2.0)

    ims = list()
    axes = list()

    for iplane in range(3):
        ax = fig.add_subplot(3,1,iplane+1) # two rows, one column, first plot
        if use_imshow:
            im = plt.imshow(toplot[iplane], cmap=cmap, clim=clim,
                            extent=[mintime, maxtime, minwires, maxwires], aspect='auto')
        else:
            im = plt.pcolormesh(x,y, toplot[iplane], cmap=cmap, vmin=clim[0], vmax=clim[1])
        ims.append(im)
        axes.append(ax)

    fig.subplots_adjust(right=0.8)
    cbar_ax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
    fig.colorbar(ims[0], ax=axes[0], cmap=cmap, cax=cbar_ax)



def plot_digitized_line(uvw_rfs, gain_mVfC=14.0, shaping=2.0*units.us, tick=0.5*units.us, adc_per_mv = 1.2*4096/2000.0):
    '''
    Make plot of shaped and digitized response functions.

    >>> dat = garfield.load("/home/bviren/projects/wire-cell/garfield-data/ub_10.tar.gz")
    >>> uvw = response.line.responses(dat)
    >>> plots.plot_digitized_line(uvw)

    See also wirecell.sigproc.paper.noise
    '''
    u, v, w = uvw_rfs
    time_offset = 50*units.us

    # deal with some round off.
    dt_hi = int(round(w.times[1] - w.times[0]))
    n_hi = len(w.times)

    n_lo = int(round(dt_hi/tick * n_hi))

    colors = ['red', 'blue', 'black']
    legends = ['U-wire', 'V-wire', 'Y-wire']

    fig, axes = plt.subplots(1, 1)

    data = list()
    for ind, rf in enumerate(uvw_rfs):
        print legends[ind], numpy.sum(rf.response)/units.electron_charge

        if shaping:
            sig = rf.shaped(gain_mVfC, shaping)
        else:
            print 'No shaping'
            sig = rf
        samp = sig.resample(n_lo)
        x = (samp.times-time_offset)/units.us

        if shaping:
            adcf = (samp.response / units.fC) * adc_per_mv
            y = numpy.array(adcf, dtype=int)
            lstype = 'steps'
        else:
            y = samp.response
            lstype = 'default'

        axes.plot(x, y,
                  ls=lstype,
                  color=colors[ind],
                  label=legends[ind])
        if not data:
            data.append(x)
        data.append(y)

    if shaping:
        axes.set_title('ADC Waveform with 2D MicroBooNE Wire Plane Model')
    else:
        axes.set_title('Induced Current with 2D MicroBooNE Wire Plane Model')
    if shaping:
        axes.set_xlabel('Sample time [$\mu$s]')
    else:
        axes.set_xlabel('Time [$\mu$s]')
    if shaping:
        axes.set_ylabel('ADC (baseline subtracted)')
    else:
        axes.set_ylabel('Instantaneous current')
    axes.legend(loc="upper left")
    xmmymm = list(axes.axis())
    xmmymm[0] = 0.0
    xmmymm[1] = 50.0
    xmmymm[3] = 65.0
    axes.axis(xmmymm)
    axes.text(5,20, "   Garfield 2D calculation\n(perpendicular line source)")
    return fig, numpy.vstack(data).T
