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


def parse_value_priority(container):
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


class CSS21Parser(CoreParser):
    """Parser for CSS 2.1

    Extends :class:`CoreParser` and adds support for @import, @media,
    @page and !important.

    Note that property values are still not parsed, as UAs using this
    parser may only support some properties or some values.

    """
    def parse_declaration(self, *args, **kwargs):
        decl = super(CSS21Parser, self).parse_declaration(*args, **kwargs)
        value = decl.value
        value.content, priority = parse_value_priority(value)
        return PropertyDeclaration(
            decl.name, value, priority, decl.line, decl.column)
