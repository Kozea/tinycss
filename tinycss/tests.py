# coding: utf8
"""
    Test suite for tinycss
    ----------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from tinycss.tokenizer import tokenize


def test_tokenizer():
    assert list(tokenize('red -->')) == [
        ('IDENT', 'red'), ('S', ' '), ('CDC', '-->')]
    # Longest match rule:
    assert list(tokenize('red-->')) == [('IDENT', 'red--'), ('DELIM', '>')]
