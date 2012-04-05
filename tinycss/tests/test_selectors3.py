# coding: utf8
"""
    Tests for the Selectors 3 helpers
    ---------------------------------

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import os

import pytest

from . import assert_errors

try:
    import lxml.cssselect
except ImportError:
    LXML_INSTALLED = False
else:
    LXML_INSTALLED = True
    from tinycss.selectors3 import (
        Selector, InvalidSelectorError, CSSSelectors3Parser,
        parse_selector_string, parse_selector_group_string)


def test_lxml():
    if os.environ.get('TINYCSS_SKIP_LXML_TESTS'):  # pragma: no cover
        return
    assert LXML_INSTALLED, (
        'lxml is not not installed, related tests will be skipped. '
        'Set the TINYCSS_SKIP_LXML_TESTS environment variable '
        'if this is expected (eg. on PyPy).')


@pytest.mark.parametrize(('css_source', 'expected_num_selectors',
                          'expected_errors'), [
    ('', [], []),
    ('foo {}  bar, baz {}', [1, 2], []),
    ('foo, {}  bar, baz {}  a>b.c:empty,d,[e="f,g"]{}',
        [2, 3], ['empty selector']),
    (' {}', [], ['empty selector']),
    ('foo > {}', [], ["Expected selector, got 'None'"]),
])
def test_parser(css_source, expected_num_selectors, expected_errors):
    if not LXML_INSTALLED:  # pragma: no cover
        pytest.skip('lxml not available')
    stylesheet = CSSSelectors3Parser().parse_stylesheet(css_source)
    assert_errors(stylesheet.errors, expected_errors)

    result = []
    for rule in stylesheet.rules:
        for selector in rule.selector_list:
            assert isinstance(selector, Selector)
        result.append(len(rule.selector_list))
    assert result == expected_num_selectors


@pytest.mark.parametrize(('css_source', 'expected_result'), [
    (' ', None),
    ('foo, ', None),
    ('foo> ', None),
    ('input:enabled', None),  # not applicable in cssselect
    ('*:first-of-type', None),  # not supported yet by cssselect
    ('* ', ((0, 0, 0, 0), None)),
    (' foo', ((0, 0, 0, 1), None)),
    (':empty ', ((0, 0, 1, 0), None)),
    (':before', ((0, 0, 0, 1), 'before')),
    ('*:before', ((0, 0, 0, 1), 'before')),
    (':nth-child(2)', ((0, 0, 1, 0), None)),
    ('.bar', ((0, 0, 1, 0), None)),
    ('[baz]', ((0, 0, 1, 0), None)),
    ('[baz="4"]', ((0, 0, 1, 0), None)),
    ('[baz^="4"]', ((0, 0, 1, 0), None)),
    ('#lipsum', ((0, 1, 0, 0), None)),

    ('foo:empty', ((0, 0, 1, 1), None)),
    ('foo:before', ((0, 0, 0, 2), 'before')),
    ('foo::before', ((0, 0, 0, 2), 'before')),
    ('foo:empty::before', ((0, 0, 1, 2), 'before')),
    ('foo::before:empty', None),  # pseudo-elements can only be last
    ('foo::before > bar', None),  # pseudo-elements can only be last

    ('#lorem + foo#ipsum:first-child > bar:first-line',
        ((0, 2, 1, 3), 'first-line')),
])
def test_selector(css_source, expected_result):
    if not LXML_INSTALLED:  # pragma: no cover
        pytest.skip('lxml not available')
    try:
        result = parse_selector_string(css_source)
    except InvalidSelectorError:
        result = None
    else:
        result = result.specificity, result.pseudo_element
    assert result == expected_result


@pytest.mark.parametrize(('css_source', 'expected_result'), [
    (' ', None),
    ('foo, ', None),
    ('foo> ', None),
    ('* ', [((0, 0, 0, 0), None)]),
    ('foo, bar', [((0, 0, 0, 1), None), ((0, 0, 0, 1), None)]),

    ('#lorem + foo#ipsum:first-child > bar:first-line, #amet',
        [((0, 2, 1, 3), 'first-line'), ((0, 1, 0, 0), None)]),
])
def test_selector_group(css_source, expected_result):
    if not LXML_INSTALLED:  # pragma: no cover
        pytest.skip('lxml not available')
    try:
        result = parse_selector_group_string(css_source)
    except InvalidSelectorError:
        result = None
    else:
        result = [(selector.specificity, selector.pseudo_element)
                  for selector in result]
    assert result == expected_result
