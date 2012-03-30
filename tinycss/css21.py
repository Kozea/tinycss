# coding: utf8
"""
    tinycss.css21
    -------------

    Parser for CSS 2.1
    http://www.w3.org/TR/CSS21/syndata.html

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

    .. attribute:: rules

        A mixed list, in source order, of :class:`RuleSet` and various
        at-rules such as :class:`ImportRule`, :class:`MediaRule`
        and :class:`PageRule`.
        Use their :obj:`at_keyword` attribute to distinguish them.

    .. attribute:: errors

        A list of :class:`ParseError`. Invalid rules and declarations
        are ignored, with the details logged in this list.

    .. attribute:: encoding

        The character encoding that was used to decode the stylesheet
        from bytes, or ``None`` for Unicode stylesheets.

    """
    def __init__(self, rules, errors, encoding):
        self.rules = rules
        self.errors = errors
        self.encoding = encoding

    def __repr__(self):  # pragma: no cover
        return '<{0.__class__.__name__} {1} rules {2} errors>'.format(
            self, len(self.rules), len(self.errors))

    def pretty(self):  # pragma: no cover
        """Return an indented string representation for debugging"""
        lines = [rule.pretty() for rule in self.rules] + [
                 e.message for e in self.errors]
        return '\n'.join(lines)


class ParseError(ValueError):
    """Details about a CSS syntax error. Usually indicates that something
    (a rule or a declaration) was ignored and will not appear as a parsed
    object.

    .. attribute:: line

        Source line where the error occured.

    .. attribute:: column

        Column in the source line where the error occured.

    .. attribute:: reason

        What happend (a string).

    """
    def __init__(self, subject, reason):
        self.line = subject.line
        self.column = subject.column
        self.reason = reason
        self.msg = self.message = (
            'Parse error at {0.line}:{0.column}, {0.reason}'.format(self))
        super(ParseError, self).__init__(self.message)

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__}: {0.message}>'.format(self))


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

        The selecor as a :class:`~tinycss.token_data.ContainerToken` object.
        In CSS 3 terminology, this is actually a selector group.

    .. attribute:: declarations

        The list of :class:`Declaration`, in source order.

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

    .. attribute:: value

        The property value as a :class:`~tinycss.token_data.ContainerToken`.

        The value is not parsed. UAs using tinycss may only support
        some properties or some values and tinycss does not know which.
        They need to parse values themselves and ignore declarations with
        unknown or unsupported properties or values, and fall back
        on any previous declaration.

        :mod:`tinycss.colors3` parses color values, but other values
        will need specific parsing/validation code.

    .. attribute:: priority

        Either the string ``'important'`` or ``None``.

    """
    def __init__(self, name, value, priority, line, column):
        self.name = name
        self.value = value
        self.priority = priority
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        priority = ' !' + self.priority if self.priority else ''
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.name}: {0.value.as_css}{1}>'.format(self, priority))

    def pretty(self):  # pragma: no cover
        """Return an indented string representation for debugging"""
        lines = [self.name + ':']
        for token in self.value.content:
            for line in token.pretty().splitlines():
                lines.append('    ' + line)
        return '\n'.join(lines)


class PageRule(object):
    """A parsed CSS 2.1 @page rule.

    .. attribute:: at_keyword

        Always ``'@page'``

    .. attribute:: selector

        The page selector.
        In CSS 2.1 this is either ``None`` (no selector), or the string
        ``'first'``, ``'left'`` or ``'right'`` for the pseudo class
        of the same name.

    .. attribute:: specificity

        Specificity of the page selector. This is a tuple of four integers,
        but these tuples are mostly meant to be compared to each other.

    .. attribute:: declarations

        A list of :class:`Declaration`, in source order.

    .. attribute:: at_rules

        The list of parsed at-rules inside the @page block, in source order.
        Always empty for CSS 2.1.

    """
    at_keyword = '@page'

    def __init__(self, selector, specificity, declarations, at_rules,
                 line, column):
        self.selector = selector
        self.specificity = specificity
        self.declarations = declarations
        self.at_rules = at_rules
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.selector}>'.format(self))


class MediaRule(object):
    """A parsed @media rule.

    .. attribute:: at_keyword

        Always ``'@media'``

    .. attribute:: media

        For CSS 2.1 without media queries: the media types
        as a list of strings.

    .. attribute:: rules

        The list :class:`RuleSet` and various at-rules inside the @media
        block, in source order.

    """
    at_keyword = '@media'

    def __init__(self, media, rules, line, column):
        self.media = media
        self.rules = rules
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.media}>'.format(self))


class ImportRule(object):
    """A parsed @import rule.

    .. attribute:: at_keyword

        Always ``'@import'``

    .. attribute:: uri

        The URI to be imported, as read from the stylesheet.
        (URIs are not made absolute.)

    .. attribute:: media

        For CSS 2.1 without media queries: the media types
        as a list of strings.
        This attribute is explicitly ``['all']`` if the media was omitted
        in the source.

    """
    at_keyword = '@import'

    def __init__(self, uri, media, line, column):
        self.uri = uri
        self.media = media
        self.line = line
        self.column = column

    def __repr__(self):  # pragma: no cover
        return ('<{0.__class__.__name__} {0.line}:{0.column}'
                ' {0.uri}>'.format(self))



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


class CSS21Parser(object):
    """Parser for CSS 2.1

    This parser supports the core CSS syntax as well as @import, @media,
    @page and !important.

    Note that property values are still not parsed, as UAs using this
    parser may only support some properties or some values.

    Currently the parser holds no state. It being a class only allows
    subclassing and overriding its methods.

    """

    # User API:

    def parse_stylesheet_file(self, css_file, protocol_encoding=None,
                             linking_encoding=None, document_encoding=None):
        """Parse a stylesheet from a file or filename.

        Character encoding-related parameters and behavior are the same
        as in :meth:`parse_stylesheet_bytes`.

        :param css_file:
            Either a file (any object with a :meth:`~file.read` method)
            or a filename.
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
        If no encoding information is available or decoding fails,
        decoding defaults to UTF-8 and then fall back on ISO-8859-1.

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
        rules = self.parse_rules(
            tokens, errors, context='stylesheet')
        return Stylesheet(rules, errors, encoding)

    def parse_style_attr(self, css_source):
        """Parse a "style" attribute (eg. of an HTML element).

        This method only accepts Unicode as the source (HTML) document
        is supposed to handle the character encoding.

        :param css_source:
            The attribute value, as an unicode string.
        :return:
            A tuple of the list of valid :class:`Declaration` and
            a list of :class:`ParseError`.
        """
        return self.parse_declaration_list(tokenize_grouped(css_source))

    # API for subclasses:

    def parse_rules(self, tokens, errors, context):
        """Parse a sequence of rules (rulesets and at-rules).

        :param tokens:
            An iterable of tokens.
        :param errors:
            A list where to append encountered :class:`ParseError`
        :param context:
            Either 'stylesheet' or an at-keyword such as '@media'.
            (Some at-rules are only allowed in some contexts.)
        :return:
            A list of parsed rules.

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
        if rule.at_keyword == '@page':
            if context != 'stylesheet':
                raise ParseError(rule, '@page rule not allowed in ' + context)
            selector, specificity = self.parse_page_selector(rule.head)
            if rule.body is None:
                raise ParseError(rule,
                    'invalid {0} rule: missing block'.format(rule.at_keyword))
            declarations, at_rules = self.parse_page_block(rule.body, errors)
            return PageRule(selector, specificity, declarations, at_rules,
                            rule.line, rule.column)

        elif rule.at_keyword == '@media':
            if context != 'stylesheet':
                raise ParseError(rule, '@media rule not allowed in ' + context)
            if not rule.head:
                raise ParseError(rule.body, 'expected media types for @media')
            media = self.parse_media(rule.head)
            if rule.body is None:
                raise ParseError(rule,
                    'invalid {0} rule: missing block'.format(rule.at_keyword))
            rules = self.parse_rules(
                rule.body.content, errors, '@media')
            return MediaRule(media, rules, rule.line, rule.column)

        elif rule.at_keyword == '@import':
            if context != 'stylesheet':
                raise ParseError(rule,
                    '@import rule not allowed in ' + context)
            for previous_rule in previous_rules:
                if previous_rule.at_keyword not in ('@charset', '@import'):
                    if previous_rule.at_keyword:
                        type_ = 'an {0} rule'.format(previous_rule.at_keyword)
                    else:
                        type_ = 'a ruleset'
                    raise ParseError(previous_rule,
                        '@import rule not allowed after ' + type_)
            head = rule.head
            if not head:
                raise ParseError(rule,
                    'expected URI or STRING for @import rule')
            if head[0].type not in ('URI', 'STRING'):
                raise ParseError(rule,
                    'expected URI or STRING for @import rule, got '
                    + head[0].type)
            uri = head[0].value
            if len(head) == 1:
                media = ['all']
            else:
                for i, token in enumerate(head[1:], 1):
                    if token.type != 'S':
                        media = self.parse_media(head[i:])
                        break
                else:  # pragma: no cover
                    # This is unreachable since the core parser has removed
                    # any trailing white space in head.
                    media = ['all']
            if rule.body is not None:
                raise ParseError(rule.body, "expected ';', got a block")
            return ImportRule(uri, media, rule.line, rule.column)

        elif rule.at_keyword == '@charset':
            raise ParseError(rule, 'mis-placed or malformed @charset rule')

        else:
            raise ParseError(rule, 'unknown at-rule in {0} context: {1}'
                                    .format(context, rule.at_keyword))

    def parse_media(self, tokens):
        """For CSS 2.1, parse a list of media types.

        Media Queries are expected to override this.

        :param tokens:
            An non-empty iterable of tokens
        :raises:
            :class:`ParseError` on invalid media types/queries
        :returns:
            For CSS 2.1, a list of media types as strings
        """
        media_types = []
        tokens = iter(tokens)
        token = next(tokens)
        while 1:
            if token.type == 'IDENT':
                media_types.append(token.value.lower())
            else:
                raise ParseError(token,
                    'expected a media type, got {0}'.format(token.type))
            token = next(tokens, None)
            if not token:
                return media_types
            if not (token.type == 'DELIM' and token.value == ','):
                raise ParseError(token,
                    'expected a comma, got {0}'.format(token.type))
            while 1:
                next_token = next(tokens, None)
                if not next_token:
                    raise ParseError(token, 'expected a media type')
                token = next_token
                if token.type != 'S':
                    break

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
            return None, (0, 0)
        if (len(head) == 2 and head[0].type == ':'
                and head[1].type == 'IDENT'):
            pseudo_class = head[1].value
            specificity = {
                'first': (1, 0), 'left': (0, 1), 'right': (0, 1),
            }.get(pseudo_class)
            if specificity:
                return pseudo_class, specificity
        raise ParseError(head[0], 'invalid @page selector')

    def parse_page_block(self, body, errors):
        """Parse the body of an @page rule.

        :param body:
            The ``body`` attribute of an unparsed :class:`AtRule`.
        :param errors:
            A list where to append encountered :class:`ParseError`
        :returns:
            A tuple of:

            * A list of :class:`Declaration`
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
                    result = self.parse_at_rule(
                        rule, at_rules, errors, '@page')
                    at_rules.append(result)
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
                while selector_parts and selector_parts[-1].type == 'S':
                    selector_parts.pop()
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
        value, priority = self.parse_value_priority(value)
        value = ContainerToken(
            'VALUES', '', '', value, value[0].line, value[0].column)
        return Declaration(
            property_name, value, priority, name_token.line, name_token.column)

    def parse_value_priority(self, original_value):
        """Take a list of tokens and separate any !important marker.
        """
        value = list(original_value)
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
                            token, 'expected a value before !important')
                    return value, 'important'
                # Skip white space between '!' and 'important'
                elif token.type != 'S':
                    break
        return original_value, None

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
