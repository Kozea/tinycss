# coding: utf8
"""
    tinycss.parser
    --------------

    Simple recursive-descent parser for the CSS core syntax:
    http://www.w3.org/TR/CSS21/syndata.html#tokenization

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals

from .tokenizer import tokenize
from . import structures


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


class PeekableIterator(object):
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.pushed = []
        self.push = self.pushed.append

    def next(self):
        if self.pushed:
            return self.pushed.pop()
        else:
            return next(self.iterator)

    __next__ = next


def parse(string):
    tokens = PeekableIterator(tokenize(string))
    return structures.StyleSheet(list(parse_stylesheet(tokens)))


def parse_stylesheet(tokens):
    for token in tokens:
        name, value = token
        if name not in ('CDO', 'CDC', 'S'):
            tokens.push(token)
            yield parse_statement(token, tokens)


def parse_statement(tokens):
    for token in tokens:
        name, value = token
        if name == 'ATKEYWORD':
            return parse_at_rule(value, tokens)
        else:
            return parse_ruleset(token, tokens)


def parse_at_rule(at_keyword, tokens):
    consume_whitespace(tokens)
    content = []
    for token in chain([next_token], tokens):
        name, value = token
        if name == '{':
            content.append(parse_block(tokens))
        if name == ';':
            # TODO: is S* here really needed?
            # It seems redundant with parse_stylesheet()
            consume_whitespace(tokens)
        if name in '{;':
            return structures.AtRule(at_keyword, content)
        content.append(parse_any(tokens))  # XXX
    raise ValueError('Premature end of at-rule.')  # XXX


def parse_block(tokens):
    # Assume the '{' token was already consumed.
    consume_whitespace(tokens)
    content = []
    for token in tokens:
        name, value = token
        if name == '}':
            consume_whitespace(tokens)
            return structures.Block(content)
        elif name == '{':
            content.append(parse_block(tokens))
        elif name == 'ATKEYWORD':
            content.append(structures.AtKeyword(value))
            consume_whitespace(tokens)
        elif name == ';':
            consume_whitespace(tokens)
        else:
            content.append(parse_any(tokens))  # XXX
    raise ValueError('Premature end of block.')  # XXX


def parse_ruleset(tokens):
    selector = parse_selector(tokens)
    declarations = []
    consume_whitespace(tokens)
    parse_declaration(tokens, declarations)
    for token in tokens:
        name, value = token
        if name == '}':
            return structures.RuleSet(declarations)
        else:
            assert name == ';'  # XXX
            consume_whitespace(tokens)
            parse_declaration(tokens, declarations)
    raise ValueError('Premature end of ruleset.')  # XXX


def parse_selector(tokens):
    """
    Actually:
        selector? '{'
    """
    content = []
    for token in tokens:
        name, value = token
        if name == '{':
            return content
        else:
            content.append(parse_any(tokens))  # XXX


def parse_declaration(tokens, declarations):
    """
    Actually:
        declaration?

    If a declaration is found, append it to ``declarations``

    """
    consumed_tokens = []
    token = next(tokens, None)
    if token is not None:
        consumed_tokens.append(token)
        name, value = token
        if name == 'IDENT':
            property_name = value
            token = next(tokens, None)
            if token is not None:
                consumed_tokens.append(token)
                name, value = token
                if name == ':':
                    values = parse_values(tokens)
                    if values:
                        declarations.append(structures.Declaration(
                            property_name, values))
                        return

    # No declaration found
    for token in reversed(consumed_tokens):
        tokens.push(token)


def parse_value(tokens):
    content = []
    for token in tokens:
        name, value = token
        if name == '{':
            content.append(parse_block(tokens))
        elif name == 'ATKEYWORD':
            content.append(structures.AtKeyword(value))
            consume_whitespace(tokens)
        else:
            result = parse_any(tokens)
            if result is None:
                return content
            content.append(result)


def parse_any(tokens):
    token = next(token, None)
    if token is None:
        return None
    if name in ['IDENT', 'NUMBER', 'PERCENTAGE', 'DIMENSION', 'STRING',
                'DELIM', 'URI', 'HASH', 'UNICODE-RANGE', 'INCLUDES',
                'DASHMATCH', ':']:
        consume_whitespace(tokens)
        return structures.ScalarValue(name, value)
    if name == 'FUNCTION':
        consume_whitespace(tokens)
        function_name = value[:-1]
        arguments = []
        while 1:
            argument = parse_any(tokens)
            if argument is None:
                token = next(tokens, None)
                assert token is not None  # XXX
                name, value = token
                assert name == ')'  # XXX
                consume_whitespace(tokens)
                return structures.Function(function_name, arguments)
            else:
                arguments.append(argument)
            # XXX unused?
    # TODO: (...)  ,  [...]


def consume_whitespace(tokens):
    """Match S*"""
    for token in tokens:
        name, value = token
        if name != 'S':
            tokens.push(token)
