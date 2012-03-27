tinycss: CSS parser for Python
==============================

*tinycss* is a complete yet simple CSS parser for Python. It supports the full
syntax and error handling for CSS 2.1 as well as some CSS 3 modules.
It is designed to be easy to extend for new CSS modules.


Quick facts:

* Free software: BSD licensed
* Compatible Python 2.6+ and 3.x
* Source, issues and pull requests `on Github`_
* Releases `on PyPI`_
* Install with ``pip install tinycss``

.. _on Github: https://github.com/SimonSapin/tinycss/
.. _on PyPI: http://pypi.python.org/pypi/tinycss


Supported syntax:

* CSS 2.1
* Selectors 3 (with matching in *lxml* documents)
* CSS Color 3
* CSS Paged Media 3


.. Contents:

.. toctree::
   :maxdepth: 2


Requirements
------------

tinycss is tested on CPython 2.6, 2.7, 3.1 and 3.2 as well as PyPy 1.8;
it should work on any implementation of **Python 2.6 or later version
(including 3.x)** of the language.

`lxml <http://lxml.de/>`_ is required for the :mod:`~tinycss.selectors3`
module, but not for the base parser or other modules.

`Cython <http://cython.org/>`_ is used for optional accelerators.


Installation
------------

Installing with `pip <http://www.pip-installer.org/>`_ should Just Work:

.. code-block:: sh

    pip install tinycss

The release tarballs contain pre-*cythoned* C files for the accelerators:
you will not need Cython to install like this.
If the accelerators fail to build for some reason, tinycss will
print a warning and fall back on a pure-Python installation.
