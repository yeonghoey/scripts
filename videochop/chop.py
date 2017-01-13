# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from math import ceil, floor
import os
from pprint import pprint
import subprocess
import sys

import pysrt


VIDEO_EXTS = '.avi .mp4 .mkv .mov'.split()
SUBTITLE_EXTS = '.srt'.split()  # only support srt currently


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


def chop_video(video_path, outpath_format, index, start, end):
    outpath = (outpath_format % index) + '.mp4'
    command = 'ffmpeg -y '\
              '-i "{video_path}" '\
              '-vcodec mpeg4 -qscale:v 16 '\
              '-acodec libmp3lame '\
              '-ss "{start}" -to "{end}" "{outpath}"'.format(**locals())
    return subprocess.call(command, shell=True)


def chop_srt(srt_path, outpath_format, index, start, end):
    subs = pysrt.open(srt_path)
    parts = subs.slice(ends_after={'seconds': start},
                       starts_before={'seconds': end})
    parts.shift(seconds=-start)
    parts.clean_indexes()

    outpath = (outpath_format % index) + '.srt'
    parts.save(path=outpath)


def main(video_path, srt_path, outpath_format, seconds, start_index=1):
    seconds = int(seconds)
    slices = compute_slices(srt_path, seconds=seconds)
    for i, (s, e) in enumerate(slices, start_index):
        chop_video(video_path, outpath_format, i, s, e)
        chop_srt(srt_path, outpath_format, i, s, e)


def detect_file(path_head, exts):
    pass


def errexit(message):
    print(message, file=sys.stderr)
    exit(1)


if __name__ == '__main__':
    params = sys.argv[1:]

    if len(params) != 3:
        errexit('Usage: videochop <path_head> <outdir> <seconds>')

    path_head, outpath_format, seconds = params

    video_path = detect_file(path_head, VIDEO_EXTS)
    if video_path is None: errexit('Failed to detect video')

    subtitle_path = detect_file(path_head, SUBTITLE_EXTS)
    if subtitle_path is None: errexit('Failed to detect subtitle')

    main(*params)
