# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from math import ceil, floor
import multiprocessing
import os
from pprint import pprint
import re
import subprocess
import sys

import pysrt


def main(srcpattern, dstdir, seconds):
    plan = build_plan(srcpattern, dstdir, seconds)
    prompt_plan(plan)

    pool = multiprocessing.Pool(processes=4)
    for vpath, spath, outbase, slices in plan:
        for i, (start, end) in enumerate(slices, 1):
            dstroot = '{}.{:02d}'.format(outbase, i)
            pool.apply_async(chop, (vpath, spath, dstroot, start, end))
    pool.close()
    pool.join()


def build_plan(srcpattern, dstdir, seconds):
    srcdir, pattern = os.path.split(srcpattern)
    pattern = pattern.replace('N', '\d')
    vpaths = detect_targets(srcdir, pattern, ['.avi', '.mp4', '.mkv'])
    spaths = detect_targets(srcdir, pattern, ['.srt'])
    plan = []
    for key, vpath in vpaths.viewitems():
        if key in spaths:
            spath = spaths[key]
            slices = compute_slices_by_srt(spath, seconds)
        else:
            spath = None
            slices = compute_slices_by_duration(vpath, seconds)

        outbase = os.path.join(dstdir, key)
        plan.append((vpath, spath, outbase, slices))
    return sorted(plan, key=lambda t: t[2])


def detect_targets(srcdir, pattern, exts):
    paths = [os.path.join(srcdir, name) for name in os.listdir(srcdir)]
    paths = [p for p in paths if os.path.isfile(p)]
    results = {}
    for path in paths:
        _, ext = os.path.splitext(path)
        m = re.search(pattern, path, flags=re.IGNORECASE)
        if ext in exts and  m is not None:
            key = m.group(0).lower()
            results[key] = path
    return results


def compute_slices_by_srt(spath, seconds, padding=1):
    subs = pysrt.open(spath)
    seconds, padding = {'seconds': seconds}, {'seconds': padding}
    head, intervals = None, []
    for s in subs:
        if head is None:
            head = s.start - padding  # SubRipTime clamps negatives to zero
        term = s.end - head
        if term >= seconds:
            tail = s.end + padding  # ffmpeg clamps ranges into durations
            intervals.append((head, tail))
            head = None

    # Merge remainings into the last piece
    if head is not None:
        head, _ = intervals[-1]
        tail = subs[-1].end + padding
        intervals[-1] = (head, tail)

    # Return intervals as seconds
    return [(int(floor(a.ordinal/1000.)), int(ceil(b.ordinal/1000.)))
            for a, b in intervals]


def compute_slices_by_duration(vpath, seconds, padding=1):
    pos, duration = 0, read_duration(vpath)
    intervals = [(max(0, i*seconds-padding),
                  min((i+1)*seconds+padding, duration))
                 for i in range(duration//seconds)]

    s, e = intervals[-1]
    remainings = duration % seconds
    intervals[-1] = (s, e + remainings)
    return intervals


def read_duration(vpath):
    command = 'ffmpeg -i "{vpath}" 2>&1 | '\
              'grep -o "Duration: \d\d:\d\d:\d\d"'.format(vpath=vpath)
    output = subprocess.check_output(command, shell=True)
    mo = re.search(r'(\d\d):(\d\d):(\d\d)', output)
    if mo is None:
        errexit('Failed to read duration for %s' % vpath)
    h, m, s = mo.groups()
    return int(h)*3600 + int(m)*60 + int(s) + 1  # +1 for milliseconds


def prompt_plan(plan):
    for vpath, spath, outbase, slices in plan:
        _, video_name = os.path.split(vpath)

        _, srt_name = os.path.split(spath) if spath is not None else \
                      (None, '<no-subtitle>')
        print('{} into {} slices'.format(outbase, len(slices)))
        print('- {}'.format(video_name))
        print('- {}'.format(srt_name))

    prompt = raw_input('Are you sure? (yes/.) ')
    if prompt.lower() != 'yes':
        errexit('Abort')


def chop(vpath, spath, dstroot, start, end):
    chop_video(vpath, dstroot + '.mp4', start, end)
    if spath is not None:
        chop_srt(spath, dstroot + '.srt', start, end)


def chop_video(vpath, outpath, start, end):
    command = 'ffmpeg -y '\
              '-i "{vpath}" '\
              '-vcodec mpeg4 -qscale:v 16 '\
              '-acodec libmp3lame '\
              '-ss "{start}" -to "{end}" "{outpath}"'.format(**locals())
    return subprocess.call(command, shell=True)


def chop_srt(spath, outpath, start, end):
    subs = pysrt.open(spath)
    parts = subs.slice(ends_after={'seconds': start},
                       starts_before={'seconds': end})
    parts.shift(seconds=-start)
    parts.clean_indexes()
    parts.save(path=outpath)


def errexit(message):
    print(message, file=sys.stderr)
    exit(1)


if __name__ == '__main__':
    params = sys.argv[1:]
    if len(params) != 3:
        errexit('Usage: videochop <srcpattern> <dstdir> <seconds>')

    srcpattern, dstdir, seconds = params[:3]
    seconds = int(seconds)
    main(srcpattern, dstdir, seconds)
