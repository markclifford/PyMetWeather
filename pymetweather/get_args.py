import argparse
from ConfigParser import RawConfigParser
import os
from os.path import expanduser
from pkg_resources import resource_filename


def get_command_line_args():
    parser = argparse.ArgumentParser(
        description=('Retreive and display weather forecast from the met '
                     'office. Default behaviour is to check for updates if '
                     'the saved forecast is more than ninety minutes old'))
    parser.add_argument('-d', '--dont-update', dest='dont_update',
                        action='store_true', help='do not check for updates')
    parser.add_argument('-q', '--quiet-update', dest='quiet_update',
                        action='store_true', help='check for updates and quit')
    return vars(parser.parse_args())


def get_config_args():
    cp = RawConfigParser({
        'location': 'Heathrow',
        'api_key': '',
        'datadir': expanduser('~/.metweather')})

    if os.path.isfile(expanduser('~/.metweatherrc')):
        cp.read([expanduser('~/.metweatherrc')])
        args = dict(cp.items('default'))
    else:
        args = cp.defaults()

    if not args['api_key']:
        #raise Exception("No API key given")
        raw_input(
            'No API key found, Press any key to proceed with example data')
        args['datadir'] = resource_filename('pymetweather', 'example-data')
        args['dont_update'] = True

    args['datadir'] = expanduser(args['datadir'])

    if not os.path.isdir(args['datadir']):
        os.mkdir(args['datadir'])

    return args
