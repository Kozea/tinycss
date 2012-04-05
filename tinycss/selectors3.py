# coding: utf8
"""
    tinycss.selectors3
    ------------------

    Helpers for selectors:
    http://www.w3.org/TR/css3-selectors/

    This module integrates lxml.cssselect in tinycss:
    http://lxml.de/cssselect.html

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from __future__ import unicode_literals, division

from .tokenizer import tokenize_grouped
from .parsing import split_on_comma
from .css21 import CSS21Parser, ParseError

try:
    from lxml import cssselect
except ImportError as exc:
    exc.message = exc.msg = (
        __name__ + ' depends on lxml.cssselect. Please install lxml '
        'with "pip install lxml" or from http://lxml.de/')
    exc.args = (exc.message,)
    raise


#: The specificity for declarations in the "style" attribute of HTML elements
#: or equivalent.
STYLE_ATTRIBUTE_SPECIFICITY = (1, 0, 0, 0)


class Selector(object):
    """A Level 3 selector.

    In CSS 3, each ruleset has a list of comma-separated selectors.
    A :class:`Selector` object represents one of these selectors.
    These selectors optionally have one *pseudo-element* that must be
    at the end.

    .. commented for now: this is expected to change
    .. .. attribute:: parsed_selector

        The selector parsed as a tree of cssselect internal objects.

    .. attribute:: pseudo_element

        One of ``'before'``, ``'after'``, ``'first-letter'``, ``'first-line'``
        or ``None``.

    .. attribute:: specificity

        The specificity of this selector. This is a tuple of four integers,
        but these tuples are mostly meant to be compared to each other.

    """
    def __init__(self, parsed_selector, pseudo_element, specificity, match):
        self.parsed_selector = parsed_selector
        self.pseudo_element = pseudo_element
        self.specificity = specificity
        # Mask the method (class attribute) with a callable instance attribute.
        self.match = match

    def match(self, lxml_element, **kwargs):
        """Find elements in an XML or HTML document that match the part
        of this selector before any *pseudo-element*.

        This is based on :mod:`lxml.cssselect`, so the document must
        have been parsed with lxml, not another implementation of the
        ElementTree API.

        Keyword arguments are passed to the underlying
        :class:`lxml.etree.XPath` object. In particular, a `namespaces`_
        dict can be passed.

        .. _namespaces: http://lxml.de/xpathxslt.html#namespaces-and-prefixes

        :param lxml_element:
            A lxml :class:`~lxml.etree.Element` or
            :class:`~lxml.etree.ElementTree`.
        :returns:
            The list of elements inside this tree that match the selector.
            Remember to consider :attr:`pseudo_element` separately.

        """
        # This dummy method is mostly here to hold its docstring,
        # it just calls the instance attribute.
        assert 'match' in vars(self)
        return self.match(document, **kwargs)


class InvalidSelectorError(ValueError):
    """The parsed selector does not match the Selectors 3 grammar."""


def parse_selector_group_string(css_string):
    """Parse a Level 3 selector group.

    A selector group is a list of comma-separated selectors. This is
    what you find in front of a CSS ruleset.

    :param css_string:
        An Unicode string for a selector, as read in a stylesheet.
    :raises:
        :class:`InvalidSelectorError` if any of the selectors is invalid
        or unsupported.
    :returns:
        A list of :class:`Selector` objects.

    """
    return _parse_selector_group_tokens(tokenize_grouped(css_string))


def _parse_selector_group_tokens(group_tokens):
    return [parse_selector_string(''.join(t.as_css() for t in tokens))
            for tokens in split_on_comma(group_tokens)]


def parse_selector_string(css_string):
    """Parse a single Level 3 selector.

    Note that what you find in front of a CSS ruleset is a *group of
    selectors*, ie. a list of comma-separated selectors. This function
    only parses a single selector.

    If you have a group of selectors in a string, use
    :func:`parse_selector_group_string`.

    :param css_string:
        An Unicode string for a selector, as read in a stylesheet.
    :raises:
        :class:`InvalidSelectorError` if the selector is invalid
        or unsupported.
    :returns:
        A :class:`Selector` object.

    """
    css_string = css_string.strip()
    if not css_string:
        # Work around a cssselect bug: https://github.com/lxml/lxml/pull/36
        # (cssselect parses the empty string as '*')
        raise InvalidSelectorError('empty selector')
    try:
        parsed_selector = cssselect.parse(css_string)
    except cssselect.SelectorSyntaxError as exc:
        # TODO: distinguish invalid and unsupported?
        raise InvalidSelectorError(exc.args[0])

    if isinstance(parsed_selector, cssselect.Or):
        raise InvalidSelectorError('expected a single selector, '
                                   'got a selector group')

    pseudo_element = None
    if isinstance(parsed_selector, cssselect.CombinedSelector):
        simple_selector = parsed_selector.subselector
        if isinstance(simple_selector, cssselect.Pseudo) \
                and simple_selector.ident in (
                    'before', 'after', 'first-line', 'first-letter'):
            pseudo_element = str(simple_selector.ident).lstrip(':')
            # Remove the pseudo-element from the selector
            parsed_selector.subselector = simple_selector.element
    elif isinstance(parsed_selector, cssselect.Pseudo) \
            and parsed_selector.ident in (
                'before', 'after', 'first-line', 'first-letter'):
        pseudo_element = str(parsed_selector.ident).lstrip(':')
        # Remove the pseudo-element from the selector
        parsed_selector = parsed_selector.element

    # a, b, c and d as in CSS 2.1
    # http://www.w3.org/TR/CSS21/cascade.html#specificity
    a = 0  # not a style attribute
    b, c, d = _calculate_specificity(parsed_selector)
    if pseudo_element:
        d += 1
    specificity = (a, b, c, d)

    try:
        match = cssselect.CSSSelector(parsed_selector)
    except (cssselect.ExpressionError, NotImplementedError) as exc:
        raise InvalidSelectorError(
            exc.args[0] if exc.args else 'not implemented')
    return Selector(parsed_selector, pseudo_element, specificity, match)


def _calculate_specificity(parsed_selector):
    """Return the (a, b, c) part of the specificity.
    (In CSS 3 terms. (b, c, d) in CSS 2.1 terms)

    ``parsed_selector`` is assumed to be a single selector (not a selector
    group) with any pseudo-element already removed.

    """
    # All Function selectors in CSS 3 are functional pseudo-classes
    if isinstance(parsed_selector, cssselect.Element):
        c = 1 if parsed_selector.element != '*' else 0
        return 0, 0, c
    elif isinstance(parsed_selector, cssselect.Pseudo):
        a, b, c = _calculate_specificity(parsed_selector.element)
        return a, b + 1, c
    elif isinstance(parsed_selector, (cssselect.Class, cssselect.Function,
                                      cssselect.Attrib)):
        a, b, c = _calculate_specificity(parsed_selector.selector)
        return a, b + 1, c
    elif isinstance(parsed_selector, cssselect.Hash):
        a, b, c = _calculate_specificity(parsed_selector.selector)
        return a + 1, b, c
    else:
        assert isinstance(parsed_selector, cssselect.CombinedSelector)
        a1, b1, c1 = _calculate_specificity(parsed_selector.selector)
        a2, b2, c2 = _calculate_specificity(parsed_selector.subselector)
        return a1 + a2, b1 + b2, c1 + c2


class CSSSelectors3Parser(CSS21Parser):
    """Extend :class:`~.css21.CSS21Parser` to add parsing and matching of
    `Level 3 Selectors <http://www.w3.org/TR/selectors/>`_.

    Compared to CSS 2.1, :class:`~.css21.RuleSet` objects get a new'
    ``selector_list`` attribute set to the list of parsed :class:`Selector`
    objects for this ruleset.

    Also, whole rulesets are ignored (with a logged
    :class:`~.parsing.ParseError`) if they have an invalid selector.

    """
    def parse_ruleset(self, first_token, tokens):
        ruleset, errors = super(CSSSelectors3Parser, self).parse_ruleset(
            first_token, tokens)
        try:
            ruleset.selector_list = _parse_selector_group_tokens(
                ruleset.selector)
        except InvalidSelectorError as exc:
            # Invalidate the whole ruleset even if some selectors
            # in the selector group are valid.
            raise ParseError(ruleset.selector, exc.args[0])
        return ruleset, errors
