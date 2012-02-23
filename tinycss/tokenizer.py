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
            expand_macros(value),
            # Case-insensitive when matching eg. uRL(foo)
            # but preserve the case in extracted groups
            re.I)))

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


def tokenize_flat(string, ignore_comments=True):
    """
    :param string:
        CSS as an unicode string
    :param ignore_comments:
        if true (the default) comments will not be included in the
        return value
    :return:
        An iterator of :class:`Token`

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
                # Parse numbers, extract strings and URIs, unescape
                unit = None
                if type_ in ('DIMENSION', 'PERCENTAGE', 'NUMBER'):
                    if type_ == 'PERCENTAGE':
                        value = css_value[:-1]
                        unit = '%'
                    elif type_ == 'DIMENSION':
                        value = match.group(1)
                        unit = match.group(2)
                        unit = unicode_unescape(unit)
                        unit = simple_unescape(unit)
                        unit = unit.lower()
                    else: # NUMBER
                        value = css_value
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
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
            yield Token(type_, css_value, value, unit, line, column)
        pos += length
        newlines = list(find_newlines(css_value))
        if newlines:
            line += len(newlines)
            # Have line start at column 1
            column = length - newlines[-1].end() + 1
        else:
            column += length


def regroup(tokens, stop_at=None):
    """
    Match pairs of tokens: () [] {} function()
    (Strings in "" or '' are taken care of by the tokenizer.)

    Opening tokens are replaced by a :class:`ContainerToken`.
    Closing tokens are removed. Unmatched closing tokens are invalid
    but left as-is. All nested structures that are still open at
    the end of the stylesheet are implicitly closed.

    :param tokens:
        a *flat* iterator of tokens, as returned by :func:`tokenize_flat`.
        Needs to be an iterator that can be consumed little by little,
        not any iterable.
    :param stop_at:
        only used for recursion
    :return:
        A tree of tokens.

    """
    pairs = {'FUNCTION': ')', '(': ')', '[': ']', '{': '}'}
    for token in tokens:
        assert not hasattr(token, 'content'), (
            'Token looks already grouped: {0}'.format(token))
        type_ = token.type
        if type_ == stop_at:
            return

        end = pairs.get(type_)
        if end is None:
            yield token  # Not a grouping token
        else:
            content = list(regroup(tokens, end))
            if type_ == 'FUNCTION':
                yield FunctionToken(token.type, token.as_css, end,
                                    token.value, content,
                                    token.line, token.column)
            else:
                yield ContainerToken(token.type, token.as_css, end,
                                     content,
                                     token.line, token.column)


def tokenize_grouped(string, ignore_comments=True):
    """
    :param string:
        CSS as an unicode string
    :param ignore_comments:
        if true (the default) comments will not be included in the
        return value
    :return:
        An iterator of :class:`Token`

    """
    return regroup(tokenize_flat(string, ignore_comments))


class Token(object):
    """A single atomic token.

    .. attribute:: type
        The type of token as a string. eg. 'IDENT'

    .. attribute:: as_css
        The string as it was read from the CSS source

    .. attribute:: value
        The parsed value:

        * All backslash-escapes are unescaped.
        * NUMBER, PERCENTAGE or DIMENSION tokens: the numeric value
          as an int or float.
        * STRING tokens: the unescaped string without quotes
        * URI tokens: the unescaped URI without quotes or
          ``url(`` and ``)`` markers.
        * IDENT, ATKEYWORD, HASH or FUNCTION tokens: the unescaped token,
          with ``@``, ``#`` or ``(`` markers left as-is
        * Other tokens: same as :attr:`as_css`

    .. attribute:: unit
        * DIMENSION tokens: the normalized (unescaped, lower-case)
          unit name as a string. eg. 'px'
        * PERCENTAGE tokens: the string '%'
        * Other tokens: ``None``

    .. attribute:: line
        The line number of this token in the CSS source

    .. attribute:: column
        The column number inside a line of this token in the CSS source

    """
    def __init__(self, type_, css_value, value, unit, line, column):
        self.type = type_
        self.as_css = css_value
        self.value = value
        self.unit = unit
        self.line = line
        self.column = column

    def __repr__(self):
        return ('<Token {0.type} at {0.line}:{0.column} {0.value!r}{1}>'
                .format(self, self.unit or ''))

    # For debugging:
    pretty = __repr__


class ContainerToken(object):
    """A token that contains other (nested) tokens.

    .. attribute:: type
        The type of token as a string. eg. 'IDENT'

    .. attribute:: css_start
        The string for the opening token as it was read from the CSS source

    .. attribute:: css_end
        The string for the closing token as it was read from the CSS source

    .. attribute:: content
        A list of :class:`Token` or nested :class:`ContainerToken`

    .. attribute:: line
        The line number of the opening token in the CSS source

    .. attribute:: column
        The column number inside a line of the opening token in the CSS source

    """
    def __init__(self, type_, css_start, css_end, content, line, column):
        self.type = type_
        self.css_start = css_start
        self.css_end = css_end
        self.content = content
        self.line = line
        self.column = column

    @property
    def as_css(self):
        """The (recursive) CSS representation of the token,
        as parsed in the source.
        """
        parts = [self.css_start]
        parts.extend(token.as_css for token in self.content)
        parts.append(self.css_end)
        return ''.join(parts)


    format_string = '<ContainerToken {0.type} at {0.line}:{0.column}>'

    def __repr__(self):
        return (format_string + ' {0.content}').format(self)

    def pretty(self):
        """Return an indented string representation for debugging"""
        lines = [self.format_string.format(self)]
        for token in self.content:
            for line in token.pretty().splitlines():
                lines.append('    ' + line)
        return '\n'.join(lines)


class FunctionToken(ContainerToken):
    """A :class:`ContainerToken` for a FUNCTION group.
    Has an additional attribute:

    .. attribute:: function_name
        The unescaped name of the function, with the ``(`` marker removed.

    """
    def __init__(self, type_, css_start, css_end, function_name, content,
                 line, column):
        super(FunctionToken, self).__init__(
            type_, css_start, css_end, content, line, column)
        # Remove the ( marker:
        self.function_name = function_name[:-1]

    format_string = '<FunctionToken {0.function_name}() at {0.line}:{0.column}>'
