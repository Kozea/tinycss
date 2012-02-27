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

# Removed these tokens. Instead, they’re tokenized as two DELIM each.
#    INCLUDES	~=
#    DASHMATCH	|=
# They are only used in selectors but selectors3 also have ^=, *= and $=.
# We don’t actually parse selectors anyway

# Re-ordered so that the longest match is always the first.
# For example, "url('foo')" matches URI, BAD_URI, FUNCTION and IDENT,
# but URI would always be a longer match than the others.
TOKENS = r'''
    S	[ \t\r\n\f]+

    URI	url\({w}({string}|([!#$%&*-\[\]-~]|{nonascii}|{escape})*){w}\)
    BAD_URI	{baduri}
    FUNCTION	{ident}\(
    UNICODE-RANGE	u\+[0-9a-f?]{{1,6}}(-[0-9a-f]{{1,6}})?
    IDENT	{ident}

    ATKEYWORD	@{ident}
    HASH	#{name}

    DIMENSION	({num})({ident})
    PERCENTAGE	{num}%
    NUMBER	{num}

    STRING	{string}
    BAD_STRING	{badstring}

    COMMENT	\/\*[^*]*\*+([^/*][^*]*\*+)*\/
    BAD_COMMENT	{badcomment}

    :	:
    ;	;
    {	\{{
    }	\}}
    (	\(
    )	\)
    [	\[
    ]	\]
    CDO	<!--
    CDC	-->
'''


# Strings with {macro} expanded
COMPILED_MACROS = {}

# match methods of re.RegexObject
COMPILED_TOKEN_REGEXPS = []  # ordered


def _init():
    """Import-time initialization."""
    COMPILED_MACROS.clear()
    expand_macros = functools.partial(
        Formatter().vformat, args=(), kwargs=COMPILED_MACROS)

    for line in MACROS.splitlines():
        if line.strip():
            name, value = line.split('\t')
            COMPILED_MACROS[name.strip()] = '(?:%s)' % expand_macros(value)

    del COMPILED_TOKEN_REGEXPS[:]
    for line in TOKENS.splitlines():
        if line.strip():
            name, value = line.split('\t')
            COMPILED_TOKEN_REGEXPS.append((
                name.strip(),
                re.compile(
                    expand_macros(value),
                    # Case-insensitive when matching eg. uRL(foo)
                    # but preserve the case in extracted groups
                    re.I
                ).match
            ))

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


def tokenize_flat(css_source, ignore_comments=True):
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
    compiled_token = COMPILED_TOKEN_REGEXPS
    unicode_unescape = UNICODE_UNESCAPE
    newline_unescape = NEWLINE_UNESCAPE
    simple_unescape = SIMPLE_UNESCAPE
    find_newlines = FIND_NEWLINES

    pos = 0
    line = 1
    column = 1
    source_len = len(css_source)
    while pos < source_len:
        for type_, regexp in compiled_token:
            match = regexp(css_source, pos)
            if match is not None:
                # First match is the longest. See comments on TOKENS above.
                css_value = match.group()
                break
        else:
            # No match.
            # "Any other character not matched by the above rules,
            #  and neither a single nor a double quote."
            # ... but quotes at the start of a token are always matched
            # by STRING or BAD_STRING. So DELIM is any single character.
            type_ = 'DELIM'
            css_value = css_source[pos]
        length = len(css_value)
        next_pos = pos + length

        # A BAD_COMMENT is a comment at EOF. Ignore it too.
        if not (ignore_comments and type_ in ('COMMENT', 'BAD_COMMENT')):
            # Parse numbers, extract strings and URIs, unescape
            unit = None
            if type_ == 'DIMENSION':
                value = match.group(1)
                value = float(value) if '.' in value else int(value)
                unit = match.group(2)
                unit = unicode_unescape(unit)
                unit = simple_unescape(unit)
                unit = unit.lower()  # normalize
            elif type_ == 'PERCENTAGE':
                value = css_value[:-1]
                value = float(value) if '.' in value else int(value)
                unit = '%'
            elif type_ == 'NUMBER':
                value = css_value
                value = float(value) if '.' in value else int(value)
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
            # BAD_STRING can only be one of:
            # * Unclosed string at the end of the stylesheet:
            #   Close the string, but this is not an error.
            #   Make it a "good" STRING token.
            # * Unclosed string at the (unescaped) end of the line:
            #   Close the string, but this is an error.
            #   Leave it as a BAD_STRING, don’t bother parsing it.
            # See http://www.w3.org/TR/CSS21/syndata.html#parsing-errors
            elif type_ == 'BAD_STRING' and next_pos == source_len:
                type_ = 'STRING'
                value = css_value[1:]  # Remove quote
                value = newline_unescape(value)
                value = unicode_unescape(value)
                value = simple_unescape(value)
            else:
                value = css_value
            yield Token(type_, css_value, value, unit, line, column)

        pos = next_pos
        newlines = list(find_newlines(css_value))
        if newlines:
            line += len(newlines)
            # Add 1 to have lines start at column 1, not 0
            column = length - newlines[-1].end() + 1
        else:
            column += length


def regroup(tokens):
    """
    Match pairs of tokens: () [] {} function()
    (Strings in "" or '' are taken care of by the tokenizer.)

    Opening tokens are replaced by a :class:`ContainerToken`.
    Closing tokens are removed. Unmatched closing tokens are invalid
    but left as-is. All nested structures that are still open at
    the end of the stylesheet are implicitly closed.

    :param tokens:
        a *flat* iterable of tokens, as returned by :func:`tokenize_flat`.
    :return:
        A tree of tokens.

    """
    # "global" objects for the inner recursion
    pairs = {'FUNCTION': ')', '(': ')', '[': ']', '{': '}'}
    tokens = iter(tokens)
    eof = [False]

    def _regroup_inner(stop_at=None, tokens=tokens, pairs=pairs, eof=eof):
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
                content = list(_regroup_inner(end))
                if eof[0]:
                    end = ''  # Implicit end of structure at EOF.
                if type_ == 'FUNCTION':
                    yield FunctionToken(token.type, token.as_css, end,
                                        token.value, content,
                                        token.line, token.column)
                else:
                    yield ContainerToken(token.type, token.as_css, end,
                                         content,
                                         token.line, token.column)
        else:
            eof[0] = True  # end of file/stylesheet
    return _regroup_inner()


def tokenize_grouped(css_source, ignore_comments=True):
    """
    :param css_source:
        CSS as an unicode string
    :param ignore_comments:
        if true (the default) comments will not be included in the
        return value
    :return:
        An iterator of :class:`Token`

    """
    return regroup(tokenize_flat(css_source, ignore_comments))


class Token(object):
    """A single atomic token.

    .. attribute:: is_container
        Always ``False``.
        Helps to tell :class:`Token` apart from :class:`ContainerToken`.

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
    is_container = False

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


class ContainerToken(object):
    """A token that contains other (nested) tokens.

    .. attribute:: is_container
        Always ``True``.
        Helps to tell :class:`ContainerToken` apart from :class:`Token`.

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
    is_container = True

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

    def __repr__(self):  # pragma: no cover
        return (self.format_string + ' {0.content}').format(self)

    def pretty(self):  # pragma: no cover
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
