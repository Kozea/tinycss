# coding: utf8
"""
    Test suite for tinycss
    ----------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import pytest

from tinycss.tokenizer import tokenize_flat, tokenize_grouped


@pytest.mark.parametrize(('css_source', 'expected_tokens'), [
    ('', []),
    ('red -->',
        [('IDENT', 'red'), ('S', ' '), ('CDC', '-->')]),
    # Longest match rule: no CDC
    ('red-->',
        [('IDENT', 'red--'), ('DELIM', '>')]),

    (r'''p[example="\
foo(int x) {\
    this.x = x;\
}\
"]''', [
        ('IDENT', 'p'),
        ('[', '['),
        ('IDENT', 'example'),
        ('DELIM', '='),
        ('STRING', 'foo(int x) {    this.x = x;}'),
        (']', ']')]),

    #### Numbers are parsed
    ('42 -4pX 1.25em 30%',
        [('NUMBER', 42), ('S', ' '),
         # units are normalized to lower-case:
         ('DIMENSION', -4, 'px'), ('S', ' '),
         ('DIMENSION', 1.25, 'em'), ('S', ' '),
         ('PERCENTAGE', 30, '%')]),

    #### URLs are extracted
    ('url(foo.png)', [('URI', 'foo.png')]),
    ('url("foo.png")', [('URI', 'foo.png')]),

    #### Escaping

    (r'/* Comment with a \ backslash */',
        [('COMMENT', '/* Comment with a \ backslash */')]),  # Unchanged

    # backslash followed by a newline in a string: ignored
    ('"Lorem\\\nIpsum"', [('STRING', 'LoremIpsum')]),

    # backslash followed by a newline outside a string: stands for itself
    ('Lorem\\\nIpsum',
        [('IDENT', 'Lorem'), ('DELIM', '\\'), ('S', '\n'), ('IDENT', 'Ipsum')]),

    # Cancel the meaning of special characters
    (r'"Lore\m Ipsum"', [('STRING', 'Lorem Ipsum')]),  # or not specal
    (r'"Lorem\"Ipsum"', [('STRING', 'Lorem"Ipsum')]),
    (r'Lorem\+Ipsum', [('IDENT', 'Lorem+Ipsum')]),
    (r'Lorem+Ipsum', [('IDENT', 'Lorem'), ('DELIM', '+'), ('IDENT', 'Ipsum')]),
    (r'url(foo\).png)', [('URI', 'foo).png')]),

    # Unicode
    ('\\26 B', [('IDENT', '&B')]),
    ('@\\26\tB', [('ATKEYWORD', '@&B')]),
    ('#\\26\nB', [('HASH', '#&B')]),
    ('\\26\r\nB(', [('FUNCTION', '&B(')]),
    (r'12.5\000026B', [('DIMENSION', 12.5, '&b')]),
    (r'12.5\0000263B', [('DIMENSION', 12.5, '&3b')]),  # max 6 digits
    (r'"\26 B"', [('STRING', '&B')]),
    (r"'\000026B'", [('STRING', '&B')]),
    (r'url("\26 B")', [('URI', '&B')]),
    (r'url(\26 B)', [('URI', '&B')]),
    (r'Lorem\110000Ipsum', [('IDENT', 'Lorem\uFFFDIpsum')]),

    #### Bad strings

    # String ends at EOF without closing: no error, parsed
    ('"Lorem\\26Ipsum', [('STRING', 'Lorem&Ipsum')]),
    # Unescaped newline: ends the string, error, unparsed
    ('"Lorem\\26Ipsum\n', [
        ('BAD_STRING', r'"Lorem\26Ipsum'), ('S', '\n')]),
    # Tokenization restarts after the newline, so the second " starts
    # a new string (which ends at EOF without errors, as above.)
    ('"Lorem\\26Ipsum\ndolor" sit', [
        ('BAD_STRING', r'"Lorem\26Ipsum'), ('S', '\n'),
        ('IDENT', 'dolor'), ('STRING', ' sit')]),

])
def test_tokens(css_source, expected_tokens):
    tokens = tokenize_flat(css_source, ignore_comments=False)
    result = [
        (token.type, token.value) + (
            () if token.unit is None else (token.unit,))
        for token in tokens
    ]
    assert result == expected_tokens


def test_positions():
    """Test the reported line/column position of each token."""
    css = '/* Lorem\nipsum */\fa {\n    color: red;\tcontent: "dolor\\\fsit" }'
    tokens = tokenize_flat(css, ignore_comments=False)
    result = [(token.type, token.line, token.column) for token in tokens]
    assert result == [
        (u'COMMENT', 1, 1), (u'S', 2, 9),
        (u'IDENT', 3, 1), (u'S', 3, 2), (u'{', 3, 3),
        (u'S', 3, 4), (u'IDENT', 4, 5), (u':', 4, 10),
        (u'S', 4, 11), (u'IDENT', 4, 12), (u';', 4, 15), (u'S', 4, 16),
        (u'IDENT', 4, 17), (u':', 4, 24), (u'S', 4, 25), (u'STRING', 4, 26),
        (u'S', 5, 5), (u'}', 5, 6)]


@pytest.mark.parametrize(('css_source', 'expected_tokens'), [
    ('', []),
    (r'Lorem\26 "i\psum"4px', [
        ('IDENT', 'Lorem&'), ('STRING', 'ipsum'), ('DIMENSION', 4)]),

    ('not([[lorem]]{ipsum (42)})', [
        ('FUNCTION', 'not', [
            ('[', [
                ('[', [
                    ('IDENT', 'lorem'),
                ]),
            ]),
            ('{', [
                ('IDENT', 'ipsum'),
                ('S', ' '),
                ('(', [
                    ('NUMBER', 42),
                ])
            ])
        ])]),

    # Close everything at EOF, no error
    ('a[b{"d', [
        ('IDENT', 'a'),
        ('[', [
            ('IDENT', 'b'),
            ('{', [
                ('STRING', 'd'),
            ]),
        ]),
    ]),

    # Any remaining ), ] or } token is a nesting error
    ('a[b{d]e}', [
        ('IDENT', 'a'),
        ('[', [
            ('IDENT', 'b'),
            ('{', [
                ('IDENT', 'd'),
                (']', ']'),  # The error is visible here
                ('IDENT', 'e'),
            ]),
        ]),
    ]),
    # ref:
    ('a[b{d}e]', [
        ('IDENT', 'a'),
        ('[', [
            ('IDENT', 'b'),
            ('{', [
                ('IDENT', 'd'),
            ]),
            ('IDENT', 'e'),
        ]),
    ]),
])
def test_token_grouping(css_source, expected_tokens):
    tokens = tokenize_grouped(css_source, ignore_comments=False)
    result = list(jsonify(tokens))
    assert result == expected_tokens


def jsonify(tokens):
    """Turn tokens into "JSON-compatible" data structures."""
    for token in tokens:
        if token.type == 'FUNCTION':
            yield (token.type, token.function_name,
                   list(jsonify(token.content)))
        elif token.is_container:
            yield token.type, list(jsonify(token.content))
        else:
            yield token.type, token.value


@pytest.mark.parametrize(('ignore_comments', 'expected_tokens'), [
    (False, [
        ('COMMENT', '/* lorem */'),
        ('S', ' '),
        ('IDENT', 'ipsum'),
        ('[', [
            ('IDENT', 'dolor'),
            ('COMMENT', '/* sit */'),
        ]),
        ('BAD_COMMENT', '/* amet')
    ]),
    (True, [
        ('S', ' '),
        ('IDENT', 'ipsum'),
        ('[', [
            ('IDENT', 'dolor'),
        ]),
    ]),
])
def test_comments(ignore_comments, expected_tokens):
    css_source = '/* lorem */ ipsum[dolor/* sit */]/* amet'
    tokens = tokenize_grouped(css_source, ignore_comments)
    result = list(jsonify(tokens))
    assert result == expected_tokens


@pytest.mark.parametrize('css_source', [
    r'''p[example="\
foo(int x) {\
    this.x = x;\
}\
"]''',
    '"Lorem\\26Ipsum\ndolor" sit',
    '/* Lorem\nipsum */\fa {\n    color: red;\tcontent: "dolor\\\fsit" }',
    'not([[lorem]]{ipsum (42)})',
    'a[b{d]e}',
    'a[b{"d',
])
def test_token_serialize_css(css_source):
    for tokenize in [tokenize_flat, tokenize_grouped]:
        tokens = tokenize(css_source, ignore_comments=False)
        result = ''.join(token.as_css for token in tokens)
        assert result == css_source
