# coding: utf8
"""
    Tests for the CSS 3 color parser
    --------------------------------

    :copyright: (c) 2010 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals
import pytest

from tinycss.color3 import parse_color_string


@pytest.mark.parametrize(('css_source', 'expected_result'), [
    ('', None),
    (' /* hey */\n', None),
    ('4', None),
    ('top', None),
    ('/**/transparent', (0, 0, 0, 0)),
    ('transparent', (0, 0, 0, 0)),
    (' transparent\n', (0, 0, 0, 0)),
    ('TransParent', (0, 0, 0, 0)),
    ('currentColor', 'currentColor'),
    ('CURRENTcolor', 'currentColor'),
    ('current_Color', None),

    ('black', (0, 0, 0, 1)),
    ('white', (1, 1, 1, 1)),
    ('fuchsia', (1, 0, 1, 1)),
    ('cyan', (0, 1, 1, 1)),
    ('darkkhaki', (189 / 255., 183 / 255., 107 / 255., 1)),

    ('#', None),
    ('#f', None),
    ('#ff', None),
    ('#fff', (1, 1, 1, 1)),
    ('#ffg', None),
    ('#ffff', None),
    ('#fffff', None),
    ('#ffffff', (1, 1, 1, 1)),
    ('#fffffg', None),
    ('#fffffff', None),
    ('#ffffffff', None),
    ('#fffffffff', None),

    ('#cba987', (203  / 255., 169 / 255., 135 / 255., 1)),
    ('#1122aa', (17  / 255., 34 / 255., 170 / 255., 1)),
    ('#12a', (17  / 255., 34 / 255., 170 / 255., 1)),

])
def test_color(css_source, expected_result):
    assert parse_color_string(css_source) == expected_result
