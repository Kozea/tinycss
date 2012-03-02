# coding: utf8
"""
    tinycss.tokenizer._speedups
    ---------------------------

    Cython version of the tokenizer’s inner loop.

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals

from . import (
    COMPILED_TOKEN_REGEXPS, UNICODE_UNESCAPE, NEWLINE_UNESCAPE,
    SIMPLE_UNESCAPE, FIND_NEWLINES, Token)


COMPILED_TOKEN_INDEXES = dict(
    (name, i) for i, (name, regexp) in enumerate(COMPILED_TOKEN_REGEXPS))


cdef class CToken:
    __doc__ = Token.__doc__
    is_container = False

    cdef public object type, as_css, value, unit
    cdef public Py_ssize_t line, column

    def __init__(self, type_, css_value, value, unit, line, column):
        self.type = type_
        self.as_css = css_value
        self.value = value
        self.unit = unit
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        return ('<Token {0.type} at {0.line}:{0.column} {0.value!r}{1}>'
                .format(self, self.unit or ''))

    # For debugging:
    pretty = __repr__


def tokenize_flat(css_source, int ignore_comments=1):
    """
    :param css_source:
        CSS as an unicode string
    :param ignore_comments:
        if true (the default) comments will not be included in the
        return value
    :return:
        An iterator of :class:`Token`

    """
    # Make these local variable to avoid global lookups in the loop
    compiled_token_indexes = COMPILED_TOKEN_INDEXES
    compiled_tokens = COMPILED_TOKEN_REGEXPS
    unicode_unescape = UNICODE_UNESCAPE
    newline_unescape = NEWLINE_UNESCAPE
    simple_unescape = SIMPLE_UNESCAPE
    find_newlines = FIND_NEWLINES

    # Use the integer indexes instead of string markers
    cdef Py_ssize_t BAD_COMMENT = compiled_token_indexes['BAD_COMMENT']
    cdef Py_ssize_t BAD_STRING = compiled_token_indexes['BAD_STRING']
    cdef Py_ssize_t PERCENTAGE = compiled_token_indexes['PERCENTAGE']
    cdef Py_ssize_t DIMENSION = compiled_token_indexes['DIMENSION']
    cdef Py_ssize_t ATKEYWORD = compiled_token_indexes['ATKEYWORD']
    cdef Py_ssize_t FUNCTION = compiled_token_indexes['FUNCTION']
    cdef Py_ssize_t COMMENT = compiled_token_indexes['COMMENT']
    cdef Py_ssize_t NUMBER = compiled_token_indexes['NUMBER']
    cdef Py_ssize_t STRING = compiled_token_indexes['STRING']
    cdef Py_ssize_t IDENT = compiled_token_indexes['IDENT']
    cdef Py_ssize_t HASH = compiled_token_indexes['HASH']
    cdef Py_ssize_t URI = compiled_token_indexes['URI']
    cdef Py_ssize_t DELIM = -1

    cdef Py_ssize_t pos = 0
    cdef Py_ssize_t line = 1
    cdef Py_ssize_t column = 1
    cdef Py_ssize_t source_len = len(css_source)
    cdef Py_ssize_t n_tokens = len(compiled_tokens)
    cdef Py_ssize_t length, next_pos, type_
    cdef CToken token

    tokens = []
    while pos < source_len:
        for type_ in xrange(n_tokens):
            type_name, regexp = compiled_tokens[type_]
            match = regexp(css_source, pos)
            if match:
                # First match is the longest. See comments on TOKENS above.
                css_value = match.group()
                break
        else:
            # No match.
            # "Any other character not matched by the above rules,
            #  and neither a single nor a double quote."
            # ... but quotes at the start of a token are always matched
            # by STRING or BAD_STRING. So DELIM is any single character.
            type_ = DELIM
            type_name = 'DELIM'
            css_value = css_source[pos]
        length = len(css_value)
        next_pos = pos + length

        # A BAD_COMMENT is a comment at EOF. Ignore it too.
        if not (ignore_comments and type_ in (COMMENT, BAD_COMMENT)):
            # Parse numbers, extract strings and URIs, unescape
            unit = None
            if type_ == DIMENSION:
                value = match.group(1)
                value = float(value) if '.' in value else int(value)
                unit = match.group(2)
                unit = unicode_unescape(unit)
                unit = simple_unescape(unit)
                unit = unit.lower()  # normalize
            elif type_ == PERCENTAGE:
                value = css_value[:-1]
                value = float(value) if '.' in value else int(value)
                unit = '%'
            elif type_ == NUMBER:
                value = css_value
                value = float(value) if '.' in value else int(value)
            elif type_ in (IDENT, ATKEYWORD, HASH, FUNCTION):
                value = unicode_unescape(css_value)
                value = simple_unescape(value)
            elif type_ == URI:
                value = match.group(1)
                if value and value[0] in '"\'':
                    value = value[1:-1]  # Remove quotes
                    value = newline_unescape(value)
                value = unicode_unescape(value)
                value = simple_unescape(value)
            elif type_ == STRING:
                value = css_value[1:-1]  # Remove quotes
                value = newline_unescape(value)
                value = unicode_unescape(value)
                value = simple_unescape(value)
            # BAD_STRING can only be one of:
            # * Unclosed string at the end of the stylesheet:
            #   Close the string, but this is not an error.
            #   Make it a "good" STRING token.
            # * Unclosed string at the (unescaped) end of the line:
            #   Close the string, but this is an error.
            #   Leave it as a BAD_STRING, don’t bother parsing it.
            # See http://www.w3.org/TR/CSS21/syndata.html#parsing-errors
            elif type_ == BAD_STRING and next_pos == source_len:
                type_name = 'STRING'
                value = css_value[1:]  # Remove quote
                value = newline_unescape(value)
                value = unicode_unescape(value)
                value = simple_unescape(value)
            else:
                value = css_value
            token = CToken(type_name, css_value, value, unit, line, column)
            tokens.append(token)

        pos = next_pos
        newlines = list(find_newlines(css_value))
        if newlines:
            line += len(newlines)
            # Add 1 to have lines start at column 1, not 0
            column = length - newlines[-1].end() + 1
        else:
            column += length
    return tokens
