# coding: utf8
"""
    tinycss.parser
    --------------

    Simple recursive-descent parser for the CSS core syntax:
    http://www.w3.org/TR/CSS21/syndata.html#tokenization

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals
from itertools import chain, islice

from .decoding import decode
from .tokenizer import tokenize_grouped
from .token_data import ContainerToken


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


class Stylesheet(object):
    """
    A parsed CSS stylesheet.

    .. attribute:: statements
        a mixed list of :class:`AtRule` and :class:`RuleSets` as returned by
        :func:`parse_at_rule` and :func:`parse_ruleset`, in source order

    .. attribute:: errors
        a list of :class:`ParseError`

    .. attribute:: encoding
        The character encoding used to decode the stylesheet from bytes,
        or ``None`` for Unicode stylesheets.

    """
    def __init__(self, statements, errors, encoding):
        self.statements = statements
        self.errors = errors
        self.encoding = encoding

    def __repr__(self):  # pragma: no cover
        return '<{0.__class__.__name__} {1} rules {2} errors>'.format(
            self, len(self.statements), len(self.errors))

    def pretty(self):  # pragma: no cover
        """Return an indented string representation for debugging"""
        lines = [rule.pretty() for rule in self.statements] + [
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

    .. attribute:: line
        Source line where this was read.

    .. attribute:: column
        Source column where this was read.

    The head was validated against the core grammar but **not** the body,
    as the body might contain declarations. In case of an error in a
    declaration, parsing should continue from the next declaration.
    The whole rule should not be ignored as it would be for an error
    in the head.

    You are expected to parse and validate these at-rules yourself.

    """
    def __init__(self, at_keyword, head, body, line, column):
        self.at_keyword = at_keyword
        self.head = head
        self.body = body
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__} {0.line}:{0.column} {0.at_keyword}>'
                .format(self))

    def pretty(self):  # pragma: no cover
        """Return an indented string representation for debugging"""
        lines = [self.at_keyword]
        for token in self.head:
            for line in token.pretty().splitlines():
                lines.append('    ' + line)
        if self.body is not None:
            lines.append(self.body.pretty())
        else:
            lines.append(';')
        return '\n'.join(lines)


class RuleSet(object):
    """A ruleset.

    .. attribute:: at_keyword
        Always ``None``. Helps to tell rulesets apart from at-rules.

    .. attribute:: selector
        A (possibly empty) :class:`ContainerToken` object.
        In CSS 3 terminology, this is actually a selector group.

    .. attribute:: declarations
        The list of :class:`Declaration` as returned by
        :func:`parse_declaration_list`, in source order.

    .. attribute:: line
        Source line where this was read.

    .. attribute:: column
        Source column where this was read.

    """
    def __init__(self, selector, declarations, line, column):
        self.selector = selector
        self.declarations = declarations
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__} at {0.line}:{0.column}'
                ' {0.selector.as_css}>'.format(self))

    def pretty(self):  # pragma: no cover
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
        The property value: a list of tokens as returned by
        :func:`parse_value`.

    .. attribute:: line
        Source line where this was read.

    .. attribute:: column
        Source column where this was read.

    """
    def __init__(self, name, value, line, column):
        self.name = name
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.name}: {0.value.as_css}>'.format(self))

    def pretty(self):  # pragma: no cover
        """Return an indented string representation for debugging"""
        lines = [self.name + ':']
        for token in self.value.content:
            for line in token.pretty().splitlines():
                lines.append('    ' + line)
        return '\n'.join(lines)


class ParseError(ValueError):
    """A recoverable parsing error."""
    def __init__(self, subject, reason):
        self.subject = subject
        self.reason = reason
        self.msg = self.message = (
            'Parse error at {0.subject.line}:{0.subject.column}, {0.reason}'
            .format(self))
        super(ParseError, self).__init__(self.message)

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__}: {0.message}>'.format(self))


def _remove_at_charset(tokens):
    """Remove any valid @charset at the beggining of a token stream.

    :param tokens:
        An iterable of tokens
    :returns:
        A possibly truncated iterable of tokens

    """
    tokens = iter(tokens)
    header = list(islice(tokens, 4))
    if [t.type for t in header] == ['ATKEYWORD', 'S', 'STRING', ';']:
        atkw, space, string, semicolon = header
        if ((atkw.value, space.value) == ('@charset', ' ')
                and string.as_css[0] == '"'):
            # Found a valid @charset rule, only keep what’s after it.
            return tokens
    return chain(header, tokens)


class CoreParser(object):
    """
    Currently the parser holds no state. It is only a class to allow
    subclassing and overriding its methods.

    """

    # User API:

    def parse_stylesheet_file(self, css_file, protocol_encoding=None,
                              linking_encoding=None, document_encoding=None):
        """Parse a stylesheet from a file or filename.

        The character encoding is determined from the passed metadata and the
        ``@charset`` rule in the stylesheet (if any).

        :param css_file:
            Either a file (any object with a :meth:`~file.read` method)
            or a filename.
        :param protocol_encoding:
            The "charset" parameter of a "Content-Type" HTTP header (if any),
            or similar metadata for other protocols.
        :param linking_encoding:
            ``<link charset="">`` or other metadata from the linking mechanism
            (if any)
        :param document_encoding:
            Encoding of the referring style sheet or document (if any)
        :raises:
            :class:`UnicodeDecodeError` if decoding failed
        :return:
            A :class:`Stylesheet`.

        """
        if hasattr(css_file, 'read'):
            css_bytes = css_file.read()
        else:
            with open(css_file, 'rb') as fd:
                css_bytes = fd.read()
        return self.parse_stylesheet_bytes(css_bytes, protocol_encoding,
                                           linking_encoding, document_encoding)

    def parse_stylesheet_bytes(self, css_bytes, protocol_encoding=None,
                               linking_encoding=None, document_encoding=None):
        """Parse a stylesheet from a byte string.

        The character encoding is determined from the passed metadata and the
        ``@charset`` rule in the stylesheet (if any).

        :param css_bytes:
            A CSS stylesheet as a byte string.
        :param protocol_encoding:
            The "charset" parameter of a "Content-Type" HTTP header (if any),
            or similar metadata for other protocols.
        :param linking_encoding:
            ``<link charset="">`` or other metadata from the linking mechanism
            (if any)
        :param document_encoding:
            Encoding of the referring style sheet or document (if any)
        :raises:
            :class:`UnicodeDecodeError` if decoding failed
        :return:
            A :class:`Stylesheet`.

        """
        css_unicode, encoding = decode(css_bytes, protocol_encoding,
                                       linking_encoding, document_encoding)
        return self.parse_stylesheet(css_unicode, encoding=encoding)

    def parse_stylesheet(self, css_unicode, encoding=None):
        """Parse a stylesheet from an Unicode string.

        :param css_unicode:
            A CSS stylesheet as an unicode string.
        :param encoding:
            The character encoding used to decode the stylesheet from bytes,
            if any.
        :return:
            A :class:`Stylesheet`.

        """
        tokens = tokenize_grouped(css_unicode)
        if encoding:
            tokens = _remove_at_charset(tokens)
        errors = []
        statements = self.parse_statements(
            tokens, errors, context='stylesheet')
        return Stylesheet(statements, errors, encoding)

    def parse_style_attr(self, css_source):
        """Parse a "style" attribute (eg. of an HTML element).

        :param css_source:
            The attribute value, as an unicode string.
        :return:
            A tuple of the list of valid :class`Declaration` and a list
            of :class:`ParseError`.
        """
        return self.parse_declaration_list(tokenize_grouped(css_source))

    # API for subclasses:

    def parse_statements(self, tokens, errors, context):
        """Parse a sequence of statements (rulesets and at-rules).

        :param tokens:
            An iterable of tokens.
        :param errors:
            A list where to append encountered :class:`ParseError`
        :param context:
            Either 'stylesheet' or an at-keyword such as '@media'.
            (Some at-rules are only allowed in some contexts.)
        :return:
            A list of parsed statements.

        """
        rules = []
        tokens = iter(tokens)
        for token in tokens:
            if token.type not in ('S', 'CDO', 'CDC'):
                try:
                    if token.type == 'ATKEYWORD':
                        rule = self.read_at_rule(token, tokens)
                        result = self.parse_at_rule(
                            rule, rules, errors, context)
                        rules.append(result)
                    else:
                        rule, rule_errors = self.parse_ruleset(token, tokens)
                        rules.append(rule)
                        errors.extend(rule_errors)
                except ParseError as exc:
                    errors.append(exc)
                    # Skip the entire rule
        return rules

    def parse_at_rule(self, rule, previous_rules, errors, context):
        """Parse an at-rule.

        Subclasses that override this method must use ``super()`` and
        pass its return value for at-rules they do not know.

        In :class:`CoreParser`, this method only handles @charset rules
        and raises "unknown at-rule" for everything else.
        (@import, @media and @page are in :class`CSS21Parser`.)

        :param rule:
            An unparsed :class:`AtRule`.
        :param previous_rules:
            The list of at-rules and rulesets that have been parsed so far
            in this context. This method can append to this list
            (to add a valid, parsed at-rule) or inspect it to decide if
            the rule is valid. (For example, @import rules are only allowed
            before anything but a @charset rule.)
        :param context:
            Either 'stylesheet' or an at-keyword such as '@media'.
            (Some at-rules are only allowed in some contexts.)
        :raises:
            :class:`ParseError` if the rule is invalid.
        :return:
            A parsed at-rule or None (ignore)

        """
        if rule.at_keyword == '@charset':
            raise ParseError(rule, 'mis-placed or malformed @charset rule')
        else:
            raise ParseError(rule, 'unknown at-rule in {0} context: {1}'
                                    .format(context, rule.at_keyword))

    def read_at_rule(self, at_keyword_token, tokens):
        """Read an at-rule.

        :param at_keyword_token:
            The ATKEYWORD token that starts this at-rule
            You may have read it already to distinguish the rule
            from a ruleset.
        :param tokens:
            An iterator of subsequent tokens. Will be consumed just enough
            for one at-rule.
        :return:
            An unparsed :class:`AtRule`
        :raises:
            :class:`ParseError` if the head is invalid for the core grammar.
            The body is **not** validated. See :class:`AtRule`.

        """
        # CSS syntax is case-insensitive
        at_keyword = at_keyword_token.value.lower()
        head = []
        # For the ParseError in case `tokens` is empty:
        token = at_keyword_token
        for token in tokens:
            if token.type in '{;':
                # Remove white space at the end of the head
                # (but not in the middle).
                while head and head[-1].type == 'S':
                    head.pop()
                for head_token in head:
                    self.validate_any(head_token, 'at-rule head')
                if token.type == '{':
                    body = token
                else:
                    body = None
                return AtRule(at_keyword, head, body,
                              at_keyword_token.line, at_keyword_token.column)
            # Ignore white space just after the at-keyword.
            elif head or token.type != 'S':
                head.append(token)
        raise ParseError(token, 'incomplete at-rule')

    def parse_ruleset(self, first_token, tokens):
        """Parse a ruleset: a selector followed by declaration block.

        :param first_token:
            The first token of the ruleset (probably of the selector).
            You may have read it already to distinguish the rule
            from an at-rule.
        :param tokens:
            an iterator of subsequent tokens. Will be consumed just enough
            for one ruleset.
        :return:
            a tuple of a :class:`RuleSet` and an error list.
            The errors are recovered :class:`ParseError` in declarations.
            (Parsing continues from the next declaration on such errors.)
        :raises:
            :class:`ParseError` if the selector is invalid for the
            core grammar.
            Note a that a selector can be valid for the core grammar but
            not for CSS 2.1 or another level.

        """
        selector_parts = []
        for token in chain([first_token], tokens):
            if token.type == '{':
                # Parse/validate once we’ve read the whole rule
                for selector_token in selector_parts:
                    self.validate_any(selector_token, 'selector')
                start = selector_parts[0] if selector_parts else token
                selector = ContainerToken(
                    'SELECTOR', '', '', selector_parts,
                    start.line, start.column)
                declarations, errors = self.parse_declaration_list(
                    token.content)
                ruleset = RuleSet(selector, declarations,
                                  first_token.line, first_token.column)
                return ruleset, errors
            else:
                selector_parts.append(token)
        raise ParseError(token, 'no declaration block found for ruleset')

    def parse_declaration_list(self, tokens):
        """Parse a ';' separated declaration list.

        If you have a block that contains declarations but not only
        (like ``@page`` in CSS 3 Paged Media), you need to extract them
        yourself and use :func:`parse_declaration` directly.

        :param tokens:
            an iterable of tokens. Should stop at (before) the end
            of the block, as marked by a '}'.
        :return:
            a tuple of the list of valid :class`Declaration` and a list
            of :class:`ParseError`

        """
        # split at ';'
        parts = []
        this_part = []
        for token in tokens:
            type_ = token.type
            if type_ == ';':
                if this_part:
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
                declarations.append(self.parse_declaration(part))
            except ParseError as exc:
                errors.append(exc)
                # Skip the entire declaration
        return declarations, errors

    def parse_declaration(self, tokens):
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

        name_token = next(tokens)  # assume there is at least one
        if name_token.type == 'IDENT':
            # CSS syntax is case-insensitive
            property_name = name_token.value.lower()
        else:
            raise ParseError(name_token,
                'expected a property name, got {0}'.format(name_token.type))

        token = name_token  # In case ``tokens`` is now empty
        for token in tokens:
            if token.type == ':':
                break
            elif token.type != 'S':
                raise ParseError(
                    token, "expected ':', got {0}".format(token.type))
        else:
            raise ParseError(token, "expected ':'")

        value = self.parse_value(tokens)
        if not value:
            raise ParseError(token, 'expected a property value')
        value = ContainerToken(
            'VALUES', '', '', value, value[0].line, value[0].column)
        return Declaration(
            property_name, value, name_token.line, name_token.column)

    def parse_value(self, tokens):
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
                    self.validate_block(token.content, 'property value')
                else:
                    self.validate_any(token, 'property value')
                content.append(token)

        # Remove white space at the end
        while content and content[-1].type == 'S':
            content.pop()
        return content

    def validate_block(self, tokens, context):
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
                self.validate_block(token.content, context)
            elif type_ not in (';', 'ATKEYWORD'):
                self.validate_any(token, context)

    def validate_any(self, token, context):
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
                self.validate_any(token, type_)
        elif type_ not in ('S', 'IDENT', 'DIMENSION', 'PERCENTAGE', 'NUMBER',
                           'INTEGER', 'URI', 'DELIM', 'STRING', 'HASH', ':',
                           'UNICODE-RANGE'):
            if type_ in ('}', ')', ']'):
                adjective = 'unmatched'
            else:
                adjective = 'unexpected'
            raise ParseError(token,
                '{0} {1} token in {2}'.format(adjective, type_, context))
