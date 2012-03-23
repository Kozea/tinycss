# coding: utf8
"""
    Tests for the public API
    ------------------------

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import itertools

from tinycss import make_parser
from .test_selectors3 import LXML_INSTALLED


def test_make_parser():
    if not LXML_INSTALLED:  # pragma: no cover
        pytest.skip('lxml not available')

    from tinycss.selectors3 import CSSSelectors3Parser
    from tinycss.page3 import CSSPage3Parser
    classes = (
        ('with_selectors3', CSSSelectors3Parser),
        ('with_page3', CSSPage3Parser),
    )
    classes = dict(
        with_selectors3=CSSSelectors3Parser,
        with_page3=CSSPage3Parser,
   )
    for enabled in itertools.product([True, False], repeat=len(classes)):
        kwargs = dict(zip(sorted(classes), enabled))
        parser_class = make_parser(**kwargs)
        for key, class_ in classes.items():
            assert issubclass(parser_class, class_) == kwargs[key]
