# coding: utf8
"""
    Speed tests
    -----------

    Note: this file is not named test_*.py as it is not part of the
    test suite ran by pytest.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from __future__ import unicode_literals, division

import sys
import os.path
import contextlib
import timeit
import functools

from cssutils import parseString

from .. import tokenizer
from ..css21 import CSS21Parser
from ..parsing import remove_whitespace


CSS_REPEAT = 4
TIMEIT_REPEAT = 3
TIMEIT_NUMBER = 20


def load_css():
    filename = os.path.join(os.path.dirname(__file__),
                            '..', '..', 'docs', '_static', 'custom.css')
    with open(filename, 'rb') as fd:
        return b'\n'.join([fd.read()] * CSS_REPEAT)


# Pre-load so that I/O is not measured
CSS = load_css()


@contextlib.contextmanager
def install_tokenizer(name):
    original = tokenizer.tokenize_flat
    try:
        tokenizer.tokenize_flat = getattr(tokenizer, name)
        yield
    finally:
        tokenizer.tokenize_flat = original


def parse(tokenizer_name):
    with install_tokenizer(tokenizer_name):
        stylesheet = CSS21Parser().parse_stylesheet_bytes(CSS)
    result = []
    for rule in stylesheet.rules:
        selector = ''.join(s.as_css for s in rule.selector)
        declarations = [
            (declaration.name, len(list(remove_whitespace(declaration.value))))
            for declaration in rule.declarations]
        result.append((selector, declarations))
    return result

parse_cython = functools.partial(parse, 'cython_tokenize_flat')
parse_python = functools.partial(parse, 'python_tokenize_flat')


def parse_cssutils():
    stylesheet = parseString(CSS)
    result = []
    for rule in stylesheet.cssRules:
        selector = rule.selectorText
        declarations = [
            (declaration.name, len(list(declaration.propertyValue)))
            for declaration in rule.style.getProperties(all=True)]
        result.append((selector, declarations))
    return result


def check_consistency():
    #import pprint
    #pprint.pprint(parse_python())
    result = parse_cython()
    assert len(result) > 0
    assert parse_python() == result
    assert parse_cssutils() == result
    version = '.'.join(map(str, sys.version_info[:3]))
    print('Python {}, consistency OK.'.format(version))


def time(function):
    seconds = timeit.Timer(function).repeat(TIMEIT_REPEAT, TIMEIT_NUMBER)
    miliseconds = int(min(seconds) * 1000)
    return miliseconds


def run():
    data_set = [
        ('tinycss + speedups      ', parse_cython),
        ('tinycss WITHOUT speedups', parse_python),
#        ('cssutils                ', parse_cssutils),
    ]
    label, function = data_set.pop(0)
    ref = time(function)
    print('{}  {} ms'.format(label, ref))
    for label, function in data_set:
        result = time(function)
        print('{}  {} ms  {:.2f}x'.format(label, result, result / ref))


if __name__ == '__main__':
    check_consistency()
    run()
