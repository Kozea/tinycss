CSS 3 Modules
=============

.. module:: tinycss.selectors3

Selectors 3
-----------

This module is based on `lxml.cssselect <http://lxml.de/cssselect.html>`_.
Importing :mod:`tinycss.selectors3` without lxml installed will raise an
:exc:`~exceptions.ImportError`.

.. autoclass:: CSSSelectors3Parser
.. autoclass:: Selector
    :members: match


.. module:: tinycss.color3

Color 3
-------

This module implements parsing for the *<color>* values defined in
`CSS 3 Color <http://www.w3.org/TR/css3-color/>`_.

The (deprecated) CSS2 system colors are not supported, but you can
easily test for them if you want as they are simple ``IDENT`` tokens::

    if token.type == 'IDENT' and token.value == 'ButtonText':
        return ...

Other values types are supported:

* Basic, extended (X11) and transparent color keywords;
* 3-digit and 6-digit hexadecimal notations;
* ``rgb()``, ``rgba()``, ``hsl()`` and ``hsla()`` functional notations.
* ``currentColor``

This module does not integrate with a parser class. Instead, it provides
a function that can help parse property values, as
:attr:`.css21.Declaration.value` is provided as a list of unparsed tokens.

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
