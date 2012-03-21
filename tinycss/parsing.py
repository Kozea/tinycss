# coding: utf8
"""
    tinycss.parsing
    ---------------

    Utilities for parsing lists of tokens.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals


# TODO: unit tests

def split_on_comma(tokens):
    """Split a list of tokens on commas, ie ',' DELIM tokens.

    Only "top-level" comma tokens are splitting points, not commas inside a
    function or other :class:`ContainerToken`.

    :returns: A list of lists of tokens

    """
    parts = []
    this_part = []
    for token in tokens:
        if token.type == 'DELIM' and token.value == ',':
            parts.append(this_part)
            this_part = []
        else:
            this_part.append(token)
    parts.append(this_part)
    return parts
