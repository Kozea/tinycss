# coding: utf8
"""
    tinycss
    -------

    A CSS parser, and nothing else.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

import sys

from .version import VERSION
__version__ = VERSION


def make_parser(*base_classes, **kwargs):
    """Make a parser object with the chosen features.

    :param base_classes:
        Positional arguments are base classes the new parser
        class will extend.
    :param with_selectors3:
        Add :class:`CSSSelectors3Parser` to :obj:`base_classes`: enable
        parsing and matching of level 3 selectors.
        This requires lxml.cssselect, and will raise
        :class:`ImportError` if it is not installed.
    :param with_page3:
        Add :class:`CSSPage3Parser` to :obj:`base_classes`: enable
        CSS 3 Paged Media syntax.
    :param kwargs:
        Other arguments are passed to the parser’s constructor.
    :returns:
        An instance of a new subclass of :class:`CSS21Parser`

    """
    from .css21 import CSS21Parser
    bases = [CSS21Parser]

    for module, class_name in PARSER_MODULES:
        if kwargs.pop('with_' + module, False):
            module = '.'.join([__name__, module])
            __import__(module)
            bases.append(getattr(sys.modules[module], class_name))

    bases.extend(base_classes)

    if len(bases) == 1:
        parser_class = bases[0]
    else:
        # Reverse: we want the "most specific" parser to be
        # the first base class.
        parser_class = type('CustomCSSParser', tuple(reversed(bases)), {})
    return parser_class(**kwargs)


PARSER_MODULES = [
    ('selectors3', 'CSSSelectors3Parser'),
    ('page3', 'CSSPage3Parser'),
]
