# coding: utf8
"""
    tinycss
    -------

    A CSS parser, and nothing else.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


VERSION = '0.1dev'


def make_parser(with_selectors3=False, with_page3=False):
    """Make a parser class with the chosen features.

    :param with_selectors3:
        Enable Selectors 3. This requires lxml.cssselect, and will raise
        :class:`ImportError` if it is not installed.
        See :class:`CSSSelectors3Parser`.
    :param with_page3:
        Enable CSS 3 Paged Media syntax. See :class:`CSSPage3Parser`.
    :returns:
        A new subclass of :class:`CSS21Parser`

    """
    from .css21 import CSS21Parser
    bases = [CSS21Parser]
    if with_selectors3:
        # May raise ImportError if lxml is not installed
        from .selectors3 import CSSSelectors3Parser
        bases.append(CSSSelectors3Parser)
    if with_page3:
        from .page3 import CSSPage3Parser
        bases.append(CSSPage3Parser)

    if len(bases) == 1:
        return bases[0]
    else:
        # Reverse: we want the "most specific" parser to be
        # the first base class.
        return type('CustomCSSParser', tuple(reversed(bases)), {})
