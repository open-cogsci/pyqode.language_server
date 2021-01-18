#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main server script for a pyqode.python backend. You can directly use this
script in your application if it fits your needs or use it as a starting point
for writing your own server.
"""
import argparse
import logging


if __name__ == '__main__':
    logging.basicConfig()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'port',
        help='The local tcp port to use to run the server'
    )
    parser.add_argument(
        '-c',
        '--command',
        help='The command to start the language server'
    )
    parser.add_argument(
        '-l',
        '--langid',
        help='The language identifier'
    )
    parser.add_argument(
        '--project-folders',
        nargs='*',
        default=[],
        help='A list of project folders'
    )
    args = parser.parse_args()

    from pyqode.core import backend
    from pyqode.language_server.backend import workers

    workers.start_language_server(args.command, args.project_folders)
    workers.langid = args.langid.lower()
    backend.CodeCompletionWorker.providers += [
        workers.CompletionProvider(),
        backend.DocumentWordsProvider()
    ]
    backend.serve_forever(args)
