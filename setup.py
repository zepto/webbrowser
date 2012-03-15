#!/usr/bin/env python

import copy, os, re, sha, string, sys, urllib, urlparse, shutil, stat

try:
    import distutils.core
    from distutils.command import install
except ImportError:
    raise SystemExit, """\
You don't have the python development modules installed.  

If you have Debian you can install it by running
    apt-get install python-dev

If you have RedHat and know how to install this from an RPM please
email us so we can put instructions here.
"""

# this makes 'data_files' install into the python package folder
for scheme in install.INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']
    
setup_args = {
    'name': 'webbrowser',
    'version': '0.0.18',
    'description':  'A python webkit web browser.',
    'long_description': """\
webbrowser is a python webkit web browser.
""",

    'author': 'Josiah Gordon',
    'author_email': 'josiahg@gmail.com',

    'license': 'GPLv3',
    'scripts': ['webbrowser',],
    'data_files': [
                    ('/usr/lib/', ['browser'],),
                    ('/usr/share/applications/', ['webbrowser.desktop'],),
                    ('/usr/share/doc/webbrowser-0.0.17/', ['browser/plugins/block.uri', 'browser/plugins/movie.uri'],),
                    ],

    'classifiers': [
        'Development Status :: 2 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Environment :: X11 Applications ',
        'Topic :: Network ',
    ],
                                                            
    'packages': [
        'browser', 
        'browser/plugins',
        'browser/plugins/youtube_downloader',
    ],
}
# patch distutils if it can't cope with the "classifiers" or
# "download_url" keywords
if sys.version < '2.2.3':
    from distutils.dist import DistributionMetadata
    DistributionMetadata.classifiers = None
    DistributionMetadata.download_url = None

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "posix"

if __name__ == '__main__':
    distutils.core.setup(**setup_args)



