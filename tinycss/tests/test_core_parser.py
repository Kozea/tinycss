# coding: utf8
"""
    Test suite for tinycss
    ----------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import pytest

from tinycss.core_parser import CoreParser

from .test_tokenizer import jsonify



class TestParser(CoreParser):
    """A parser that always accepts unparsed at-rules."""
    def parse_at_rule(self, at_rule, stylesheet_rules, errors):
        stylesheet_rules.append(at_rule)
        return True


@pytest.mark.parametrize(('css_source', 'expected_rules', 'expected_errors'), [
    (' /* hey */\n', 0, []),
    ('foo {}', 1, []),
    ('foo{} @page{} bar{}', 2, ['unknown at-rule: @page']),
])
def test_at_rules(css_source, expected_rules, expected_errors):
    # Not using TestParser here:
    stylesheet = CoreParser().parse_stylesheet(css_source)
    assert len(stylesheet.errors) == len(expected_errors)
    for error, expected in zip(stylesheet.errors, expected_errors):
        assert expected in error.message
    result = len(stylesheet.rules)
    assert result == expected_rules


@pytest.mark.parametrize(('css_source', 'expected_rules', 'expected_errors'), [
    (' /* hey */\n', [], []),

    ('foo{} /* hey */\n@bar;@baz{}',
        [('foo', []), ('@bar', [], None), ('@baz', [], [])], []),

    ('@import "foo.css"/**/;', [
        ('@import', [('STRING', 'foo.css')], None)], []),

    ('@import "foo.css"/**/', [], ['incomplete at-rule']),

    ('{}', [('', [])], []),

    ('a{b:4}', [('a', [('b', [('NUMBER', 4)])])], []),

    ('@page {\t b: 4; @margin}', [('@page', [], [
       ('S', '\t '), ('IDENT', 'b'), (':', ':'), ('S', ' '), ('NUMBER', 4),
       (';', ';'), ('S', ' '), ('ATKEYWORD', '@margin'),
    ])], []),

    ('foo', [], ['no declaration block found']),

    ('foo @page {} bar {}', [('bar ', [])],
        ['unexpected ATKEYWORD token in selector']),

    ('foo { content: "unclosed string;\n color:red; ; margin/**/: 2cm; }',
        [('foo ', [('margin', [('DIMENSION', 2)])])],
        ['unexpected BAD_STRING token in property value']),

    ('foo { 4px; bar: 12% }',
        [('foo ', [('bar', [('PERCENTAGE', 12)])])],
        ['expected a property name, got DIMENSION']),

    ('foo { bar! 3cm auto ; baz: 7px }',
        [('foo ', [('baz', [('DIMENSION', 7)])])],
        ["expected ':', got DELIM"]),

    ('foo { bar ; baz: {("}"/* comment */) {0@fizz}} }',
        [('foo ', [('baz', [('{', [
            ('(', [('STRING', '}')]), ('S', ' '),
            ('{', [('NUMBER', 0), ('ATKEYWORD', '@fizz')])
        ])])])],
        ["expected ':'"]),

    ('foo { bar: ; baz: not(z) }',
        [('foo ', [('baz', [('FUNCTION', 'not', [('IDENT', 'z')])])])],
        ['expected a property value']),

    ('foo { bar: (]) ; baz: U+20 }',
        [('foo ', [('baz', [('UNICODE-RANGE', 'U+20')])])],
        ['unmatched ] token in (']),
])
def test_parse_stylesheet(css_source, expected_rules, expected_errors):
    stylesheet = TestParser().parse_stylesheet(css_source)
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

    ('b:4', [('b', [('NUMBER', 4)])], []),

    ('{b:4}', [], ['expected a property name, got {']),

    ('b:4} c:3', [], ['unmatched } token in property value']),

    (' 4px; bar: 12% ',
        [('bar', [('PERCENTAGE', 12)])],
        ['expected a property name, got DIMENSION']),

    ('bar! 3cm auto ; baz: 7px',
        [('baz', [('DIMENSION', 7)])],
        ["expected ':', got DELIM"]),

    ('bar ; baz: {("}"/* comment */) {0@fizz}}',
        [('baz', [('{', [
            ('(', [('STRING', '}')]), ('S', ' '),
            ('{', [('NUMBER', 0), ('ATKEYWORD', '@fizz')])
        ])])],
        ["expected ':'"]),

    ('bar: ; baz: not(z)',
        [('baz', [('FUNCTION', 'not', [('IDENT', 'z')])])],
        ['expected a property value']),

    ('bar: (]) ; baz: U+20',
        [('baz', [('UNICODE-RANGE', 'U+20')])],
        ['unmatched ] token in (']),
])
def test_parse_style_attr(css_source, expected_declarations, expected_errors):
    declarations, errors = TestParser().parse_style_attr(css_source)
    assert len(errors) == len(expected_errors)
    for error, expected in zip(errors, expected_errors):
        assert expected in error.message
    result = [(decl.name, list(jsonify(decl.value.content)))
              for decl in declarations]
    assert result == expected_declarations
