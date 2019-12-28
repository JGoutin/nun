#! /usr/bin/env python3
#  coding=utf-8
"""Setup script

run "./setup.py --help-commands" for help.
"""
from datetime import datetime
from os import chdir
from os.path import dirname, abspath, join

from setuptools import setup, find_packages

# Sets Package information
PACKAGE_INFO = dict(
    name='nun',
    description='Package manager',
    long_description_content_type='text/markdown; charset=UTF-8',
    classifiers=[
        # Must be listed on: https://pypi.org/classifiers/
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: BSD',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Software Distribution',
        'Topic :: Utilities',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='package manager',
    author='JGoutin',
    url='https://github.com/jgoutin/nun',
    project_urls={
        'Documentation': 'https://nun.readthedocs.io',
        'Download': 'https://pypi.org/project/nun',
    },
    license='GPLv3',
    python_requires='>=3.6',
    install_requires=[
        'argcomplete>=1.10',
        'requests>=2.20.0',
        'python-dateutil>=2.6.0'
    ],
    setup_requires=['setuptools'],
    tests_require=['pytest'],
    packages=find_packages(exclude=['docs', 'tests']),
    zip_safe=True,
    command_options={},
    entry_points={'console_scripts': ['nun=nun.__main__:_run_command']})

# Gets package __version__ from package
SETUP_DIR = abspath(dirname(__file__))
with open(join(SETUP_DIR, 'nun', '__init__.py')) as source_file:
    for line in source_file:
        if line.rstrip().startswith('__version__'):
            PACKAGE_INFO['version'] = line.split('=', 1)[1].strip(" \"\'\n")
            break

# Gets long description from readme
with open(join(SETUP_DIR, 'readme.md')) as source_file:
    PACKAGE_INFO['long_description'] = source_file.read()

# Gets Sphinx configuration
PACKAGE_INFO['command_options']['build_sphinx'] = {
    'project': ('setup.py', PACKAGE_INFO['name'].capitalize()),
    'version': ('setup.py', PACKAGE_INFO['version']),
    'release': ('setup.py', PACKAGE_INFO['version']),
    'copyright': ('setup.py', '2019-%s, %s' % (
        datetime.now().year, PACKAGE_INFO['author']))}

# Runs setup
if __name__ == '__main__':
    chdir(SETUP_DIR)
    setup(**PACKAGE_INFO)
