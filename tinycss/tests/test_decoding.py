# coding: utf8
"""
    Tests for decoding bytes to Unicode
    -----------------------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals

import pytest

from tinycss.decoding import decode


def params(css, encoding, use_bom=False, expect_error=False, **kwargs):
    """Nicer syntax to make a tuple."""
    return css, encoding, use_bom, expect_error, kwargs


@pytest.mark.parametrize(('css', 'encoding', 'use_bom', 'expect_error',
                          'kwargs'), [
    params('𐂃', 'utf8'),
    params('é', 'latin1', expect_error=True),
    params('@charset "ISO-8859-1"; é', 'latin1'),
    params('@charset "ISO-8859-8"; é', 'latin1', expect_error=True),
    params('𐂃', 'utf-16-le', expect_error=True),  # no BOM
    params('𐂃', 'utf-16-le', use_bom=True),
    params('𐂃', 'utf-32-be', expect_error=True),
    params('𐂃', 'utf-32-be', use_bom=True),
    params('𐂃', 'utf-32-be', document_encoding='utf-32-be'),
    params('𐂃', 'utf-32-be', linking_encoding='utf-32-be'),
    params('@charset "utf-32-le"; 𐂃', 'utf-32-be',
           use_bom=True, expect_error=True),
    # protocol_encoding takes precedence over @charset
    params('@charset "ISO-8859-8"; é', 'latin1',
           protocol_encoding='ISO-8859-1'),
    # @charset takes precedence over document_encoding
    params('@charset "ISO-8859-1"; é', 'latin1',
           document_encoding='ISO-8859-8'),
    # @charset takes precedence over linking_encoding
    params('@charset "ISO-8859-1"; é', 'latin1',
           linking_encoding='ISO-8859-8'),
    # linking_encoding takes precedence over document_encoding
    params('é', 'latin1',
           linking_encoding='ISO-8859-1', document_encoding='ISO-8859-8'),
])
def test_decode(css, encoding, use_bom, expect_error, kwargs):
    if use_bom:
        source = '\ufeff' + css
    else:
        source = css
    css_bytes = source.encode(encoding)
    try:
        result = decode(css_bytes, **kwargs)
    except UnicodeDecodeError as exc:
        result = exc
    if expect_error:
        assert result != css, 'Unexpected unicode success'
    else:
        print(result, css, result == css, map(ord, result), map(ord, css))
        assert result == css, 'Unexpected unicode error'
