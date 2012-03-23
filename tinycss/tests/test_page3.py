# coding: utf8
"""
    Tests for the Paged Media 3 parser
    ----------------------------------

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import os

import pytest

from tinycss.page3 import CSSPage3Parser
from .test_tokenizer import jsonify
from . import assert_errors


@pytest.mark.parametrize(('css', 'expected_selector','expected_errors'), [
    ('@page {}', (None, None), []),

    ('@page :first {}', (None, 'first'), []),
    ('@page:left{}', (None, 'left'), []),
    ('@page :right {}', (None, 'right'), []),
    ('@page :last {}', None, ['invalid @page selector']),
    ('@page : first {}', None, ['invalid @page selector']),

    ('@page foo:first {}', ('foo', 'first'), []),
    ('@page bar :left {}', ('bar', 'left'), []),
    (r'@page \26:right {}', ('&', 'right'), []),

    ('@page foo {}', ('foo', None), []),
    (r'@page \26 {}', ('&', None), []),

    ('@page foo fist {}', None, ['invalid @page selector']),
    ('@page foo, bar {}', None, ['invalid @page selector']),
    ('@page foo&first {}', None, ['invalid @page selector']),
])
def test_selectors(css, expected_selector, expected_errors):
    stylesheet = CSSPage3Parser().parse_stylesheet(css)
    assert_errors(stylesheet.errors, expected_errors)

    if stylesheet.statements:
        assert len(stylesheet.statements) == 1
        rule = stylesheet.statements[0]
        assert rule.at_keyword == '@page'
        selector = rule.selector
    else:
        selector = None
    assert selector == expected_selector


@pytest.mark.parametrize(('css', 'expected_declarations',
                          'expected_rules','expected_errors'), [
    ('@page {}', [], [], []),
    ('@page { foo: 4; bar: z }',
        [('foo', [('INTEGER', 4)]), ('bar', [('IDENT', 'z')])], [], []),
    ('''@page { foo: 4;
                @top-center { content: "Awesome Title" }
                @bottom-left { content: counter(page) }
                bar: z
        }''',
        [('foo', [('INTEGER', 4)]), ('bar', [('IDENT', 'z')])],
        [('@top-center', [('content', [('STRING', 'Awesome Title')])]),
         ('@bottom-left', [('content', [
            ('FUNCTION', 'counter', [('IDENT', 'page')])])])],
        []),
    ('''@page { foo: 4;
                @bottom-top { content: counter(page) }
                bar: z
        }''',
        [('foo', [('INTEGER', 4)]), ('bar', [('IDENT', 'z')])],
        [],
        ['unknown at-rule in @page context: @bottom-top']),
    # Not much error recovery tests here. This should be covered in test_css21
])
def test_content(css, expected_declarations, expected_rules, expected_errors):
    stylesheet = CSSPage3Parser().parse_stylesheet(css)
    assert_errors(stylesheet.errors, expected_errors)

    def declarations(rule):
        return [(decl.name, list(jsonify(decl.value.content)))
                for decl in rule.declarations]

    assert len(stylesheet.statements) == 1
    rule = stylesheet.statements[0]
    assert rule.at_keyword == '@page'
    assert declarations(rule) == expected_declarations
    rules = [(margin_rule.at_keyword, declarations(margin_rule))
             for margin_rule in rule.at_rules]
    assert rules == expected_rules
