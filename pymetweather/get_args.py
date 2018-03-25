import argparse
from configparser import RawConfigParser
from os import mkdir
import os.path


def get_command_line_args():
    parser = argparse.ArgumentParser(description=(
        'Retreive and display weather forecast from the met '
        'office. Default behaviour is to check for updates if '
        'the saved forecast is more than ninety minutes old'
    ))

    parser.add_argument(
        '-l',
        '--location',
        help='location of forecast'
    )
    parser.add_argument(
        '-d',
        '--dont-update',
        dest='dont_update',
        action='store_true',
        help='do not check for updates'
    )

    parser.add_argument(
        '-q',
        '--quiet-update',
        dest='quiet_update',
        action='store_true',
        help='check for updates and quit'
    )

    return vars(parser.parse_args())


def get_config_args():
    cp = RawConfigParser({
        'api_key': '',
        'datadir': os.path.expanduser('~/.metweather')})

    if os.path.isfile(os.path.expanduser('~/.metweatherrc')):
        cp.read([os.path.expanduser('~/.metweatherrc')])
        args = dict(cp.items('default'))
    else:
        args = cp.defaults()

    if not args['api_key']:
        raise Exception("No API key given")

    args['datadir'] = os.path.expanduser(args['datadir'])

    if not os.path.isdir(args['datadir']):
        mkdir(args['datadir'])
    return args
