from __future__ import absolute_import, unicode_literals

import os
import sys


template = '''
{name};"<a href=""{file_url}"">{file_url}</a>"
'''.strip()


def targets(srcdir):
    _, base = os.path.split(srcdir)

    for name in os.listdir(srcdir):
        head, ext = os.path.splitext(name)
        path = os.path.join(srcdir, name)
        if os.path.isfile(path) and ext in ['.mp4', '.mkv', '.avi']:
            yield (os.path.join(base, head), path)


if __name__ == '__main__':
    srcdir = sys.argv[1]
    for name, path in targets(srcdir):
        file_url = 'file:/' + path
        print template.format(name=name, file_url=file_url)
