# coding: utf8
"""
    tinycss.structures
    ------------------

    Data structures for parse stylesheets.

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals


class _Structure(object):
    __slots__ = ()

    def __init__(self, *args):
        slots = self.__slots__
        if len(args) != len(slots):
            raise TypeError('Got %i arguments, expected %i'
                            % (len(args), len(slots)))
        for name, value in zip(slots, args):
            setattr(self, name, value)


class Stylesheet(_Structure):
    __slots__ = ('statements')


class AtRule(_Structure):
    __slots__ = ('at_keyword', 'content')


class Block(_Structure):
    __slots__ = ('content',)


class RuleSet(_Structure):
    __slots__ = ('content',)


class AtKeyword(_Structure):
    """at-keyword not in an at-rule."""
    __slots__ = ('at_keyword',)


class Declaration(_Structure):
    __slots__ =  ('property_name', 'values')

class ScalarValue(_Structure):
    __slots__ =  ('type', 'value')

class Function(_Structure):
    __slots__ =  ('name', 'arguments')
