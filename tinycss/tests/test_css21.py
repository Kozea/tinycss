# coding: utf8
"""
    Tests for the CSS 2.1 parser
    ----------------------------

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import pytest

from tinycss.css21 import CSS21Parser

from .test_tokenizer import jsonify
from . import assert_errors


@pytest.mark.parametrize(('css_source', 'expected_rules', 'expected_errors'), [
    (' /* hey */\n', [], []),
    ('@import "foo.css";', [('foo.css', ['all'])], []),
    ('@import url(foo.css);', [('foo.css', ['all'])], []),
    ('@import "foo.css" screen, print;',
        [('foo.css', ['screen', 'print'])], []),
    ('@charset "ascii"; @import "foo.css"; @import "bar.css";',
        [('foo.css', ['all']), ('bar.css', ['all'])], []),
    ('foo {} @import "foo.css";',
        [], ['@import rule not allowed after a ruleset']),
    ('@page {} @import "foo.css";',
        [], ['@import rule not allowed after an @page rule']),
    ('@import ;',
        [], ['expected URI or STRING for @import rule']),
    ('@import foo.css;',
        [], ['expected URI or STRING for @import rule, got IDENT']),
    ('@import "foo.css" {}',
        [], ["expected ';', got a block"]),
])
def test_at_import(css_source, expected_rules, expected_errors):
    # Pass 'encoding' to allow @charset
    stylesheet = CSS21Parser().parse_stylesheet(css_source, encoding='utf8')
    assert_errors(stylesheet.errors, expected_errors)

    result = [
        (rule.uri, rule.media)
        for rule in stylesheet.rules
        if rule.at_keyword == '@import'
    ]
    assert result == expected_rules


@pytest.mark.parametrize(('css', 'expected_result', 'expected_errors'), [
    ('@page {}', (None, (0, 0), []), []),
    ('@page:first {}', ('first', (1, 0), []), []),
    ('@page :left{}', ('left', (0, 1), []), []),
    ('@page\t\n:right {}', ('right', (0, 1), []), []),
    ('@page :last {}', None, ['invalid @page selector']),
    ('@page : right {}', None, ['invalid @page selector']),
    ('@page table:left {}', None, ['invalid @page selector']),

    ('@page;', None, ['invalid @page rule: missing block']),
    ('@page { a:1; ; b: 2 }',
        (None, (0, 0), [('a', [('INTEGER', 1)]), ('b', [('INTEGER', 2)])]),
        []),
    ('@page { a:1; c: ; b: 2 }',
        (None, (0, 0), [('a', [('INTEGER', 1)]), ('b', [('INTEGER', 2)])]),
        ['expected a property value']),
    ('@page { a:1; @top-left {} b: 2 }',
        (None, (0, 0), [('a', [('INTEGER', 1)]), ('b', [('INTEGER', 2)])]),
        ['unknown at-rule in @page context: @top-left']),
    ('@page { a:1; @top-left {}; b: 2 }',
        (None, (0, 0), [('a', [('INTEGER', 1)]), ('b', [('INTEGER', 2)])]),
        ['unknown at-rule in @page context: @top-left']),
])
def test_at_page(css, expected_result, expected_errors):
    stylesheet = CSS21Parser().parse_stylesheet(css)
    assert_errors(stylesheet.errors, expected_errors)

    if expected_result is None:
        assert not stylesheet.rules
    else:
        assert len(stylesheet.rules) == 1
        rule = stylesheet.rules[0]
        assert rule.at_keyword == '@page'
        assert rule.at_rules == []  # in CSS 2.1
        result = (
            rule.selector,
            rule.specificity,
            [(decl.name, list(jsonify(decl.value.content)))
                for decl in rule.declarations],
        )
        assert result == expected_result


@pytest.mark.parametrize(('css_source', 'expected_rules', 'expected_errors'), [
    (' /* hey */\n', [], []),
    ('@media all {}', [(['all'], [])], []),
    ('@media screen, print {}', [(['screen', 'print'], [])], []),
    ('@media all;', [], ['invalid @media rule: missing block']),
    ('@media  {}', [], ['expected media types for @media']),
    ('@media 4 {}', [], ['expected a media type, got INTEGER']),
    ('@media , screen {}', [], ['expected a media type, got DELIM']),
    ('@media screen, {}', [], ['expected a media type']),
    ('@media screen print {}', [], ['expected a comma, got S']),

    ('@media all { @page { a: 1 } @media; @import; foo { a: 1 } }',
        [(['all'], [('foo', [('a', [('INTEGER', 1)])])])],
        ['@page rule not allowed in @media',
         '@media rule not allowed in @media',
         '@import rule not allowed in @media']),

])
def test_at_media(css_source, expected_rules, expected_errors):
    stylesheet = CSS21Parser().parse_stylesheet(css_source)
    assert_errors(stylesheet.errors, expected_errors)

    for rule in stylesheet.rules:
        assert rule.at_keyword == '@media'
    result = [
        (rule.media, [
            (sub_rule.selector.as_css, [
                (decl.name, list(jsonify(decl.value.content)))
                for decl in sub_rule.declarations])
            for sub_rule in rule.rules
        ])
        for rule in stylesheet.rules
    ]
    assert result == expected_rules


@pytest.mark.parametrize(('css_source', 'expected_declarations',
                          'expected_errors'), [
    (' /* hey */\n', [], []),

    ('a:1; b:2',
        [('a', [('INTEGER', 1)], None), ('b', [('INTEGER', 2)], None)], []),

    ('a:1 important; b: important',
        [('a', [('INTEGER', 1), ('S', ' '), ('IDENT', 'important')], None),
            ('b', [('IDENT', 'important')], None)],
        []),

    ('a:1 !important; b:2',
        [('a', [('INTEGER', 1)], 'important'), ('b', [('INTEGER', 2)], None)],
        []),

    ('a:1!\t important; b:2',
        [('a', [('INTEGER', 1)], 'important'), ('b', [('INTEGER', 2)], None)],
        []),

    ('a: !important; b:2',
        [('b', [('INTEGER', 2)], None)],
        ['expected a value before !important']),

])
def test_important(css_source, expected_declarations, expected_errors):
    declarations, errors = CSS21Parser().parse_style_attr(css_source)
    assert_errors(errors, expected_errors)
    result = [(decl.name, list(jsonify(decl.value.content)), decl.priority)
              for decl in declarations]
    assert result == expected_declarations
