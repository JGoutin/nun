#! /usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# coding=utf-8
"""Command line interface"""


def _run_command():
    """
    Command line entry point
    """
    from argparse import ArgumentParser
    from argcomplete import autocomplete
    from nun._cfg import APP_NAME

    # Parser: "nun"
    parser = ArgumentParser(
        prog=APP_NAME, description='A package manager to install from Git '
                                   'repositories and platforms.')
    sub_parsers = parser.add_subparsers(
        dest='parser_action', title='Commands',
        help='Commands', description=''
        )
    parser.add_argument('--debug',  action='store_true',
                        help='If True, show full error traceback and stop on '
                             'first error.')

    # Parser: "nun download"
    # TODO: Autocomplete resource_id from platforms
    description = 'Download.'
    action = sub_parsers.add_parser(
        'download', help=description, description=description)
    action.add_argument('resources', nargs='*', help='Resources.')
    action.add_argument('--output', '-o', help='Output directory.', default='.')
    action.add_argument('--force', '-f', help='Always replace destination.',
                        action='store_true')

    # Parser: "nun extract"
    description = 'Extract archives.'
    action = sub_parsers.add_parser(
        'extract', help=description, description=description)
    action.add_argument('resources', nargs='*', help='Resources.')
    action.add_argument('--output', '-o', help='Output directory.', default='.')
    action.add_argument('--trusted',
                        help='Allow extraction of files outside of the '
                             'output directory.',
                        action='store_true')
    action.add_argument('--strip_components', type=int, default=0,
                        help='strip NUMBER leading components from file '
                             'path on extraction')
    action.add_argument('--force', '-f', help='Always replace destination.',
                        action='store_true')

    # Parser: "nun install"
    description = 'Install packages.'
    action = sub_parsers.add_parser(
        'install', help=description, description=description)
    action.add_argument('resources', nargs='*', help='Resources.')

    # Parser: "nun update"
    description = 'Update packages.'
    action = sub_parsers.add_parser(
        'update', help=description, description=description)
    action.add_argument('resources', nargs='*', help='Resources.', default="*")

    # Parser: "nun remove"
    # TODO: Autocomplete resource from tracked
    description = 'Remove and un-track packages.'
    action = sub_parsers.add_parser(
        'remove', help=description, description=description)
    action.add_argument('resources', nargs='*', help='Resources.', default="*")

    # Parser: "nun info"
    description = 'Information about package.'
    action = sub_parsers.add_parser(
        'info', help=description, description=description)
    action.add_argument('resources', nargs='*', help='Resources.')

    # Parser: "nun list"
    description = 'List packages.'
    action = sub_parsers.add_parser(
        'list', help=description, description=description)

    # Enable autocompletion
    autocomplete(parser)

    # Get arguments and call function
    args = vars(parser.parse_args())
    parser_action = args.pop('parser_action')
    if not parser_action:
        parser.error('An action is required')

    try:
        from os.path import dirname, realpath
        import sys
        sys.path.insert(0, dirname(dirname(realpath(__file__))))

        import nun
        nun.set_ui('cli')
        getattr(nun, parser_action)(**args)

    except KeyboardInterrupt:  # pragma: no cover
        parser.exit(status=1, message="Interrupted by user\n")

    except Exception as exception:
        if args.get('debug'):
            raise
        parser.exit(status=1, message=f'\033[31m{exception}\033[30m\n')


if __name__ == '__main__':
    _run_command()
