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




class PlaneResponse(namedtuple("PlaneResponse","paths planeid location pitch pitchdir wiredir")):
    '''
    :param list paths: List of PathResponse objects.
    :param int planeid: A numerical identifier for the plane.
    :param float location: Location in drift direction of this plane.
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


