# coding: utf8
"""
    Tests for the CSS 2.1 parser
    ----------------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import pytest

from tinycss.css21 import CSS21Parser

from .test_tokenizer import jsonify



@pytest.mark.parametrize(('css_source', 'expected_rules', 'expected_errors'), [
    (' /* hey */\n', [], []),


])
def test_parse_stylesheet(css_source, expected_rules, expected_errors):
    stylesheet = CSS21Parser().parse_stylesheet(css_source)
    assert len(stylesheet.errors) == len(expected_errors)
    for error, expected in zip(stylesheet.errors, expected_errors):
        assert expected in error.message
    result = [
        (rule.at_keyword, list(jsonify(rule.head)),
            list(jsonify(rule.body.content)) if rule.body else None)
        if rule.at_keyword else
        (rule.selector.as_css, [
            (decl.name, list(jsonify(decl.value.content)))
            for decl in rule.declarations])
        for rule in stylesheet.rules
    ]
    assert result == expected_rules


@pytest.mark.parametrize(('css_source', 'expected_declarations',
                          'expected_errors'), [
    (' /* hey */\n', [], []),

    ('a:1; b:2',
        [('a', [('NUMBER', 1)], None), ('b', [('NUMBER', 2)], None)], []),

    ('a:1 important; b: important',
        [('a', [('NUMBER', 1), ('S', ' '), ('IDENT', 'important')], None),
            ('b', [('IDENT', 'important')], None)],
        []),

    ('a:1 !important; b:2',
        [('a', [('NUMBER', 1)], 'important'), ('b', [('NUMBER', 2)], None)],
        []),

    ('a:1!\t important; b:2',
        [('a', [('NUMBER', 1)], 'important'), ('b', [('NUMBER', 2)], None)],
        []),

    ('a: !important; b:2',
        [('b', [('NUMBER', 2)], None)],
        ['expected a value before !important']),

])
def test_parse_style_attr(css_source, expected_declarations, expected_errors):
    declarations, errors = CSS21Parser().parse_style_attr(css_source)
    assert len(errors) == len(expected_errors)
    for error, expected in zip(errors, expected_errors):
        assert expected in error.message
    result = [(decl.name, list(jsonify(decl.value.content)), decl.priority)
              for decl in declarations]
    assert result == expected_declarations
