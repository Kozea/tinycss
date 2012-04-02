.. _hacking:

Hacking tinycss
===============

.. highlight:: sh

Bugs and feature requests
-------------------------

Bug reports, feature requests and other issues should got to the
`tinycss issue tracker`_ on Github. Any suggestion or feedback is welcome.
Please include in full any error message, trackback or other detail that
could be helpful.

.. _tinycss issue tracker: https://github.com/SimonSapin/tinycss/issues


Installing the development version
----------------------------------

First, get the latest git version::

    git clone https://github.com/SimonSapin/tinycss.git
    cd tinycss

Cython_ is required. lxml_ is used by the :mod:`~tinycss.selectors3`, but
is otherwise optional. pytest_ is used to run the test suite. Installing in
a virtualenv_ is recommended::

    virtualenv env
    . env/bin/activate
    pip install Cython lxml pytest

.. _Cython: http://cython.org/
.. _lxml: http://lxml.de/
.. _pytest: http://pytest.org/
.. _virtualenv: http://www.virtualenv.org/

You can omit lxml in the command above if you don’t intend to work on
selectors.

Then, install tinycss in-place with pip’s *editable mode*. This will also
build the accelerators::

    pip install -e .


Running the test suite
----------------------

Once you have everything installed (see above), just run pytest from the
*tinycss* directory::

    py.test

If you chose not to install lxml, use the ``TINYCSS_SKIP_LXML_TESTS``
environment variable::

    TINYCSS_SKIP_LXML_TESTS=1 py.test

Similarly, there is a ``TINYCSS_SKIP_SPEEDUPS_TESTS`` environment variable
if the accelerators are not available for some reason.

If you get test failures on a fresh git clone, something may have gone wrong
during the installation. Otherwise, you probably found a bug. Please
`report it <#bugs-and-feature-requests>`_.


Test in multiple Python versions with tox
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

tox_ automatically creates virtualenvs for various Python versions and
runs the test suite there::

    pip install tox

Change to the project’s root directory and just run::

    tox

.. _tox: http://tox.testrun.org/

tinycss pre-configures tox to test in CPython 2.6, 2.7, 3.1 and 3.2 as well as
PyPy, but you can change that with the ``-e`` parameter. Eg::

    tox -e py27,py32

If you use ``--`` in the arguments passed to tox, further arguments
are passed to the underlying ``py.test`` command::

    tox -- -x --pdb


Building the documentation
--------------------------

This documentation is made with Sphinx_::

    pip install Sphinx

.. _Sphinx: http://sphinx.pocoo.org/

To build the HTML version of the documentation, change to the project’s root
directory and run::

    python setup.py build_sphinx

The built HTML files are in ``docs/_build/html``.


Making a patch and a pull request
---------------------------------

If you would like to see something included in tinycss, please fork
`the repository <https://github.com/SimonSapin/tinycss/>`_ on Github
and make a pull request. Make sure to include tests for your change.


Mailing-list
------------

tinycss does not have a mailing-list of its own for now, but the
`WeasyPrint mailing-list <http://weasyprint.org/community/>`_
is appropriate to discuss it.
