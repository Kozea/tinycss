# coding: utf8
"""
    tinycss.tokenizer
    -----------------

    Tokenizer for the CSS core syntax:
    http://www.w3.org/TR/CSS21/syndata.html#tokenization

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals

import re
import sys
import functools
from string import Formatter


# * Raw strings with the r'' notation are used so that \ do not need
#   to be escaped.
# * Names and regexps are separated by a tabulation.
# * Macros are re-ordered so that only previous definitions are needed.
# * {} are used for macro substitution with ``string.Formatter``,
#   so other uses of { or } have been doubled.
# * The syntax is otherwise compatible with re.compile.
# * Some parentheses were added to add capturing groups.
#   (in unicode, DIMENSION and URI)

# *** Willful violation: ***
# Numbers can take a + or - sign, but the sign is a separate DELIM token.
# Since comments are allowed anywhere between tokens, this makes
# the following this is valid. It means 10 negative pixels:
#    margin-top: -/**/10px

# This makes parsing numbers a pain, so instead we’ll do the same is Firefox
# and make the sign part as of the 'num' macro. The above CSS will be invalid.
# See discussion:
# http://lists.w3.org/Archives/Public/www-style/2011Oct/0028.html
MACROS = r'''
    nl	\n|\r\n|\r|\f
    w	[ \t\r\n\f]*
    nonascii	[^\0-\237]
    unicode	\\([0-9a-f]{{1,6}})(\r\n|[ \n\r\t\f])?
    escape	{unicode}|\\[^\n\r\f0-9a-f]
    nmstart	[_a-z]|{nonascii}|{escape}
    nmchar	[_a-z0-9-]|{nonascii}|{escape}
    name	{nmchar}+
    ident	[-]?{nmstart}{nmchar}*
    num	[-+]?(?:[0-9]*\.[0-9]+|[0-9]+)
    string1	\"([^\n\r\f\\"]|\\{nl}|{escape})*\"
    string2	\'([^\n\r\f\\']|\\{nl}|{escape})*\'
    string	{string1}|{string2}
    badstring1	\"([^\n\r\f\\"]|\\{nl}|{escape})*\\?
    badstring2	\'([^\n\r\f\\']|\\{nl}|{escape})*\\?
    badstring	{badstring1}|{badstring2}
    badcomment1	\/\*[^*]*\*+([^/*][^*]*\*+)*
    badcomment2	\/\*[^*]*(\*+[^/*][^*]*)*
    badcomment	{badcomment1}|{badcomment2}
    baduri1	url\({w}([!#$%&*-~]|{nonascii}|{escape})*{w}
    baduri2	url\({w}{string}{w}
    baduri3	url\({w}{badstring}
    baduri	{baduri1}|{baduri2}|{baduri3}
'''.replace(r'\0', '\0').replace(r'\237', '\237')

TOKENS = r'''
    IDENT	{ident}
    ATKEYWORD	@{ident}
    STRING	{string}
    BAD_STRING	{badstring}
    BAD_URI	{baduri}
    BAD_COMMENT	{badcomment}
    HASH	#{name}
    NUMBER	{num}
    PERCENTAGE	{num}%
    DIMENSION	({num})({ident})
    URI	url\({w}({string}|([!#$%&*-\[\]-~]|{nonascii}|{escape})*){w}\)
    UNICODE-RANGE	u\+[0-9a-f?]{{1,6}}(-[0-9a-f]{{1,6}})?
    CDO	<!--
    CDC	-->
    :	:
    ;	;
    {	\{{
    }	\}}
    (	\(
    )	\)
    [	\[
    ]	\]
    S	[ \t\r\n\f]+
    COMMENT	\/\*[^*]*\*+([^/*][^*]*\*+)*\/
    FUNCTION	{ident}\(
    INCLUDES	~=
    DASHMATCH	|=
'''

COMPILED_MACROS = {}
COMPILED_TOKENS = []  # ordered


def _init():
    """Import-time initialization."""
    COMPILED_MACROS.clear()
    expand_macros = functools.partial(
        Formatter().vformat, args=(), kwargs=COMPILED_MACROS)

    for line in MACROS.strip().splitlines():
        name, value = line.split('\t')
        COMPILED_MACROS[name.strip()] = '(?:%s)' % expand_macros(value)

    del COMPILED_TOKENS[:]
    for line in TOKENS.strip().splitlines():
        name, value = line.split('\t')
        COMPILED_TOKENS.append((name.strip(), re.compile(
            expand_macros(value), re.I)))

_init()


def _unicode_replace(match):
    codepoint = int(match.group(1), 16)
    if codepoint <= sys.maxunicode:
        return unichr(codepoint)
    else:
        return '\N{REPLACEMENT CHARACTER}'  # U+FFFD

UNICODE_UNESCAPE = functools.partial(
    re.compile(COMPILED_MACROS['unicode'], re.I).sub,
    _unicode_replace)

NEWLINE_UNESCAPE = functools.partial(
    re.compile(r'\\' + COMPILED_MACROS['nl']).sub,
    '')

SIMPLE_UNESCAPE = functools.partial(
    re.compile(r'\\(.)').sub,
    r'\1')

FIND_NEWLINES = re.compile(COMPILED_MACROS['nl']).finditer


def tokenize(string, ignore_comments=True):
    """
    Take an unicode string and yield tokens as ``(type, value)`` tuples.

    All backslash-escapes are unescaped.

    Values are transformed:

    * For NUMBER or PERCENTAGE tokens: a parsed numeric value as a int or float.
    * For DIMENSION tokens: parsed as a ``(numeric_value, unit)`` tuple
    * For STRING tokens: the string without quotes
    * For URI tokens: the URI without quotes or ``url(`` and ``)`` markers.

    """
    # Make these local variable to avoid global lookups in the loop
    compiled_tokens = COMPILED_TOKENS
    unicode_unescape = UNICODE_UNESCAPE
    newline_unescape = NEWLINE_UNESCAPE
    simple_unescape = SIMPLE_UNESCAPE
    find_newlines = FIND_NEWLINES

    pos = 0
    line = 1
    column = 1
    len_string = len(string)
    while pos < len_string:
        # Find the longest match
        length = 0
        type_ = None
        for this_type, regexp in compiled_tokens:
            this_match = regexp.match(string, pos)
            if this_match is not None:
                this_value = this_match.group()
                this_length = len(this_value)
                if this_length > length:
                    match = this_match
                    type_ = this_type
                    css_value = this_value
                    length = this_length
        if not (ignore_comments and type_ == 'COMMENT'):
            if type_ is None:  # No match
                # "Any other character not matched by the above rules,
                #  and neither a single nor a double quote."
                # ... but quotes at the start of a token are always matched
                # by STRING or BADSTRING. So DELIM is any single character.
                type_ = 'DELIM'
                css_value = value = string[pos]
                length = 1
            else:
                # Parse number, extract strings and URIs, unescape
                if type_ in ('DIMENSION', 'PERCENTAGE', 'NUMBER'):
                    if type_ == 'PERCENTAGE':
                        value = css_value[:-1]
                    elif type_ == 'DIMENSION':
                        value = match.group(1)
                        unit = match.group(2)
                        unit = unicode_unescape(unit)
                        unit = simple_unescape(unit)
                    else: # NUMBER
                        value = css_value
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                    if type_ == 'DIMENSION':
                        value = value, unit
                elif type_ in ('IDENT', 'ATKEYWORD', 'HASH', 'FUNCTION'):
                    value = unicode_unescape(css_value)
                    value = simple_unescape(value)
                elif type_ == 'URI':
                    value = match.group(1)
                    if value and value[0] in '"\'':
                        value = value[1:-1]  # Remove quotes
                        value = newline_unescape(value)
                    value = unicode_unescape(value)
                    value = simple_unescape(value)
                elif type_ == 'STRING':
                    value = css_value[1:-1]  # Remove quotes
                    value = newline_unescape(value)
                    value = unicode_unescape(value)
                    value = simple_unescape(value)
                else:
                    value = css_value
            yield Token(type_, css_value, value, line, column)
        pos += length
        newlines = list(find_newlines(css_value))
        if newlines:
            line += len(newlines)
            # Have line start at column 1
            column = length - newlines[-1].end() + 1
        else:
            column += length



class Token(object):
    """A single atomic token"""
    def __init__(self, type_, css_value, value, line, column):
        self.type = type_
        self.as_css = css_value
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return self.format_string.format(self)

    # For debugging:
    pretty = __repr__
    format_string = '<Token {0.type} at {0.line}:{0.column} {0.value!r}>'
