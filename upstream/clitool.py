#!/usr/bin/env python
# -*- coding: utf-8 -*-

# The MIT License (MIT)
#
# Copyright (c) 2014 Paul Durivage for Storj Labs
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from __future__ import print_function

import os

import sys
import argparse
import progressbar

import upstream
from upstream.shard import Shard
from upstream.exc import FileError
from upstream.file import SizeHelpers
from upstream.streamer import Streamer


def printcallback(value):
    print(value)


class ProgressCallback(object):
    def __init__(self):
        self.bar = None
        self.started = False

    def callback(self, values):
        if not self.bar:
            self.bar = progressbar.ProgressBar(
                maxval=values[1],
                widgets=[
                    'Uploading Shard: ', progressbar.Percentage(),
                    ' ', progressbar.Bar(),
                    ' ', progressbar.ETA(),
                    ' ', progressbar.FileTransferSpeed()
                ],
            )
        if not self.started:
            self.bar.start()
            self.bar.update(values[0])


def parse_shard_size(size):
    """ Parse a string, expected to be in the format of, for example:
    250m, 512k, 1024b.  A string without a trailing letter is assumed to be
    bytes. Accepts the following: m as mebibytes, k as kibibytes, b as bytes,


    :param size:
    :return:
    """
    size = str(size)
    if size.isdigit():
        return int(size)
    last = size[-1].lower()
    number = size[:-1]
    choices = ['b', 'k', 'm']
    if last not in choices:
        return
    if last == 'b':
        return int(number)
    elif last == 'k':
        return SizeHelpers.kib_to_bytes(int(number))
    elif last == 'm':
        return SizeHelpers.mib_to_bytes(int(number))


def calculate_shards(args, shard_size, filepath):
    file_size = os.path.getsize(filepath)
    num_shards = int(file_size / shard_size)
    shards = []
    start = 0
    end = shard_size
    for shard in range(num_shards):
        tup = (start, end)
        shards.append(tup)
        start = end
        end += shard_size
    if args.verbose:
        for i, s in enumerate(shards):
            print("Shard %d - Start: %d; End: %s" % (i, s[0], s[1]))
        print("File will be uploaded in %d piece(s)." % len(shards))

    return shards


def upload(args):
    """ Controls actions for uploading

    :param args: Parsed args namespace
    """
    shard_size = parse_shard_size(args.shard_size)

    try:
        filepath = Streamer.check_path(args.file)
    except FileError as e:
        sys.stderr.write('%s\n' % e.message)
        sys.exit(1)

    streamer = Streamer(args.server)
    shards = calculate_shards(args, shard_size, filepath)
    shard_info = []
    for idx, shard in enumerate(shards):
        i = idx + 1
        start = shard[0]
        callback = ProgressCallback()
        shard = streamer.upload(
            args.file,
            start_pos=start,
            shard_size=shard_size,
            callback=callback.callback
        )
        callback.bar.finish()
        sys.stdout.flush()
        if args.verbose:
            print("\nShard %d - URI: %s\n" % (i, shard.uri))
        shard_info.append(shard.uri)
    print()
    print("Download this file by using the following command: ")
    print("upstream download --uri", " ".join(shard_info), "--dest <filename>")


def download(args):
    """ Controls actions for downloading

    :param args: Argparse namespace
    """
    shards = []
    for uri in args.uri:
        if args.verbose:
            print("Creating shard.")
        shard = Shard()
        shard.from_uri(uri)
        shards.append(shard)

    streamer = Streamer(args.server)
    if args.verbose:
        print("Connecting to %s..." % streamer.server)

    result = streamer.download(
        shards, dest=args.dest, shardsize=8096, verbose=args.verbose
    )

    if result:
        print("\nDownloaded to %s." % (args.dest or shard.filehash))
    else:
        print("Something bad happened.")
        sys.exit(1)


def parse_args():
    """ Parses args

    :return: argparse namespace
    """
    parser = argparse.ArgumentParser("Upstream",
                                     description="Command line client for "
                                                 "the Storj web-core API")
    parser.add_argument('--server', default='http://node1.metadisk.org')
    parser.add_argument('-v', dest='verbose',
                        action='store_true', help='Verbose output')
    parser.add_argument('--version', action='version',
                        version="%(prog)s " + upstream.__version__,
                        help='Diplay version.')
    subparser = parser.add_subparsers(dest='action')

    upload_parser = subparser.add_parser('upload',
                                         help="Upload a file from API")
    upload_parser.add_argument('--shard-size',
                               default=SizeHelpers.mib_to_bytes(250),
                               help="Size of shards to break file into and "
                                    "to upload, max: 250m, default: 250m. "
                                    "Ex. 25m - file will be broken into 25 MB "
                                    "shards and uploaded shard by shard")
    upload_parser.add_argument('file', help="Path to file to upload")

    download_parser = subparser.add_parser('download',
                                           help="Download a file from API")
    download_parser.add_argument(
        '--uri',
        required=True,
        nargs='+',
        help="URI, or URIs, of file to download. Accepts multiple values, "
             "space separated. If multiple URIs are specified, the URIs are "
             "joined to create a single file"
    )
    download_parser.add_argument('--dest',
                                 help="Folder or file to download file")
    download_parser.add_argument('--shard-size', type=int, default=1024)

    return parser.parse_args()


def main():
    args = parse_args()
    if args.action == 'upload':
        upload(args)
    elif args.action == 'download':
        download(args)


if __name__ == '__main__':
    main()
