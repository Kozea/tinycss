# coding: utf8
"""
    tinycss.css21
    -------------

    Parser for CSS 2.1
    http://www.w3.org/TR/CSS21/syndata.html

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals

from .core import CoreParser, Declaration, ParseError


class PropertyDeclaration(Declaration):
    """A CSS 2.1 property declaration.

    Same as :class:`Declaration` with an additional attribute:

    .. attribute:: priority
        Either the string ``'important'`` or ``None``.

    """
    def __init__(self, name, value, priority, line, column):
        super(PropertyDeclaration, self).__init__(name, value, line, column)
        self.priority = priority


class PageRule(object):
    """A parsed CSS 2.1 @page rule.

    .. attribute:: at_keyword
        Always ``'@page'``

    .. attribute:: selector
        The page selector, eg. ``'first'`` for ``@page :first {}``
        or ``None`` for ``@page {}``

    .. attribute:: declarations
        A list of :class:`PropertyDeclaration`

    .. attribute:: at_rules
        The list of parsed at-rules inside the @page block.
        Always empty for CSS 2.1.

    """
    at_keyword = '@page'

    def __init__(self, selector, declarations, at_rules):
        self.selector = selector
        self.declarations = declarations
        self.at_rules = at_rules


class CSS21Parser(CoreParser):
    """Parser for CSS 2.1

    Extends :class:`CoreParser` and adds support for @import, @media,
    @page and !important.

    Note that property values are still not parsed, as UAs using this
    parser may only support some properties or some values.

    """
    def parse_at_rule(self, rule, stylesheet_rules, errors):
        if rule.at_keyword == '@page':
            selector = self.parse_page_selector(rule.head)
            if not rule.body:
                raise ParseError((rule.head[-1] if selector else rule),
                    'invalid @page rule: missing block')
            declarations, at_rules = self.parse_page_block(rule.body, errors)
            stylesheet_rules.append(PageRule(selector, declarations, at_rules))
            return True


    def parse_page_selector(self, head):
        """Parse an @page selector.

        :param head:
            The ``head`` attribute of an unparsed :class:`AtRule`.
        :returns:
            A page selector. For CSS 2.1, this is 'first', 'left', 'right'
            or None.
        :raises:
            :class:`ParseError` on invalid selectors
        """
        if not head:
            return None
        if (len(head) == 2 and head[0].type == ':'
                and head[1].type == 'IDENT' and head[1].value in (
                    'first', 'left', 'right')):
            return head[1].value
        raise ParseError(head[0], 'invalid @page selector')


    def parse_page_block(self, body, errors):
        """Parse the body of an @page rule.

        :param body:
            The ``body`` attribute of an unparsed :class:`AtRule`.
        :param errors:
            A list where to append encountered :class:`ParseError`
        :returns:
            A tuple of:

            * A list of :class:`PropertyDeclaration`
            * A list of parsed at-rules (empty for CSS 2.1)
            * A list of :class:`ParseError`

        """
        at_rules = []
        declarations = []
        tokens = iter(body.content)
        for token in tokens:
            if token.type == 'ATKEYWORD':
                try:
                    rule = self.read_at_rule(token, tokens)
                    parsed_rule = self.parse_page_at_rule(rule)
                    if not parsed_rule:
                        raise ParseError(rule,
                            'unknown at-rule in @page context: '
                            + rule.at_keyword)
                    at_rules.append(parsed_rule)
                except ParseError as err:
                    errors.append(err)
            elif token.type != 'S':
                declaration_tokens = []
                while token and token.type != ';':
                    declaration_tokens.append(token)
                    token = next(tokens, None)
                if declaration_tokens:
                    try:
                        declarations.append(
                            self.parse_declaration(declaration_tokens))
                    except ParseError as err:
                        errors.append(err)
        return declarations, at_rules

    def parse_page_at_rule(self, rule):
        """Parse an at-rule in the page context. (Always an error in CSS 2.1)

        :param rule:
            An unparsed :class:`AtRule` read in the @page context.
        :returns:
            A parsed at-rule, or None (unknown rule)

        """


    def parse_declaration(self, *args, **kwargs):
        decl = super(CSS21Parser, self).parse_declaration(*args, **kwargs)
        value = decl.value
        value.content, priority = self.parse_value_priority(value)
        return PropertyDeclaration(
            decl.name, value, priority, decl.line, decl.column)


    def parse_value_priority(self, container):
        """Take a VALUE ContainerToken from the core parser and
        separate any !important marker.
        """
        value = list(container.content)
        # Walk the token list from the end
        token = value.pop()
        if token.type == 'IDENT' and token.value == 'important':
            while value:
                token = value.pop()
                if token.type == 'DELIM' and token.value == '!':
                    # Skip any white space before the '!'
                    while value and value[-1].type == 'S':
                        value.pop()
                    if not value:
                        raise ParseError(
                            container, 'expected a value before !important')
                    return value, 'important'
                # Skip white space between '!' and 'important'
                elif token.type != 'S':
                    break
        return container.content, None
