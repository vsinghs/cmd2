# coding=utf-8
"""
Unit/functional testing for argparse completer in cmd2

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""
import os
import pytest
import sys
from typing import List

from cmd2.argparse_completer import ACArgumentParser, AutoCompleter
try:
    from cmd2.argcomplete_bridge import CompletionFinder
except:
    # Don't test if argcomplete isn't present (likely on Windows)
    pytest.skip()

actors = ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher', 'Alec Guinness', 'Peter Mayhew',
          'Anthony Daniels', 'Adam Driver', 'Daisy Ridley', 'John Boyega', 'Oscar Isaac',
          'Lupita Nyong\'o', 'Andy Serkis', 'Liam Neeson', 'Ewan McGregor', 'Natalie Portman',
          'Jake Lloyd', 'Hayden Christensen', 'Christopher Lee']


def query_actors() -> List[str]:
    """Simulating a function that queries and returns a completion values"""
    return actors


@pytest.fixture
def parser1():
    """creates a argparse object to test completion against"""
    ratings_types = ['G', 'PG', 'PG-13', 'R', 'NC-17']

    def _do_media_movies(self, args) -> None:
        if not args.command:
            self.do_help('media movies')
        else:
            print('media movies ' + str(args.__dict__))

    def _do_media_shows(self, args) -> None:
        if not args.command:
            self.do_help('media shows')

        if not args.command:
            self.do_help('media shows')
        else:
            print('media shows ' + str(args.__dict__))

    media_parser = ACArgumentParser(prog='media')

    media_types_subparsers = media_parser.add_subparsers(title='Media Types', dest='type')

    movies_parser = media_types_subparsers.add_parser('movies')
    movies_parser.set_defaults(func=_do_media_movies)

    movies_commands_subparsers = movies_parser.add_subparsers(title='Commands', dest='command')

    movies_list_parser = movies_commands_subparsers.add_parser('list')

    movies_list_parser.add_argument('-t', '--title', help='Title Filter')
    movies_list_parser.add_argument('-r', '--rating', help='Rating Filter', nargs='+',
                                    choices=ratings_types)
    movies_list_parser.add_argument('-d', '--director', help='Director Filter')
    movies_list_parser.add_argument('-a', '--actor', help='Actor Filter', action='append')

    movies_add_parser = movies_commands_subparsers.add_parser('add')
    movies_add_parser.add_argument('title', help='Movie Title')
    movies_add_parser.add_argument('rating', help='Movie Rating', choices=ratings_types)
    movies_add_parser.add_argument('-d', '--director', help='Director', nargs=(1, 2), required=True)
    movies_add_parser.add_argument('actor', help='Actors', nargs='*')

    movies_commands_subparsers.add_parser('delete')

    shows_parser = media_types_subparsers.add_parser('shows')
    shows_parser.set_defaults(func=_do_media_shows)

    shows_commands_subparsers = shows_parser.add_subparsers(title='Commands', dest='command')

    shows_commands_subparsers.add_parser('list')

    return media_parser


# noinspection PyShadowingNames
def test_bash_nocomplete(parser1):
    completer = CompletionFinder()
    result = completer(parser1, AutoCompleter(parser1))
    assert result is None


# save the real os.fdopen
os_fdopen = os.fdopen


def my_fdopen(fd, mode):
    """mock fdopen that redirects 8 and 9 from argcomplete to stdin/stdout for testing"""
    if fd > 7:
        return os_fdopen(fd - 7, mode)
    return os_fdopen(fd, mode)


# noinspection PyShadowingNames
def test_invalid_ifs(parser1, mock):
    completer = CompletionFinder()

    mock.patch.dict(os.environ, {'_ARGCOMPLETE': '1',
                                 '_ARGCOMPLETE_IFS': '\013\013'})

    mock.patch.object(os, 'fdopen', my_fdopen)

    with pytest.raises(SystemExit):
        completer(parser1, AutoCompleter(parser1), exit_method=sys.exit)


# noinspection PyShadowingNames
@pytest.mark.parametrize('comp_line, exp_out, exp_err', [
    ('media ', 'movies\013shows', ''),
    ('media mo', 'movies', ''),
    ('media movies add ', '\013\013 ', '''
Hint:
  TITLE                   Movie Title'''),
    ('media movies list -a "J', '"John Boyega"\013"Jake Lloyd"', ''),
    ('media movies list ', '', '')
])
def test_commands(parser1, capfd, mock, comp_line, exp_out, exp_err):
    completer = CompletionFinder()

    mock.patch.dict(os.environ, {'_ARGCOMPLETE': '1',
                                 '_ARGCOMPLETE_IFS': '\013',
                                 'COMP_TYPE': '63',
                                 'COMP_LINE': comp_line,
                                 'COMP_POINT': str(len(comp_line))})

    mock.patch.object(os, 'fdopen', my_fdopen)

    with pytest.raises(SystemExit):
        choices = {'actor': query_actors,  # function
                   }
        autocompleter = AutoCompleter(parser1, arg_choices=choices)
        completer(parser1, autocompleter, exit_method=sys.exit)

    out, err = capfd.readouterr()
    assert out == exp_out
    assert err == exp_err


def fdopen_fail_8(fd, mode):
    """mock fdopen that forces failure if fd == 8"""
    if fd == 8:
        raise IOError()
    return my_fdopen(fd, mode)


# noinspection PyShadowingNames
def test_fail_alt_stdout(parser1, mock):
    completer = CompletionFinder()

    comp_line = 'media movies list '
    mock.patch.dict(os.environ, {'_ARGCOMPLETE': '1',
                                 '_ARGCOMPLETE_IFS': '\013',
                                 'COMP_TYPE': '63',
                                 'COMP_LINE': comp_line,
                                 'COMP_POINT': str(len(comp_line))})
    mock.patch.object(os, 'fdopen', fdopen_fail_8)

    try:
        choices = {'actor': query_actors,  # function
                   }
        autocompleter = AutoCompleter(parser1, arg_choices=choices)
        completer(parser1, autocompleter, exit_method=sys.exit)
    except SystemExit as err:
        assert err.code == 1


def fdopen_fail_9(fd, mode):
    """mock fdopen that forces failure if fd == 9"""
    if fd == 9:
        raise IOError()
    return my_fdopen(fd, mode)


# noinspection PyShadowingNames
def test_fail_alt_stderr(parser1, capfd, mock):
    completer = CompletionFinder()

    comp_line = 'media movies add '
    exp_out = '\013\013 '
    exp_err = '''
Hint:
  TITLE                   Movie Title'''

    mock.patch.dict(os.environ, {'_ARGCOMPLETE': '1',
                                 '_ARGCOMPLETE_IFS': '\013',
                                 'COMP_TYPE': '63',
                                 'COMP_LINE': comp_line,
                                 'COMP_POINT': str(len(comp_line))})
    mock.patch.object(os, 'fdopen', fdopen_fail_9)

    with pytest.raises(SystemExit):
        choices = {'actor': query_actors,  # function
                   }
        autocompleter = AutoCompleter(parser1, arg_choices=choices)
        completer(parser1, autocompleter, exit_method=sys.exit)

    out, err = capfd.readouterr()
    assert out == exp_out
    assert err == exp_err
