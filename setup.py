from __future__ import with_statement
import re
import os.path
from setuptools import setup, find_packages, Extension
from Cython.Distutils import build_ext


init_py = os.path.join(os.path.dirname(__file__), 'tinycss', '__init__.py')
with open(init_py) as fd:
    VERSION = re.search("VERSION = '([^']+)'", fd.read()).group(1)


setup(
    name='tinycss',
    version=VERSION,
    url='https://github.com/SimonSapin/tinycss',
    license='BSD',
    author='Simon Sapin',
    author_email='simon.sapin@exyr.org',
    description='A CSS parser, and nothing else.',
    packages=find_packages(),
    cmdclass = {'build_ext': build_ext},
    ext_modules=[Extension(
        'tinycss.speedups',
        sources=[os.path.join('tinycss', 'speedups.pyx')]
    )],
)
