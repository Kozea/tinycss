# coding: utf8
"""
    Tests for the core parser
    -------------------------

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import io
import os
import tempfile

import pytest

from tinycss.core import CoreParser

from .test_tokenizer import jsonify
from . import assert_errors


class TestParser(CoreParser):
    """A parser that always accepts unparsed at-rules."""
    def parse_at_rule(self, rule, stylesheet_rules, errors, context):
        if rule.at_keyword == '@charset':
            return super(TestParser, self).parse_at_rule(
                rule, stylesheet_rules, errors, context)
        else:
            return rule


def parse_bytes(css_bytes, kwargs):
    return TestParser().parse_stylesheet_bytes(css_bytes, **kwargs)


def parse_bytesio_file(css_bytes, kwargs):
    css_file = io.BytesIO(css_bytes)
    return TestParser().parse_stylesheet_file(css_file, **kwargs)


def parse_filename(css_bytes, kwargs):
    css_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        css_file.write(css_bytes)
        # Windows can not open the filename a second time while
        # it is still open for writing.
        css_file.close()
        return TestParser().parse_stylesheet_file(css_file.name, **kwargs)
    finally:
        os.remove(css_file.name)


@pytest.mark.parametrize(('css_bytes', 'kwargs', 'expected_result', 'parse'), [
    params + (parse,)
    for parse in [parse_bytes, parse_bytesio_file, parse_filename]
    for params in [
        ('@import "é";'.encode('utf8'), {}, 'é'),
        ('@import "é";'.encode('utf16'), {}, 'é'),  # with a BOM
        ('@import "é";'.encode('latin1'), {}, None),
        ('@charset "latin1";@import "é";'.encode('latin1'), {}, 'é'),
        (' @charset "latin1";@import "é";'.encode('latin1'), {}, None),
        ('@import "é";'.encode('latin1'),
            {'document_encoding': 'latin1'}, 'é'),
        ('@import "é";'.encode('latin1'), {'document_encoding': 'utf8'}, None),
        ('@charset "utf8"; @import "é";'.encode('utf8'),
            {'document_encoding': 'latin1'}, 'é'),
        # Mojibake yay!
        (' @charset "utf8"; @import "é";'.encode('utf8'),
            {'document_encoding': 'latin1'}, 'Ã©'),
        ('@import "é";'.encode('utf8'), {'document_encoding': 'latin1'}, 'Ã©'),
    ]
])
def test_bytes(css_bytes, kwargs, expected_result, parse):
    try:
        stylesheet = parse(css_bytes, kwargs)
    except UnicodeDecodeError:
        result = None
    else:
        assert stylesheet.rules[0].at_keyword == '@import'
        head = stylesheet.rules[0].head
        assert head[0].type == 'STRING'
        result = head[0].value
    assert result == expected_result


@pytest.mark.parametrize(('css_source', 'expected_rules', 'expected_errors'), [
    (' /* hey */\n', 0, []),
    ('foo {}', 1, []),
    ('foo{} @page{} bar{}', 2,
        ['unknown at-rule in stylesheet context: @page']),
    ('@charset "ascii"; foo {}', 1, []),
    (' @charset "ascii"; foo {}', 1, ['mis-placed or malformed @charset rule']),
    ('@charset ascii; foo {}', 1, ['mis-placed or malformed @charset rule']),
    ('foo {} @charset "ascii";', 1, ['mis-placed or malformed @charset rule']),
])
def test_at_rules(css_source, expected_rules, expected_errors):
    # Pass 'encoding' to allow @charset
    # Not using TestParser here:
    stylesheet = CoreParser().parse_stylesheet(css_source, encoding='utf8')
    assert_errors(stylesheet.errors, expected_errors)
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

    ('a{b:4}', [('a', [('b', [('INTEGER', 4)])])], []),

    ('@page {\t b: 4; @margin}', [('@page', [], [
       ('S', '\t '), ('IDENT', 'b'), (':', ':'), ('S', ' '), ('INTEGER', 4),
       (';', ';'), ('S', ' '), ('ATKEYWORD', '@margin'),
    ])], []),

    ('foo', [], ['no declaration block found']),

    ('foo @page {} bar {}', [('bar', [])],
        ['unexpected ATKEYWORD token in selector']),

    ('foo { content: "unclosed string;\n color:red; ; margin/**/: 2cm; }',
        [('foo', [('margin', [('DIMENSION', 2)])])],
        ['unexpected BAD_STRING token in property value']),

    ('foo { 4px; bar: 12% }',
        [('foo', [('bar', [('PERCENTAGE', 12)])])],
        ['expected a property name, got DIMENSION']),

    ('foo { bar! 3cm auto ; baz: 7px }',
        [('foo', [('baz', [('DIMENSION', 7)])])],
        ["expected ':', got DELIM"]),

    ('foo { bar ; baz: {("}"/* comment */) {0@fizz}} }',
        [('foo', [('baz', [('{', [
            ('(', [('STRING', '}')]), ('S', ' '),
            ('{', [('INTEGER', 0), ('ATKEYWORD', '@fizz')])
        ])])])],
        ["expected ':'"]),

    ('foo { bar: ; baz: not(z) }',
        [('foo', [('baz', [('FUNCTION', 'not', [('IDENT', 'z')])])])],
        ['expected a property value']),

    ('foo { bar: (]) ; baz: U+20 }',
        [('foo', [('baz', [('UNICODE-RANGE', 'U+20')])])],
        ['unmatched ] token in (']),
])
def test_parse_stylesheet(css_source, expected_rules, expected_errors):
    stylesheet = TestParser().parse_stylesheet(css_source)
    assert_errors(stylesheet.errors, expected_errors)
    result = [
        (rule.at_keyword, list(jsonify(rule.head)),
            list(jsonify(rule.body.content))
            if rule.body is not None else None)
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

    ('b:4', [('b', [('INTEGER', 4)])], []),

    ('{b:4}', [], ['expected a property name, got {']),

    ('b:4} c:3', [], ['unmatched } token in property value']),

    (' 4px; bar: 12% ',
        [('bar', [('PERCENTAGE', 12)])],
        ['expected a property name, got DIMENSION']),

    ('bar! 3cm auto ; baz: 7px',
        [('baz', [('DIMENSION', 7)])],
        ["expected ':', got DELIM"]),

    ('foo; bar ; baz: {("}"/* comment */) {0@fizz}}',
        [('baz', [('{', [
            ('(', [('STRING', '}')]), ('S', ' '),
            ('{', [('INTEGER', 0), ('ATKEYWORD', '@fizz')])
        ])])],
        ["expected ':'", "expected ':'"]),

    ('bar: ; baz: not(z)',
        [('baz', [('FUNCTION', 'not', [('IDENT', 'z')])])],
        ['expected a property value']),

    ('bar: (]) ; baz: U+20',
        [('baz', [('UNICODE-RANGE', 'U+20')])],
        ['unmatched ] token in (']),
])
def test_parse_style_attr(css_source, expected_declarations, expected_errors):
    declarations, errors = TestParser().parse_style_attr(css_source)
    assert_errors(errors, expected_errors)
    result = [(decl.name, list(jsonify(decl.value.content)))
              for decl in declarations]
    assert result == expected_declarations
