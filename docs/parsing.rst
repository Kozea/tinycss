Parsing with tinycss
====================

.. highlight:: python

Quickstart
----------

Import *tinycss*, make a parser object, and parse a stylesheet:

.. doctest::

    >>> import tinycss
    >>> parser = tinycss.make_parser()
    >>> stylesheet = parser.parse_stylesheet_bytes(b'''@import "foo.css";
    ...     p.error { color: red }''')
    >>> for rule in stylesheet.rules:
    ...     print(rule)
    <ImportRule 1:1 foo.css>
    <RuleSet at 2:5 p.error>

You’ll get a :class:`~tinycss.core.Stylesheet` object which contains
all the parsed content.


Parsers
-------

Parsers are subclasses of :class:`tinycss.css21.CSS21Parser`. Various subclasses
add support for more syntax. You can choose which features to enable
by making a new parser class with multiple inheritance, but there is also
a convenience function to do that:

.. module:: tinycss

.. autofunction:: make_parser(*base_classes, with_selectors3=False, with_page3=False, **kwargs)


.. module:: tinycss.core

Parsing a stylesheet
~~~~~~~~~~~~~~~~~~~~

Parser classes have three different methods to parse CSS stylesheet,
depending on whether you have a file, a byte string, or an Unicode string.

.. automethod:: CoreParser.parse_stylesheet_file
.. automethod:: CoreParser.parse_stylesheet_bytes
.. automethod:: CoreParser.parse_stylesheet


Parsing a ``style`` attribute
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: CoreParser.parse_style_attr


Tokens
------

Some parts of a stylesheet (such as property values) are not parsed
by tinycss. They appear as tokens instead.
All of these objects have :obj:`line` and :obj:`column` attributes (not
repeated every time fore brevity) that indicate where in the CSS source this
object was read.

tinycss does not know which properties and which values a given User Agent
wants to support: it is the UA’s responsibility to ignore unknown and
unsupported values, and fall back on any previous declaration.

.. module:: tinycss.token_data

.. autoclass:: Token()
.. autoclass:: tinycss.speedups.CToken()
.. autoclass:: ContainerToken()

    .. method:: __iter__, __len__

        Shortcuts for accessing :attr:`content`.

.. autoclass:: FunctionToken()


Parsed objects
--------------

These data structures make up the results of the various parsing methods.
All of these objects have :obj:`line` and :obj:`column` attributes (not
repeated every time fore brevity) that indicate where in the CSS source this
object was read.

.. currentmodule:: tinycss.core

.. autoclass:: Stylesheet()
.. autoclass:: ParseError()
.. autoclass:: RuleSet()
.. autoclass:: Declaration()

.. module:: tinycss.css21

.. autoclass:: PropertyDeclaration()
.. autoclass:: PageRule()
.. autoclass:: MediaRule()
.. autoclass:: ImportRule()
