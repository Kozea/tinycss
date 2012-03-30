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
import operator
import functools


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


COMPILED_TOKEN_REGEXPS = []  # [(name, regexp.match)]  ordered
COMPILED_TOKEN_INDEXES = {}  # {name: i}  helper for the C speedups


def _init():
    """Import-time initialization."""
    COMPILED_MACROS.clear()
    # Formatter is broken on PyPy: https://bugs.pypy.org/issue1081
#    expand_macros = functools.partial(
#        Formatter().vformat, args=(), kwargs=COMPILED_MACROS)

    for line in MACROS.splitlines():
        if line.strip():
            name, value = line.split('\t')
            COMPILED_MACROS[name.strip()] = '(?:%s)' \
                % value.format(**COMPILED_MACROS)

    del COMPILED_TOKEN_REGEXPS[:]
    for line in TOKENS.splitlines():
        if line.strip():
            name, value = line.split('\t')
            COMPILED_TOKEN_REGEXPS.append((
                name.strip(),
                re.compile(
                    value.format(**COMPILED_MACROS),
                    # Case-insensitive when matching eg. uRL(foo)
                    # but preserve the case in extracted groups
                    re.I
                ).match
            ))

    COMPILED_TOKEN_INDEXES.clear()
    for i, (name, regexp) in enumerate(COMPILED_TOKEN_REGEXPS):
        COMPILED_TOKEN_INDEXES[name] = i

_init()


try:
    unichr
except NameError:  # pragma: no cover
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
    re.compile(COMPILED_MACROS['unicode'], re.I).sub,
    _unicode_replace)

NEWLINE_UNESCAPE = functools.partial(
    re.compile(r'()\\' + COMPILED_MACROS['nl']).sub,
    '')

SIMPLE_UNESCAPE = functools.partial(
    re.compile(r'\\(.)').sub,
    # Same as r'\1', but faster on CPython
    operator.methodcaller('group', 1))

FIND_NEWLINES = re.compile(COMPILED_MACROS['nl']).finditer


class Token(object):
    """A single atomic token.

    .. attribute:: is_container

        Always ``False``.
        Helps to tell :class:`Token` apart from :class:`ContainerToken`.

    .. attribute:: type

        The type of token as a string:

        ``S``
            A sequence of white space

        ``IDENT``
            An identifier: a name that does not start with a digit.
            A name is a sequence of letters, digits, escaped characters
            and non-ASCII characters. Eg: ``margin-left``

        ``HASH``
            ``#`` followed immediately by a name. Eg: ``#ff8800``

        ``ATKEYWORD``
            ``@`` followed immediately by an identifier. Eg: ``@page``

        ``URI``
            Eg: ``url(foo)`` The content may or may not be quoted.

        ``UNICODE-RANGE``
            ``U+`` followed by one or two hexadecimal
            Unicode codepoints. Eg: ``U+20-00FF``

        ``INTEGER``
            An integer with an optional ``+`` or ``-`` sign

        ``NUMBER``
            A non-integer number  with an optional ``+`` or ``-`` sign

        ``DIMENSION``
            An integer or number followed immediately by an
            identifier (the unit). Eg: ``12px``

        ``PERCENTAGE``
            An integer or number followed immediately by ``%``

        ``STRING``
            A string, quoted with ``"`` or ``'``

        ``:`` or ``;``
            That character.

        ``DELIM``
            A single character not matched in another token. Eg: ``,``

        Note that other token types exist in the early tokenization steps,
        but these are ignored, are syntax errors, or are later transformed
        into :class:`ContainerToken` or :class:`FunctionToken`.

    .. attribute:: as_css

        The string as it was read from the CSS source

    .. attribute:: value

        The parsed value:

        * INTEGER, NUMBER, PERCENTAGE or DIMENSION tokens: the numeric value
          as an int or float.
        * STRING tokens: the unescaped string without quotes
        * URI tokens: the unescaped URI without quotes or
          ``url(`` and ``)`` markers.
        * IDENT, ATKEYWORD or HASH tokens: the unescaped token,
          with ``@`` or ``#`` markers left as-is
        * Other tokens: same as :attr:`as_css`

        *Unescaped* refers to the various escaping methods based on the
        backslash ``\`` character in CSS syntax.

    .. attribute:: unit

        * DIMENSION tokens: the normalized (unescaped, lower-case)
          unit name as a string. eg. ``'px'``
        * PERCENTAGE tokens: the string ``'%'``
        * Other tokens: ``None``

    .. attribute:: line

        The line number of this token in the CSS source

    .. attribute:: column

        The column number inside a line of this token in the CSS source

    """
    is_container = False
    __slots__ = 'type', 'as_css', 'value', 'unit', 'line', 'column'

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

        The type of token as a string. One of ``{``, ``(``, ``[`` or
        ``FUNCTION``. For ``FUNCTION``, the object is actually a
        :class:`FunctionToken`.

    .. attribute:: css_start

        The string for the opening token as it was read from the CSS source.
        Eg: ``{``

    .. attribute:: css_end

        The string for the closing token as it was read from the CSS source
        Eg: ``}``

    .. attribute:: content

        A list of :class:`Token` or nested :class:`ContainerToken`,
        not including the opening or closing token.

    .. attribute:: line

        The line number of the opening token in the CSS source

    .. attribute:: column

        The column number inside a line of the opening token in the CSS source

    """
    is_container = True
    __slots__ = 'type', 'css_start', 'css_end', 'content', 'line', 'column'

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

    # Sequence-like API (not the full collections.Sequence ABC, though)

    def __iter__(self):
        return iter(self.content)

    def __len__(self):
        return len(self.content)


class FunctionToken(ContainerToken):
    """A specialized :class:`ContainerToken` for a ``FUNCTION`` group.
    Has an additional attribute:

    .. attribute:: function_name

        The unescaped name of the function, with the ``(`` marker removed.

    """
    __slots__ = 'function_name',

    def __init__(self, type_, css_start, css_end, function_name, content,
                 line, column):
        super(FunctionToken, self).__init__(
            type_, css_start, css_end, content, line, column)
        # Remove the ( marker:
        self.function_name = function_name[:-1]

    format_string = ('<FunctionToken {0.function_name}() at '
                     '{0.line}:{0.column}>')
