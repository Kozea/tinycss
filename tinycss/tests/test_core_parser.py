# coding: utf8
"""
    Test suite for tinycss
    ----------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import pytest

from tinycss.core_parser import parse

from .test_tokenizer import jsonify


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
def test_core_parser(css_source, expected_rules, expected_errors):
    stylesheet = parse(css_source)
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
