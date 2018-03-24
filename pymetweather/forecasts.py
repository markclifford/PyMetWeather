import json
from datetime import timedelta, datetime

import dpath
import pytz
from requests_futures.sessions import FuturesSession

base_url = "http://datapoint.metoffice.gov.uk/public/data/"
main_url = base_url + "val/wxfcs/all/json/"
text_url = base_url + "txt/wxfcs/regionalforecast/json/"

uktz = pytz.timezone('Europe/London')


def get_time(time_string):
    if time_string.endswith('Z'):
        t = datetime.strptime(time_string, '%Y-%m-%dT%H:%M:%SZ')
        return t.replace(tzinfo=pytz.utc)
    else:
        t = datetime.strptime(time_string, '%Y-%m-%dT%H:%M:%S')
        return pytz.utc.normalize(uktz.localize(t))


def get_date(date_string):
    return datetime.strptime(date_string, '%Y-%m-%dZ').replace(tzinfo=pytz.utc)


class ConnectionError(Exception):
    pass


class Forecast(object):
    def __init__(self, datafile, weather):
        self.datafile = datafile
        self.weather = weather
        self.needs_update = False
        self.data = None
        self.status = True

    def load(self):
        try:
            with open(self.datafile) as f:
                self.data = json.load(f)
                self.set_forecast()
        except IOError:
            self.needs_update = True

    def start_update(self):
        print 'getting forecast {}'.format(self.__class__.__name__)
        self.future = self.get_data()

    def complete_update(self):
        try:
            self.data = self.future.result().json()
        except ConnectionError:
            print 'Could not update {}'.format(self.__class__.__name__)
            self.status = False
        else:
            self.set_forecast()
            self.write()

    def time(self):
        return get_time(self.data['SiteRep']['DV']['dataDate'])

    def check_location(self, site_name):
        if self.data is not None:
            if self.forecast['name'] != site_name.upper():
                self.needs_update = True

    def start_check_for_updates(self):
        self.update_future = None

        if self.needs_update:
            return True
        age = datetime.utcnow().replace(tzinfo=pytz.utc) - self.time()
        if age > self.updatedelta:
            print 'check for updates required {}'.format(
                self.__class__.__name__)
            self.update_future = self.get_update_time()

    def complete_check_for_updates(self):
        if self.update_future is None:
            return

        result = self.update_future.result().json()
        new_time = get_time(dpath.get(result, self.update_time_path))
        if new_time > self.time():
            print 'update available {}'.format(self.__class__.__name__)
            print new_time, self.time()
            self.needs_update = True

    def set_forecast(self):
        self.forecast = self.data['SiteRep']['DV']['Location']

    def write(self):
        with open(self.datafile, 'w') as f:
            json.dump(self.data, f)

    def get_update_time(self):
        print 'getting update time {}'.format(self.__class__.__name__)
        try:
            return self.get_update_time_data()
        except ConnectionError:
            print 'Could not get update time {}'.format(
                self.__class__.__name__)
            return None


class DailyForecast(Forecast):
    res = 'daily'
    updatedelta = timedelta(minutes=90)
    update_time_path = 'Resource/dataDate'

    def get_data(self):
        return self.weather.session.get(
            main_url + self.weather.site_id, params={'res': self.res})

    def get_update_time_data(self):
        return self.weather.session.get(
                main_url + 'capabilities', params={'res': self.res})


class ThreeHourForecast(DailyForecast):
    res = '3hourly'


class RegionalForecast(Forecast):
    updatedelta = timedelta(hours=12)
    update_time_path = 'RegionalFcst/issuedAt'

    def get_data(self):
        return self.weather.session.get(text_url + self.weather.region)

    def get_update_time_data(self):
        return self.weather.session.get('/'.join([text_url, 'capabilities']))

    def set_forecast(self):
        self.forecast = self.data['RegionalFcst']['FcstPeriods']['Period']

    def time(self):
        return get_time(self.data['RegionalFcst']['issuedAt'])

    def check_location(self, region):
        if self.data is not None:
            if self.data['RegionalFcst']['regionId'] != region:
                self.needs_update = True


class WeatherForecast(object):
    #codes_file = resource_filename('pymetweather', 'codes.json')

    def __init__(self, api_key, site_name, datadir):
        self.datadir = datadir
        self.site_file = '{}/met-loc-site-id'.format(datadir)

        self.api_key = api_key
        self.site_name = site_name
        self.site_id = None

        self.session = FuturesSession(max_workers=5)
        self.session.params = {'key': self.api_key}

    def load_site_id_and_region(self):
        try:
            with open(self.site_file) as f:
                name = f.readline().strip(' \n\t')
                self.site_id = str(int(f.readline().strip(' \n\t')))
                self.region_name = f.readline().strip(' \n\t')
                self.region = str(int(f.readline().strip(' \n\t')))
            if name != self.site_name:
                self.get_site_id_and_region()
        except (IOError, ValueError):
            self.get_site_id_and_region()

    def get_site_id_and_region(self):
        print "Getting site information for {}...".format(self.site_name)

        sites_future = self.session.get(main_url + 'sitelist')
        regions_future = self.session.get(text_url + 'sitelist')

        sites = sites_future.result().json()['Locations']['Location']
        regions = regions_future.result().json()['Locations']['Location']

        site_id = [l for l in sites if l['name'] == self.site_name]
        assert len(site_id) >= 1, 'Site {} not found'.format(self.site_name)

        self.site_id = site_id[0]['id']
        region = site_id[0]['region']

        region = [r for r in regions if r['@name'] == region]
        assert len(region) == 1
        self.region_name = region[0]['@name']
        self.region = region[0]['@id']

        with open(self.site_file, 'w') as f:
            f.write('{}\n{}\n{}\n{}'.format(
                self.site_name, self.site_id, self.region_name, self.region))

    def load(self, no_updates=False):
        self.get_data(no_updates)
        self.hourly = self.forecasts['hourly'].data
        self.hourly_fcs = self.forecasts['hourly'].forecast
        self.daily = self.forecasts['daily'].data
        self.daily_fcs = self.forecasts['daily'].forecast
        self.regional = self.forecasts['regional'].data
        self.reg_fcs = self.forecasts['regional'].forecast

    def get_data(self, no_updates=False):

        self.load_site_id_and_region()

        datafile = self.datadir + '/met{}.json'
        self.forecasts = {
            'hourly': ThreeHourForecast(datafile.format('3hour'), self),
            'daily': DailyForecast(datafile.format('daily'), self),
            'regional': RegionalForecast(datafile.format('regional'), self)}

        for f in self.forecasts.values():
            f.load()

        self.forecasts['hourly'].check_location(self.site_name)
        self.forecasts['daily'].check_location(self.site_name)
        self.forecasts['regional'].check_location(self.region_name)

        if not no_updates:
            for fc in self.forecasts.values():
                fc.start_check_for_updates()
            for fc in self.forecasts.values():
                fc.complete_check_for_updates()

        to_update = [fc for fc in self.forecasts.values() if fc.needs_update]
        for fc in to_update:
            fc.start_update()
        for fc in to_update:
            fc.complete_update()
        if not all([f.status for f in self.forecasts.values()]):
            raise ConnectionError('Could not retreive forecasts')

    def process_forecast(self, weather_types, visibility_types):
        for period in self.hourly_fcs['Period']:
            day = get_date(period['value'])
            for rep in period['Rep']:
                rep['$'] = uktz.normalize(
                    day + timedelta(minutes=int(rep['$']))).hour
                rep['W'] = weather_types[rep['W']].split('(')[0]
                rep['V'] = visibility_types[rep['V']]

                rep['F'] = '({})'.format(rep['F']).rjust(4)
                rep['G'] = '({})'.format(rep['G']).rjust(4)

        for period in self.daily_fcs['Period']:
            period['value'] = get_date(period['value']).strftime('%A') + ':'
            for rep in period['Rep']:
                rep['W'] = weather_types[rep['W']].split('(')[0]
                rep['V'] = visibility_types[rep['V']]
                if 'FDm' in rep:
                    rep['FDm'] = '({})'.format(rep['FDm']).rjust(4)
                if 'FNm' in rep:
                    rep['FNm'] = '({})'.format(rep['FNm']).rjust(4)
                if 'Gm' in rep:
                    rep['Gm'] = '({})'.format(rep['Gm']).rjust(4)
                if 'Gn' in rep:
                    rep['Gn'] = '({})'.format(rep['Gn']).rjust(4)
