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
import re


# Syntax: {} are used for macro substitution with string.Formatter,
# so other uses of { or } must be doubled. Everything else is re.compile
# syntax.
MACROS = [
    # Re-ordered so that only earlier definitions are needed.
    ('nl', '\\n|\\r\\n|\\r|\\f'),
    ('w', '[ \\t\\r\\n\\f]*'),
    ('nonascii', '[^\0-\237]'),
    ('unicode', '\\\\[0-9a-f]{{1,6}}(\\r\\n|[ \\n\\r\\t\\f])?'),
    ('escape', '{unicode}|\\\\[^\\n\\r\\f0-9a-f]'),
    ('nmstart', '[_a-z]|{nonascii}|{escape}'),
    ('nmchar', '[_a-z0-9-]|{nonascii}|{escape}'),
    ('name', '{nmchar}+'),
    ('ident', '[-]?{nmstart}{nmchar}*'),
    ('num', '[0-9]+|[0-9]*\\.[0-9]+'),
    ('string1', '\\"([^\\n\\r\\f\\\\"]|\\\\{nl}|{escape})*\\"'),
    ('string2', "\\'([^\\n\\r\\f\\\\']|\\\\{nl}|{escape})*\\'"),
    ('string', '{string1}|{string2}'),
    ('badstring1', '\\"([^\\n\\r\\f\\\\"]|\\\\{nl}|{escape})*\\\\?'),
    ('badstring2', "\\'([^\\n\\r\\f\\\\']|\\\\{nl}|{escape})*\\\\?"),
    ('badstring', '{badstring1}|{badstring2}'),
    ('badcomment1', '\\/\\*[^*]*\\*+([^/*][^*]*\\*+)*'),
    ('badcomment2', '\\/\\*[^*]*(\\*+[^/*][^*]*)*'),
    ('badcomment', '{badcomment1}|{badcomment2}'),
    ('baduri1', 'url\\({w}([!#$%&*-~]|{nonascii}|{escape})*{w}'),
    ('baduri2', 'url\\({w}{string}{w}'),
    ('baduri3', 'url\\({w}{badstring}'),
    ('baduri', '{baduri1}|{baduri2}|{baduri3}'),
]

TOKENS = [
    ('IDENT', '{ident}'),
    ('ATKEYWORD', '@{ident}'),
    ('STRING', '{string}'),
    ('BAD_STRING', '{badstring}'),
    ('BAD_URI', '{baduri}'),
    ('BAD_COMMENT', '{badcomment}'),
    ('HASH', '#{name}'),
    ('NUMBER', '{num}'),
    ('PERCENTAGE', '{num}%'),
    ('DIMENSION', '{num}{ident}'),
    ('URI', 'url\\({w}{string}{w}\\)|'
            'url\\({w}([!#$%&*-\\[\\]-~]|{nonascii}|{escape})*{w}\\)',),
    ('UNICODE-RANGE', 'u\\+[0-9a-f?]{{1,6}}(-[0-9a-f]{{1,6}})?'),
    ('CDO', '<!--'),
    ('CDC', '-->'),
    (':', ':'),
    (';', ';'),
    ('{', '\\{{'),
    ('}', '\\}}'),
    ('(', '\\('),
    (')', '\\)'),
    ('[', '\\['),
    (']', '\\]'),
    ('S', '[ \t\r\n\f]+'),
    ('COMMENT', '\\/\\*[^*]*\\*+([^/*][^*]*\\*+)*\\/'),
    ('FUNCTION', '{ident}\\('),
    ('INCLUDES', '~='),
    ('DASHMATCH', '|='),
]

COMPILED_TOKENS = []  # ordered


def _init():
    """Import-time initialization."""
    compiled_macros = {}
    expand_macros = functools.partial(
        string.Formatter().vformat, args=(), kwargs=compiled_macros)
    for name, macro in MACROS:
        compiled_macros[name] = '(?:%s)' % expand_macros(macro)
    del COMPILED_TOKENS[:]
    for name, token in TOKENS:
        COMPILED_TOKENS.append((name, re.compile(expand_macros(token))))
_init()


def tokenize(string, ignore_comments=True):
    """Take an unicode string and yield tokens as ``(type, value)`` tuples."""
    pos = 0
    len_string = len(string)
    tokens = COMPILED_TOKENS
    while pos < len_string:
        # Find the longest match
        candidate_len = 0
        for name, regexp in tokens:
            match = regexp.match(string, pos)
            if match is None:
                continue
            this_value = match.group()
            this_len = len(this_value)
            if this_len > candidate_len:
                candidate_name = name
                candidate_value = this_value
                candidate_len = this_len
        if candidate_len == 0:
            # "Any other character not matched by the above rules,
            #  and neither a single nor a double quote."
            # ... but quotes at the start of a token are always matched
            # by STRING or BADSTRING. So DELIM is any single character.
            yield 'DELIM', string[pos]
            pos += 1
        else:
            pos += candidate_len
            if not (
                ignore_comments and
                candidate_name in ('COMMENT', 'BAD_COMMENT')
            ):
                yield candidate_name, candidate_value
