# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from math import ceil, floor
import os
from pprint import pprint
import re
import subprocess
import sys

import pysrt


def main(srcdir, pattern, dstdir, seconds):
    plan = build_plan(srcdir, pattern, dstdir, seconds)
    prompt_plan(plan)

    for outpath_base, video_path, srt_path, slices in plan:
        for i, (s, e) in enumerate(slices, 1):
            dstpath_root = '{}.{:02d}'.format(outpath_base, i)
            chop_video(video_path, dstpath_root + '.mp4', s, e)
            chop_srt(srt_path, dstpath_root + '.srt', s, e)


def build_plan(srcdir, pattern, dstdir, seconds):
    plan = []
    video_paths = detect_targets(srcdir, pattern, ['.avi', '.mp4', '.mkv'])
    srt_paths = detect_targets(srcdir, pattern, ['.srt'])
    for key in video_paths:
        if key not in srt_paths:
            errexit('Failed to find srt for "%s"' % video_paths[key])
        outpath_base = os.path.join(dstdir, key)
        video_path = video_paths[key]
        srt_path = srt_paths[key]
        slices = compute_slices(srt_path, seconds)
        plan.append((outpath_base, video_paths[key], srt_paths[key], slices))
    return sorted(plan)


def detect_targets(srcdir, pattern, exts):
    paths = [os.path.join(srcdir, name) for name in os.listdir(srcdir)]
    paths = [p for p in paths if os.path.isfile(p)]
    pattern = pattern.replace('N', '\d')
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
    for dstroot, video_path, srt_path, slices in plan:
        _, video_name = os.path.split(video_path)
        _, srt_name = os.path.split(srt_path)
        print('{} into {} slices'.format(dstroot, len(slices)))
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
    return subprocess.call(command, shell=True)


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
    if len(params) != 4:
        errexit('Usage: videochop <srdir> <pattern> <dstdir> <seconds>')

    srcdir, pattern, dstdir, seconds = params[:4]
    seconds = int(seconds)
    main(srcdir, pattern, dstdir, seconds)
