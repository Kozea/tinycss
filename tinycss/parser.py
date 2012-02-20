# coding: utf8
"""
    tinycss.parser
    --------------

    Simple recursive-descent parser for the CSS core syntax:
    http://www.w3.org/TR/CSS21/syndata.html#tokenization

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals, print_function
from itertools import chain
import functools
import sys
import re

from .tokenizer import tokenize, COMPILED_MACROS


#  stylesheet  : [ CDO | CDC | S | statement ]*;
#  statement   : ruleset | at-rule;
#  at-rule     : ATKEYWORD S* any* [ block | ';' S* ];
#  block       : '{' S* [ any | block | ATKEYWORD S* | ';' S* ]* '}' S*;
#  ruleset     : selector? '{' S* declaration? [ ';' S* declaration? ]* '}' S*;
#  selector    : any+;
#  declaration : property S* ':' S* value;
#  property    : IDENT;
#  value       : [ any | block | ATKEYWORD S* ]+;
#  any         : [ IDENT | NUMBER | PERCENTAGE | DIMENSION | STRING
#                | DELIM | URI | HASH | UNICODE-RANGE | INCLUDES
#                | DASHMATCH | ':' | FUNCTION S* [any|unused]* ')'
#                | '(' S* [any|unused]* ')' | '[' S* [any|unused]* ']'
#                ] S*;
#  unused      : block | ATKEYWORD S* | ';' S* | CDO S* | CDC S*;


def parse(string):
    tokens = regroup(iter(tokenize(string)))
    return list(parse_stylesheet(tokens))


def regroup(tokens, end=None):
    """
    Take a flat *iterator* of tokens and match pairs: () [] {} function()
    (Strings in "" or '' are taken care of by the tokenizer.)

    The result is a tree: opening tokens get their value replaced by the
    list of their "child" tokens, and closing tokens are removed.

    """
    pairs = {'FUNCTION': ')', '(': ')', '[': ']', '{': '}'}
    for token in tokens:
        type_ = token.type
        if type_ == end:
            return

        next_end = pairs.get(type_)
        if next_end is None:
            yield token  # Not a grouping token
        else:
            content = list(regroup(tokens, next_end))
            if type_ == 'FUNCTION':
                # Include function name
                content = token.value, content
            yield token.replace_value(content)


class UnexpectedToken(ValueError):
    def __init__(self, token, reason):
        self.token = token
        self.reason = reason

    def warn(self):
        warn('Unexpected token {}, {}'.format(self.token, self.reason))


def warn(message):
    # TODO: use the logging module
    print(message, file=sys.stderr)


def parse_stylesheet(tokens):
    for token in tokens:
        if token.type not in ('S', 'CDO', 'CDC'):
            try:
                if token.type == 'ATKEYWORD':
                    yield parse_at_rule(token.value, tokens)
                else:
                    yield parse_ruleset(chain([token], tokens))
            except UnexpectedToken as e:
                e.warn()
                # Skip the entire rule


def parse_ruleset(tokens):
    selector_parts = []
    for token in tokens:
        if token.type == '{':
            # Any of these can raise UnexpectedToken, but we’ve read the
            # whole rule from the iterator.

            at_keyword = None
            # Individual values in selectors are not parsed. They are
            # validated, but the entire selector is serialized as a string.
            selector = ''.join(parse_selector(selector_parts))
            declarations = list(parse_declarations(token.value))
            return at_keyword, selector, declarations
        else:
            selector_parts.append(token)


def parse_at_rule(at_keyword, tokens):
    head = []
    for token in tokens:
        if token.type in '{;':
            head = [parse_any(token) if token.type != 'S' else token
                    for token in head]
            if token.type == '{':
                body = list(parse_block(token.value))
            else:
                body = None
            return at_keyword, head, body
        # Ignore white space just after the at-keyword, but keep it afterwards
        elif head or token.type != 'S':
            head.append(token)


def parse_selector(parts):
    """Validate a selector and serialize it to string chunks."""
    for token in parts:
        type_ = token.type
        if type_ in ('S', 'IDENT', 'HASH', 'DELIM', 'INCLUDES', 'DASHMATCH',
                     'NUMBER', 'PERCENTAGE', 'DIMENSION', 'STRING', ':',
                     'URI', 'UNICODE-RANGE'):
            yield token.css_value
        elif type_ == '[':
            yield '['
            yield ''.join(parse_selector(token.value))
            yield ']'
        elif type_ == '(':
            yield '('
            yield ''.join(parse_selector(token.value))
            yield ')'
        elif type_ == 'FUNCTION':
            yield token.css_value  # function name
            _unescaped_function_name, value = token.value
            yield ''.join(parse_selector(value))
            yield ')'
        else:
            raise UnexpectedToken(token, 'invalid in selector')


def parse_declarations(tokens):
    # split at ';'
    parts = []
    this_part = []
    for token in tokens:
        type_ = token.type
        if type_ == ';' and this_part:
            parts.append(this_part)
            this_part = []
        # XXX skip white space?
        elif type_ != 'S':
            this_part.append(token)
    if this_part:
        parts.append(this_part)

    for part in parts:
        try:
            yield parse_declaration(part)
        except UnexpectedToken as e:
            e.warn()
            # Skip the entire declaration


def parse_declaration(tokens):
    tokens = iter(tokens)
    def get(expected_type):
        token = next(tokens, None)
        if token is None:
            raise UnexpectedToken(
                None, 'expected %r for declaration' % expected_type)
        if token.type != expected_type:
            raise UnexpectedToken(
                token, 'expected %r for declaration' % expected_type)
        return token
    property_name = get('IDENT').value
    get(':')
    return property_name, list(parse_values(tokens))


def parse_values(tokens):
    got_anything = False
    for token in tokens:
        type_ = token.type
        if type_ == 'ATKEYWORD':
            got_anything = True
            yield token
        elif type_ == '{':
            got_anything = True
            yield list(parse_block(token.value))
        # XXX skip white space?
        elif type_ != 'S':
            got_anything = True
            yield parse_any(token)
    if not got_anything:
        raise UnexpectedToken(None, 'missing value')


def parse_block(tokens):
    for token in tokens:
        type_ = token.type
        if type_ in (';', 'ATKEYWORD'):
            yield token
        elif type_ == '{':
            yield token.replace_value(list(parse_block(token.value)))
        # XXX skip white space?
        elif type_ != 'S':
            yield parse_any(token)


def parse_any(token):
    type_ = token.type
    if type_ in ('IDENT', 'DIMENSION', 'PERCENTAGE', 'NUMBER', 'URI',
                 'DELIM', 'STRING', 'HASH', 'ATKEYWORD', ':',
                 'UNICODE-RANGE', 'INCLUDES', 'DASHMATCH'):
        return token

    elif type_ == 'FUNCTION':
        function_name, arguments = token.value
        parsed_arguments = []
        for token in arguments:
            # XXX skip white space?
            if token.type != 'S':
                parsed_arguments.append(parse_any(token))
        value = function_name, arguments
        return token.replace_value(value)

    elif type_ in ('(', '['):
        content = token.value
        value = []
        for token in content:
            # XXX skip white space?
            if token.type != 'S':
                value.append(parse_any(token))
        return token.replace_value(value)

    else:
        raise UnexpectedToken(token, "invalid in 'any'")


if __name__ == '__main__':
    # XXX debug
    import sys, pprint
    with open(sys.argv[1], 'rb') as fd:
        content = fd.read().decode('utf8')
    pprint.pprint(parse(content))
