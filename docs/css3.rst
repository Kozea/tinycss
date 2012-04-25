CSS 3 Modules
=============

.. _selectors3:

Selectors 3
-----------

See cssselect_ can be used to parse selectors.

**TODO:** give an example of how to use it with tinycss.

.. _cssselect: http://packages.python.org/cssselect/


.. module:: tinycss.color3

Color 3
-------

This module implements parsing for the *<color>* values, as defined in
`CSS 3 Color <http://www.w3.org/TR/css3-color/>`_.

The (deprecated) CSS2 system colors are not supported, but you can
easily test for them if you want as they are simple ``IDENT`` tokens.
For example::

    if token.type == 'IDENT' and token.value == 'ButtonText':
        return ...

All other values types *are* supported:

* Basic, extended (X11) and transparent color keywords;
* 3-digit and 6-digit hexadecimal notations;
* ``rgb()``, ``rgba()``, ``hsl()`` and ``hsla()`` functional notations.
* ``currentColor``

This module does not integrate with a parser class. Instead, it provides
a function that can parse tokens as found in :attr:`.css21.Declaration.value`,
for example.

.. autofunction:: parse_color
.. autofunction:: parse_color_string
.. autoclass:: RGBA


.. module:: tinycss.page3

Paged Media 3
-------------

.. autoclass:: CSSPage3Parser
.. autoclass:: MarginRule


Other CSS modules
-----------------

To add support for new CSS syntax, see :ref:`extending`.
