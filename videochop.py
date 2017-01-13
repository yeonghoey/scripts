# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from math import ceil, floor
import os
from pprint import pprint
import re
import subprocess
import sys

import pysrt


def main(srcpattern, dstdir, seconds):
    plan = build_plan(srcpattern, dstdir, seconds)
    prompt_plan(plan)

    for vpath, spath, outbase, slices in plan:
        processes = []
        for i, (s, e) in enumerate(slices, 1):
            dstroot = '{}.{:02d}'.format(outbase, i)
            chop_srt(spath, dstroot + '.srt', s, e)
            p = chop_video(vpath, dstroot + '.mp4', s, e)
            processes.append(p)
        for p in processes:
            p.wait()


def build_plan(srcpattern, dstdir, seconds):
    srcdir, pattern = os.path.split(srcpattern)
    pattern = pattern.replace('N', '\d')
    vpaths = detect_targets(srcdir, pattern, ['.avi', '.mp4', '.mkv'])
    spaths = detect_targets(srcdir, pattern, ['.srt'])
    plan = []
    for key in vpaths:
        if key not in spaths:
            errexit('Failed to find srt for "%s"' % vpaths[key])
        vpath = vpaths[key]
        spath = spaths[key]
        outbase = os.path.join(dstdir, key)
        slices = compute_slices(spath, seconds)
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


def compute_slices(path, seconds, padding=1):
    subs = pysrt.open(path)
    seconds, padding = {'seconds': seconds}, {'seconds': padding}
    head, intervals = None, []
    for s in subs:
        if head is None:
            head = s.start - padding
        term = s.end - head
        if term >= seconds:
            tail = s.end + padding
            intervals.append((head, tail))
            head = None

    # Merge remainings into the last piece
    if head is not None:
        head, _ = intervals[-1]
        tail = subs[-1].end + padding
        intervals.append((head, tail))

    # Return intervals as seconds
    return [(int(floor(a.ordinal/1000.)), int(ceil(b.ordinal/1000.)))
            for a, b in intervals]


def prompt_plan(plan):
    for vpath, spath, outbase, slices in plan:
        _, video_name = os.path.split(vpath)
        _, srt_name = os.path.split(spath)
        print('{} into {} slices'.format(outbase, len(slices)))
        print('- {}'.format(video_name))
        print('- {}'.format(srt_name))
    
    prompt = raw_input('Are you sure? (yes/.) ')
    if prompt.lower() != 'yes':
        errexit('Abort')


def chop_video(video_path, outpath, start, end):
    command = 'ffmpeg -y '\
              '-i "{video_path}" '\
              '-vcodec mpeg4 -qscale:v 16 '\
              '-acodec libmp3lame '\
              '-ss "{start}" -to "{end}" "{outpath}"'.format(**locals())
    return subprocess.Popen(command, shell=True)


def chop_srt(srt_path, outpath, start, end):
    subs = pysrt.open(srt_path)
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
        errexit('Usage: videochop <srcpattern> <pattern> <dstdir> <seconds>')

    srcpattern, dstdir, seconds = params[:3]
    seconds = int(seconds)
    main(srcpattern, dstdir, seconds)
