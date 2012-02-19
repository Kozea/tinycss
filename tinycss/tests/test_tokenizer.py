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
def test_tokenizer(input_css, expected_tokens):
    tokens = tokenize(input_css, ignore_comments=False)
    result = [(token.type, token.value) for token in tokens]
    assert result == expected_tokens
