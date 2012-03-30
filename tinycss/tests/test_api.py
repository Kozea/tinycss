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
from tinycss.page3 import CSSPage3Parser
from .test_selectors3 import LXML_INSTALLED


def test_make_parser():

    classes = {'with_page3': CSSPage3Parser}
    if LXML_INSTALLED:  # pragma: no cover
        from tinycss.selectors3 import CSSSelectors3Parser
        classes['with_selectors3'] = CSSSelectors3Parser

    for enabled in itertools.product([True, False], repeat=len(classes)):
        kwargs = dict(zip(sorted(classes), enabled))
        parser = make_parser(**kwargs)
        for key, class_ in classes.items():
            assert isinstance(parser, class_) == kwargs[key]

    class MyParser(object):
        def __init__(self, some_config):
            self.some_config = some_config

    parser = make_parser(MyParser, some_config=42)
    assert isinstance(parser, MyParser)
    assert parser.some_config == 42
