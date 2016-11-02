#!/usr/bin/env python
'''
This module defines an object schema which strives to be generic
enough to describe various sets of field responses including:

    - 0D :: responses which do not extend to inter-pitch regions and
      have no intra-pitch variation.  Responses come from averaged 2D
      field calculations, eg with Garfield.  This is the type
      originally used for LArSoft simulation and deconvoultion for
      some time.

    - 1D :: responses defined on drift paths starting from
      fine-grained points on a line perpendicular to drift and wire
      directions and which spans multiple wire regions.  Responses
      come from 2D field calculations, eg with Garfield.  This is the
      type used in the Wire Cell simulation as developed by Xiaoyue Li
      and Wire Cell deconvolution as developed by Xin Qian.

    - 2D :: responses defined on drift paths starting from
      fine-grained points on a plane perpendicular to nominal drift
      direction and spanning multiple wire regions.  Responses come
      from 3D field calculations, eg with LARF.  Simulation and
      deconvolution using these type of responses are not yet
      developed.

The schema is defined through a number of `namedtuple` collections.

Units Warning: time in microseconds, distance in millimeters, current
in Amperes.  This differs from the Wire Cell system of units!
'''

from collections import namedtuple

class FieldResponse(namedtuple("FieldResponse","planes axis origin tstart period")):
    '''
    :param list planes: List of PlaneResponse objects.
    :param list axis: A normalized 3-vector giving direction of axis (anti)parallel to nominal drift direction.
    :param float origin: location in millimeters on the axis where drift paths begin.
    :param float tstart: time in microseconds at which drift paths begin.
    :param float period: the sampling period in microseconds.
    '''
    __slots__ = ()




class PlaneResponse(namedtuple("PlaneResponse","paths planeid pitch pitchdir wiredir")):
    '''
    :param list paths: List of PathResponse objects.
    :param int planeid: A numerical identifier for the plane.
    :param float pitch: The wire pitch in millimeters.
    :param list pitchdir: A normalized 3-vector giving direction of the wire pitch.
    :param list wiredir: A normalized 3-vector giving direction of the wire run.

    Along with FieldResponse.axis, the following should hold: axis X wiredir = pitchdir
    '''
    __slots__ = ()
    

class PathResponse(namedtuple("PathResponse", "current pitchpos wirepos")):
    '''
    :param array current: A Bumpy array holding the induced current for the path on the wire-of-interest.
    :param float pitchpos: The position in the pitch direction to the starting point of the path, in millimeters.
    :param float wirepos: The position along the wire direction to the starting point of the path, in millimeters.

    Note: the path is in wire region: region = int(round(pitchpos/pitch)).

    Note: the path is at the impact position relative to closest wire: impact = pitchpos-region*pitch.
    '''
    __slots__ = ()


import numpy

def todict(obj):
    '''
    Return a dictionary for the object which is marked up for type.
    '''
    for typ in FieldResponse, PlaneResponse, PathResponse:
        if isinstance(obj, typ):
            return {obj.__class__.__name__: {k:todict(v) for k,v in obj._asdict().items()}}
    if isinstance(obj, numpy.ndarray):
        shape = list(obj.shape)
        elements = obj.flatten().tolist()
        return dict(array=dict(shape=shape,elements=elements))
    if isinstance(obj, list):
        return [todict(ele) for ele in obj]

    return obj

def fromdict(obj):
    '''
    Undo `todict()`.
    '''
    if isinstance(obj, dict):
        if 'array' in obj:
            return numpy.asarray(obj['array']['elements']).reshape(obj['array']['shape'])
        for typ in FieldResponse, PlaneResponse, PathResponse:
            if typ.__name__ in obj:
                return typ(**{k:fromdict(v) for k,v in obj[typ.__name__].items()})
    if isinstance(obj, list):
        return [fromdict(ele) for ele in obj]
    return obj
