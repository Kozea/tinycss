# coding: utf8
"""
    Test suite for tinycss
    ----------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import pytest
from tinycss.tokenizer import tokenize


@pytest.mark.parametrize(('input_css', 'expected_tokens'), [
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
    ('42 -4px 1.25em 30%',
        [('NUMBER', 42), ('S', ' '),
         ('DIMENSION', (-4, 'px')), ('S', ' '),
         ('DIMENSION', (1.25, 'em')), ('S', ' '),
         ('PERCENTAGE', 30)]),

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

    # Cancel the meaning of sepcial characters
    (r'"Lorem\"Ipsum"', [('STRING', 'Lorem"Ipsum')]),
    (r'Lorem\+Ipsum', [('IDENT', 'Lorem+Ipsum')]),
    (r'Lorem+Ipsum', [('IDENT', 'Lorem'), ('DELIM', '+'), ('IDENT', 'Ipsum')]),
    (r'url(foo\).png)', [('URI', 'foo).png')]),

    # Unicode
    (r'#\26 B', [('HASH', '#&B')]),
    (r'12.5\000026B', [('DIMENSION', (12.5, '&B'))]),
    (r'"\26 B"', [('STRING', '&B')]),
    (r"'\000026B'", [('STRING', '&B')]),
    (r'url("\26 B")', [('URI', '&B')]),
    (r'url(\26 B)', [('URI', '&B')]),
    (r'Lorem\110000Ipsum', [('IDENT', 'Lorem\uFFFDIpsum')]),

])
def test_tokens(input_css, expected_tokens):
    tokens = tokenize(input_css, ignore_comments=False)
    result = [(token.type, token.value) for token in tokens]
    assert result == expected_tokens


def test_positions():
    """Test the reported line/column position of each token."""
    css = '/* Lorem\nipsum */\fa {\n    color: red;\tcontent: "dolor\\\fsit" }'
    tokens = tokenize(css, ignore_comments=False)
    result = [(token.type, token.line, token.column) for token in tokens]
    assert result == [
        (u'COMMENT', 1, 1), (u'S', 2, 9),
        (u'IDENT', 3, 1), (u'S', 3, 2), (u'{', 3, 3),
        (u'S', 3, 4), (u'IDENT', 4, 5), (u':', 4, 10),
        (u'S', 4, 11), (u'IDENT', 4, 12), (u';', 4, 15), (u'S', 4, 16),
        (u'IDENT', 4, 17), (u':', 4, 24), (u'S', 4, 25), (u'STRING', 4, 26),
        (u'S', 5, 5), (u'}', 5, 6)]
