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

from .tokenizer import tokenize_grouped, ContainerToken


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
    """
    :param string: a CSS stylesheet as an unicode string
    :return: a :class:`Stylesheet`
    """
    return parse_stylesheet(tokenize_grouped(string))


class Stylesheet(object):
    """
    A parsed CSS stylesheet.

    .. attribute:: rules
        a mixed list of :class:`AtRule` and :class:`RuleSets` as returned by
        :func:`parse_at_rule` and :func:`parse_ruleset`, in source order

    .. attribute:: errors
        a list of :class:`ParseError`

    """
    def __init__(self, rules, errors):
        self.rules = rules
        self.errors = errors

    def pretty(self):
        """Return an indented string representation for debugging"""
        lines = [rule.pretty() for rule in self.rules] + [
                 e.message for e in self.errors]
        return '\n'.join(lines)


class AtRule(object):
    """
    An unparsed at-rule.

    .. attribute:: at_keyword
        The normalized (lower-case) at-keyword as a string. eg. '@page'

    .. attribute:: head
        The "head" of the at-rule until ';' or '{': a list of tokens
        (:class:`Token` or :class:`ContainerToken`)

    .. attribute:: body
        A block as a '{' :class:`ContainerToken`, or ``None`` if the at-rule
        ends with ';'

    The head was validated against the core grammar but **not** the body,
    as the body might contain declarations. In case of an error in a
    declaration, parsing should continue from the next declaration.
    The whole rule should not be ignored as it would be for an error
    in the head.

    You are expected to parse and validate these at-rules yourself.

    """
    def __init__(self, at_keyword, head, body):
        self.at_keyword = at_keyword
        self.head = head
        self.body = body

    def pretty(self):
        """Return an indented string representation for debugging"""
        lines = [self.at_keyword]
        for token in self.head:
            for line in token.pretty().splitlines():
                lines.append('    ' + line)
        if self.body:
            lines.append(self.body.pretty())
        else:
            lines.append(';')
        return '\n'.join(lines)


class RuleSet(object):
    """A ruleset.

    .. attribute:: at_keyword
        Always ``None``. Helps to tell rulesets apart from at-rules.

    .. attribute:: selector
        A (possibly empty) :class:`ContainerToken`

    .. attribute:: declarations
        The list of :class:`Declaration` as returned by
        :func:`parse_declaration_list`, in source order.

    """
    def __init__(self, selector, declarations):
        self.selector = selector
        self.declarations = declarations

    def pretty(self):
        """Return an indented string representation for debugging"""
        lines = [self.selector.pretty(), '{']
        for declaration in self.declarations:
            for line in declaration.pretty().splitlines():
                lines.append('    ' + line)
        lines.append('}')
        return '\n'.join(lines)

    at_keyword = None


class Declaration(object):
    """A property declaration.

    .. attribute:: name
        The property name as a normalized (lower-case) string.

    .. attribute:: values
        The property value: a list of tokens as returned by :func:`parse_value`.

    """
    def __init__(self, name, values):
        self.name = name
        self.values = values

    def pretty(self):
        """Return an indented string representation for debugging"""
        lines = [self.name + ':']
        for token in self.values:
            for line in token.pretty().splitlines():
                lines.append('    ' + line)
        return '\n'.join(lines)


class ParseError(ValueError):
    """A recoverable parsing error."""
    def __init__(self, token, reason):
        self.token = token
        self.message = 'Parse error at {0}:{1}, {2}'.format(
            token.line, token.column, reason)

    def __repr__(self):
        return '<{0}: {1}>'.format(type(self).__name__, self.message)


class UnexpectedTokenError(ParseError):
    """A special kind of parsing error: a token of the wrong type was found."""
    def __init__(self, token, context):
        if token.type in ('}', ')', ']'):
            adjective = 'unmatched'
        else:
            adjective = 'unexpected'
        message = '{0} {1} token in {2}'.format(adjective, token.type, context)
        super(UnexpectedToken, self).__init__(token, message)


def parse_stylesheet(tokens):
    """Parse an stylesheet.

    :param tokens:
        an iterable of tokens.
    :return:
        a :class:`Stylesheet`

    """
    rules = []
    errors = []
    for token in tokens:
        if token.type not in ('S', 'CDO', 'CDC'):
            try:
                if token.type == 'ATKEYWORD':
                    rules.append(parse_at_rule(token, tokens))
                else:
                    rule, rule_errors = parse_ruleset(token, tokens)
                    rules.append(rule)
                    errors.extend(rule_errors)
            except ParseError as e:
                errors.append(e)
                # Skip the entire rule
    return Stylesheet(rules, errors)


def parse_at_rule(at_keyword_token, tokens):
    """Parse an at-rule.

    :param at_keyword_token:
        The ATKEYWORD token that starts this at-rule
        You may have read it already to distinguish the rule from a ruleset.
    :param tokens:
        an iterator of subsequent tokens. Will be consumed just enough
        for one at-rule.
    :return:
        an :class:`AtRule`
    :raises:
        :class:`ParseError` if the head is invalid for the core grammar.
        The body is **not** validated. See :class:`AtRule`.

    """
    # CSS syntax is case-insensitive
    at_keyword = at_keyword_token.value.lower()
    head = []
    token = at_keyword_token  # For the ParseError in case `tokens` is empty
    for token in tokens:
        if token.type in '{;':
            for head_token in head:
                validate_any(head_token.value, 'at-rule head')
            if token.type == '{':
                body = token
            else:
                body = None
            return AtRule(at_keyword, head, body)
        # Ignore white space just after the at-keyword, but keep it afterwards
        elif head or token.type != 'S':
            head.append(token)
    raise ParseError(token, 'incomplete at-rule')


def parse_ruleset(first_token, tokens):
    """Parse a ruleset: a selector followed by declaration block.

    :param first_token:
        The first token of the ruleset (probably of the selector).
        You may have read it already to distinguish the rule from an at-rule.
    :param tokens:
        an iterator of subsequent tokens. Will be consumed just enough
        for one ruleset.
    :return:
        a tuple of a :class:`RuleSet` and an error list.
        The errors are recovered :class:`ParseError` in declarations.
        (Parsing continues from the next declaration on such errors.)
    :raises:
        :class:`ParseError` if the selector is invalid for the core grammar.
        Note a that a selector can be valid for the core grammar but
        not for CSS 2.1 or another level.

    """
    selector_parts = []
    for token in chain([first_token], tokens):
        if token.type == '{':
            # Parse/validate once we’ve read the whole rule
            for selector_token in selector_parts:
                validate_any(selector_token, 'selector')
            start = selector_parts[0] if selector_parts else token
            selector = ContainerToken(
                'SELECTOR', '', '', selector_parts, start.line, start.column)
            declarations, errors = parse_declaration_list(token.content)
            return RuleSet(selector, declarations), errors
        else:
            selector_parts.append(token)
    raise ParseError(token, 'no declaration block found for ruleset')


def parse_declaration_list(tokens):
    """Parse a ';' separated declaration list.

    If you have a block that contains declarations but not only
    (like ``@page`` in CSS 3 Paged Media), you need to extract them
    yourself and use :func:`parse_declaration` directly.

    :param tokens:
        an iterable of tokens. Should stop at (before) the end of the block,
        as marked by a '}'.
    :return:
        a tuple of the list of valid :class`Declaration` and a list
        of :class:`ParseError`

    """
    # split at ';'
    parts = []
    this_part = []
    for token in tokens:
        type_ = token.type
        if type_ == ';' and this_part:
            parts.append(this_part)
            this_part = []
        # skip white space at the start
        elif this_part or type_ != 'S':
            this_part.append(token)
    if this_part:
        parts.append(this_part)

    declarations = []
    errors = []
    for part in parts:
        try:
            declarations.append(parse_declaration(part))
        except ParseError as e:
            errors.append(e)
            # Skip the entire declaration
    return declarations, errors


def parse_declaration(tokens):
    """Parse a single declaration.

    :param tokens:
        an iterable of at least one token. Should stop at (before)
        the end of the declaration, as marked by a ';' or '}'.
        Empty declarations (ie. consecutive ';' with only white space
        in-between) should skipped and not passed to this function.
    :returns:
        a :class:`Declaration`
    :raises:
        :class:`ParseError` if the tokens do not match the 'declaration'
        production of the core grammar.

    """
    tokens = iter(tokens)

    token = next(tokens)  # assume there is at least one
    if token.type == 'IDENT':
        # CSS syntax is case-insensitive
        property_name = token.value.lower()
    else:
        raise UnexpectedToken(token, ', expected a property name')

    for token in tokens:
        if token.type == ':':
            break
        elif token.type != 'S':
            raise UnexpectedToken(token, ", expected ':'")
    else:
        raise ParseError(token, "expected ':'")

    value = parse_value(tokens)
    if not value:
        raise ParseError(token, 'expected a property value')
    return Declaration(property_name, value)


def parse_value(tokens):
    """Parse a property value and return a list of tokens.

    :param tokens:
        an iterable of tokens
    :return:
        a list of tokens with white space removed at the start and end,
        but not in the middle.
    :raises:
        :class:`ParseError` if there is any invalid token for the 'value'
        production of the core grammar.

    """
    content = []
    for token in tokens:
        type_ = token.type
        # Skip white space at the start
        if content or type_ != 'S':
            if type_ == '{':
                validate_block(token, 'property value')
            else:
                validate_any(token, 'property value')
            content.append(token)

    # Remove white space at the end
    while content and content[-1].type == 'S':
        content.pop()
    return content


def validate_block(tokens, context):
    """
    :raises:
        :class:`ParseError` if there is any invalid token for the 'block'
        production of the core grammar.
    :param tokens: an iterable of tokens
    :param context: a string for the 'unexpected in ...' message

    """
    for token in tokens:
        type_ = token.type
        if type_ == '{':
            validate_block(token.value, context)
        elif type_ not in (';', 'ATKEYWORD'):
            validate_any(token, context)


def validate_any(token, context):
    """
    :raises:
        :class:`ParseError` if this is an invalid token for the
        'any' production of the core grammar.
    :param token: a single token
    :param context: a string for the 'unexpected in ...' message

    """
    type_ = token.type
    if type_ in ('FUNCTION', '(', '['):
        for token in token.content:
            validate_any(token, type_)
    elif type_ not in ('S', 'IDENT', 'DIMENSION', 'PERCENTAGE', 'NUMBER',
                       'URI', 'DELIM', 'STRING', 'HASH', 'ATKEYWORD', ':',
                       'UNICODE-RANGE', 'INCLUDES', 'DASHMATCH'):
        raise UnexpectedToken(error_token, context)


if __name__ == '__main__':
    # XXX debug
    import sys, pprint
    with open(sys.argv[1], 'rb') as fd:
        content = fd.read().decode('utf8')
    print(parse(content).pretty())
