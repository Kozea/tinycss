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

import functools
import string
import sys
import re


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
'''

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
        string.Formatter().vformat, args=(), kwargs=COMPILED_MACROS)

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

    pos = 0
    len_string = len(string)
    while pos < len_string:
        # Find the longest match
        length = 0
        for this_name, regexp in compiled_tokens:
            this_match = regexp.match(string, pos)
            if this_match is None:
                continue
            this_value = this_match.group()
            this_length = len(this_value)
            if this_length > length:
                match = this_match
                name = this_name
                value = this_value
                length = this_length
        if length == 0:  # No match
            # "Any other character not matched by the above rules,
            #  and neither a single nor a double quote."
            # ... but quotes at the start of a token are always matched
            # by STRING or BADSTRING. So DELIM is any single character.
            yield 'DELIM', string[pos]
            pos += 1
        else:
            pos += length
            if ignore_comments and name in ('COMMENT', 'BAD_COMMENT'):
                continue

            if name in ('DIMENSION', 'PERCENTAGE', 'NUMBER'):
                if name == 'PERCENTAGE':
                    value = value[:-1]
                elif name == 'DIMENSION':
                    value = match.group(1)
                    unit = match.group(2)
                    unit = unicode_unescape(unit)
                    unit = simple_unescape(unit)
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
                if name == 'DIMENSION':
                    value = value, unit
            elif name in ('IDENT', 'ATKEYWORD', 'HASH', 'FUNCTION'):
                value = unicode_unescape(value)
                value = simple_unescape(value)
            elif name == 'URI':
                value = match.group(1)
                if value and value[0] in '"\'':
                    value = value[1:-1]  # Remove quotes
                    value = newline_unescape(value)
                value = unicode_unescape(value)
                value = simple_unescape(value)
            elif name == 'STRING':
                value = value[1:-1]  # Remove quotes
                value = newline_unescape(value)
                value = unicode_unescape(value)
                value = simple_unescape(value)

            yield name, value
