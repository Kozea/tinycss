# coding: utf8
"""
    tinycss.token_data
    ------------------

    Shared data for both implementations (Cython and Python) of the tokenizer.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals

import re
import sys
import functools
import operator

from . import token_data


MACROS = {}

def macro(name, value):
    MACROS[name] = '(?:%s)' % value.format(**MACROS)

macro('nl', r'\n|\r\n|\r|\f')
macro('w', r'[ \t\r\n\f]*')
macro('nonascii', '[^\0-\237]')
macro('escape', r'''
        \\[0-9a-f]{{1,6}}
        (?:
            \r\n | [ \n\r\t\f]
        )?
    |
        \\[^\n\r\f0-9a-f]
''')
macro('nmstart', r'[_a-z]|{nonascii}|{escape}')
macro('nmchar', r'[_a-z0-9-]|{nonascii}|{escape}')
macro('name', r'{nmchar}+')
macro('ident', r'[-]?{nmstart}{nmchar}*')
macro('string', r'''
        "
        (?:
            [^\n\r\f\\"]|\\{nl}|{escape}
        )*
        "
    |
        '
        (?:
            [^\n\r\f\\']|\\{nl}|{escape}
        )*
        '
''')
macro('badstring', r'''
        "
        (?:
            [^\n\r\f\\"]|\\{nl}|{escape}
        )*
        \\?
    |
        '
        (?:
            [^\n\r\f\\']|\\{nl}|{escape}
        )*
        \\?
''')


TOKENS_RE = re.compile(r'''
    (?P<S>
        [ \t\r\n\f]+
    ) |
    (?P<URI>
        url\({w}
        (?P<uri_content>
            {string} |
            (?:
                [!#$%&*-\[\]-~] | {nonascii} | {escape}
            )*
        )
        {w}\)
    ) |
    (?P<BAD_URI>
            url\({w}
            (?:
                [!#$%&*-~] | {nonascii} | {escape}
            )*
            {w}
        |
            url\({w}{string}{w}
        |
            url\({w}{badstring}
    ) |
    (?P<FUNCTION>
        {ident}\(
    ) |
    (?P<UNICODE_RANGE>
        u\+
        [0-9a-f?]{{1,6}}
        (-[0-9a-f]{{1,6}})?
    ) |
    (?P<IDENT>
        {ident}
    ) |
    (?P<ATKEYWORD>
        @{ident}
    ) |
    (?P<HASH>
        \#{name}
    ) |
    (?P<numbers>
        (?:
            (?P<fractional>
                [+-]?[0-9]*\.[0-9]+
            ) |
            (?P<integer>
                [+-]?[0-9]+
            )
        )
        (?P<unit>
            % | {ident}
        ) ?
    ) |
    (?P<STRING>
        {string}
    ) |
    (?P<BAD_STRING>
        {badstring}
    ) |
    (?P<COMMENT>
        /\*
        [^*]*
        \*+
        (?:
            [^/*]
            [^*]*
            \*+
        )*
        /
    ) |
    (?P<BAD_COMMENT>
        (?:
            /\*
            [^*]*
            \*+
            (?:
                [^/*]
                [^*]*
                \*+
            )*
        ) |
        (?:
            /\*
            [^*]*
            (?:
                \*+
                [^/*]
                [^*]*
            )*
        )
    ) |
    (?P<CDO>
        <!--
    ) |
    (?P<CDC>
        -->
    )
'''.format(**MACROS), re.VERBOSE | re.IGNORECASE)


try:
    unichr
except NameError:
    # Python 3
    unichr = chr
    unicode = str


def _unicode_replace(match, int=int, unichr=unichr, maxunicode=sys.maxunicode):
    codepoint = int(match.group(1), 16)
    if codepoint <= maxunicode:
        return unichr(codepoint)
    else:
        return '\N{REPLACEMENT CHARACTER}'  # U+FFFD


UNICODE_UNESCAPE = functools.partial(
    re.compile(r'\\([0-9a-f]{1,6})(?:\r\n|[ \n\r\t\f])?', re.I).sub,
    _unicode_replace)

NEWLINE_UNESCAPE = functools.partial(
    re.compile(r'\\(?:\n|\r\n|\r|\f)').sub,
    '')

SIMPLE_UNESCAPE = functools.partial(
    re.compile(r'\\(.)').sub,
    # Same as r'\1', but faster on CPython
    operator.methodcaller('group', 1))

NEWLINES_RE = re.compile(MACROS['nl'])


def tokenize_flat(css_source, ignore_comments=True,
    unicode_unescape=UNICODE_UNESCAPE,
    newline_unescape=NEWLINE_UNESCAPE,
    simple_unescape=SIMPLE_UNESCAPE,
    Token=token_data.Token,
    len=len,
    int=int,
    float=float,
    list=list,
    _None=None,
    ):
    """
    :param css_source:
        CSS as an unicode string
    :param ignore_comments:
        if true (the default) comments will not be included in the
        return value
    :return:
        An iterator of :class:`Token`

    """
    regexp = TOKENS_RE.match
    find_newlines = NEWLINES_RE.finditer
    pos = 0
    line = 1
    column = 1
    source_len = len(css_source)
    tokens = []
    append_token = tokens.append
    while pos < source_len:
        char = css_source[pos]
        if char in ':;{}()[]':
            type_ = char
            css_value = char
            value = char
            unit = _None
            length = 1
            next_pos = pos + 1
        else:
            match = regexp(css_source, pos)
            if match:
                groups = match.groupdict()
                css_value = match.group()
                length = len(css_value)
                next_pos = pos + length
                value = css_value
                unit = _None
                if groups['S']:
                    type_ = 'S'
                elif groups['numbers']:
                    integer = groups['integer']
                    if integer:
                        value = int(integer)
                        type_ = 'INTEGER'
                    else:
                        value = float(groups['fractional'])
                        type_ = 'NUMBER'
                    unit = groups['unit']
                    if unit == '%':
                        type_ = 'PERCENTAGE'
                    elif unit:
                        type_ = 'DIMENSION'
                        unit = unicode_unescape(unit)
                        unit = simple_unescape(unit)
                        unit = unit.lower()  # normalize
                elif groups['IDENT']:
                    type_ = 'IDENT'
                    value = unicode_unescape(css_value)
                    value = simple_unescape(value)
                elif groups['ATKEYWORD']:
                    type_ = 'ATKEYWORD'
                    value = unicode_unescape(css_value)
                    value = simple_unescape(value)
                elif groups['HASH']:
                    type_ = 'HASH'
                    value = unicode_unescape(css_value)
                    value = simple_unescape(value)
                elif groups['FUNCTION']:
                    type_ = 'FUNCTION'
                    value = unicode_unescape(css_value)
                    value = simple_unescape(value)
                elif groups['URI']:
                    type_ = 'URI'
                    value = groups['uri_content']
                    if value and value[0] in '"\'':
                        value = value[1:-1]  # Remove quotes
                        value = newline_unescape(value)
                    value = unicode_unescape(value)
                    value = simple_unescape(value)
                elif groups['STRING']:
                    type_ = 'STRING'
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
                elif groups['BAD_STRING']:
                    if next_pos == source_len:
                        type_ = 'STRING'
                        value = css_value[1:]  # Remove quote
                        value = newline_unescape(value)
                        value = unicode_unescape(value)
                        value = simple_unescape(value)
                    else:
                        type_ = 'BAD_STRING'
                elif groups['COMMENT']:
                    type_ = 'COMMENT'
                elif groups['BAD_COMMENT']:
                    type_ = 'BAD_COMMENT'
                elif groups['BAD_URI']:
                    type_ = 'BAD_URI'
                elif groups['UNICODE_RANGE']:
                    type_ = 'UNICODE-RANGE'
                elif groups['CDO']:
                    type_ = 'CDO'
                else:
                    assert groups['CDC']
                    type_ = 'CDC'
            else:
                # No match.
                # "Any other character not matched by the above rules,
                #  and neither a single nor a double quote."
                # ... but quotes at the start of a token are always matched
                # by STRING or BAD_STRING. So DELIM is any single character.
                type_ = 'DELIM'
                css_value = char
                value = char
                unit = _None
                length = 1
                next_pos = pos + 1

        # A BAD_COMMENT is a comment at EOF. Ignore it too.
        if not (ignore_comments and type_ in ('COMMENT', 'BAD_COMMENT')):
            append_token(Token(type_, css_value, value, unit, line, column))

        pos = next_pos
        newlines = list(find_newlines(css_value))
        if newlines:
            line += len(newlines)
            # Add 1 to have lines start at column 1, not 0
            column = length - newlines[-1].end() + 1
        else:
            column += length
    return tokens
