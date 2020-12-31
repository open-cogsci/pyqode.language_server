#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This setup script packages pyqode.language_server
"""
import sys
import os
from setuptools import setup, find_packages
from pyqode.language_server import __version__


DESCRIPTION = 'Adds language-server support to pyqode.core'


def readme():
    if 'bdist_deb' in sys.argv:
        return DESCRIPTION
    return str(open('README.rst').read())


pypi_release = os.environ.get('PYPI_RELEASE', 0)

requirements = [
    'pyqode3.python' if pypi_release else 'pyqode.python',
]
setup(
    name=(
        'pyqode3.language_server'
        if pypi_release
        else 'pyqode.language_server'
    ),
    namespace_packages=['pyqode'],
    version=__version__,
    packages=[p for p in find_packages() if 'test' not in p],
    keywords=["CodeEdit PySide PyQt code editor widget lsp language-server"],
    package_dir={'pyqode': 'pyqode'},
    url='https://github.com/open-cogsci/pyqode.language_server',
    license='MIT',
    author='Sebastiaan Mathot',
    author_email='s.mathot@cogsci.nl',
    description=DESCRIPTION,
    long_description=readme(),
    install_requires=requirements,
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: X11 Applications :: Qt',
        'Environment :: Win32 (MS Windows)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Widget Sets',
        'Topic :: Text Editors :: Integrated Development Environments (IDE)'
    ]
)
