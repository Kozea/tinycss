.. _extending:

Extending the parser
====================

Various modules such as :mod:`.selectors3` and :mod:`.page3` extend the
CSS 2.1 parser to add support for some CSS 3 syntax.
They do so by sub-classing :class:`.css21.CSS21Parser` and overriding/extending
some of its methods. If fact, the parser is made of methods in a class
(rather than a set of functions) solely to enable this kind of sub-classing.

tinycss is designed to enable you to have parser subclasses outside of
tinycss, without monkey-patching. If however the syntax you added is for a
W3C specification, consider including your subclass in a new tinycss module
and send a pull request: see :ref:`hacking`.


.. currentmodule:: tinycss.css21

Parser methods
--------------

In addition to methods of the user API (see :ref:`parsing`), here
are the methods of the CSS 2.1 parser that can be overriden or extended:

.. automethod:: CSS21Parser.parse_rules
.. automethod:: CSS21Parser.read_at_rule
.. automethod:: CSS21Parser.parse_at_rule
.. automethod:: CSS21Parser.parse_media
.. automethod:: CSS21Parser.parse_page_selector
.. automethod:: CSS21Parser.parse_declarations_and_at_rules
.. automethod:: CSS21Parser.parse_ruleset
.. automethod:: CSS21Parser.parse_declaration_list
.. automethod:: CSS21Parser.parse_declaration
.. automethod:: CSS21Parser.parse_value_priority

Unparsed at-rules
-----------------

.. autoclass:: AtRule


.. module:: tinycss.parsing

Parsing helper functions
------------------------

The :mod:`tinycss.parsing` module contains helper functions for parsing
tokens into a more structured form:

.. autofunction:: strip_whitespace
.. autofunction:: split_on_comma
.. autofunction:: validate_value
.. autofunction:: validate_block
.. autofunction:: validate_any
