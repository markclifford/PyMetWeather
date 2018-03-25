from abc import ABC, abstractmethod, abstractproperty
import json
import logging

import dpath
from requests_futures.sessions import FuturesSession
import pendulum

from pymetweather.codes import WEATHER_TYPES, VISIBILITY_TYPES

BASE_URL = 'http://datapoint.metoffice.gov.uk/public/data/'
MAIN_URL = BASE_URL + 'val/wxfcs/all/json/'
TEXT_URL = BASE_URL + 'txt/wxfcs/regionalforecast/json/'
TIMEZONE = 'Europe/London'

logger = logging.getLogger('pymetweather')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(ch)


class RetreivalError(Exception):
    pass


class WeatherClient(object):
    _session = None
    api_key = None

    @classmethod
    def get_session(cls):
        if cls._session is None:
            cls._session = FuturesSession(max_workers=5)
            cls._session.params = {'key': cls.api_key}
        return cls._session

    @classmethod
    def get(cls, url, params=None):
        return cls.get_session().get(url, params=params)

    @staticmethod
    def get_result(future):
        try:
            response = future.result()
            response.raise_for_status()
            return response.json()
        except Exception:
            raise RetreivalError('Error retreiving forecast')


class Forecast(ABC):
    @abstractproperty
    def updatedelta():
        pass

    @abstractproperty
    def update_time_path():
        pass

    @abstractproperty
    def forecast_path():
        pass

    @abstractproperty
    def time_path():
        pass

    def __init__(self, datafile, weather):
        self.datafile = datafile
        self.weather = weather
        self.needs_update = False
        self.data = None
        self.status = True

    @staticmethod
    def get_time(time_string):
        return pendulum.parse(time_string, tz=TIMEZONE)

    @staticmethod
    def get_date(date_string):
        return pendulum.parse(date_string.strip('Z'), tz='UTC')

    def load(self):
        try:
            with open(self.datafile) as f:
                self.data = json.load(f)
                self.set_forecast()
        except IOError:
            self.needs_update = True

    def start_update(self):
        logger.info('getting forecast {}'.format(type(self).__name__))
        self.future = self.get_data()

    def complete_update(self):
        try:
            self.data = WeatherClient.get_result(self.future)
            logger.info('Updated forecast {}'.format(type(self).__name__))
        except RetreivalError:
            logger.error('Could not update {}'.format(type(self).__name__))
            self.status = False
        else:
            self.set_forecast()
            self.process_forecast()
            self.write()

    def time(self):
        return self.get_time(dpath.get(self.data, self.time_path))

    def start_check_for_updates(self):
        self.update_future = None

        if self.needs_update:
            return True
        age = (pendulum.now() - self.time()).as_interval()
        if age > self.updatedelta:
            logger.info(
                'check for updates required {}'.format(type(self).__name__))
            self.update_future = self.get_update_time_data()

    def complete_check_for_updates(self):
        if self.update_future is None:
            return

        try:
            result = WeatherClient.get_result(self.update_future)
            logger.info('Retrived update times {}'.format(type(self).__name__))
        except RetreivalError:
            logger.error(
                'Could not get update times {}'.format(type(self).__name__))
            self.status = False
        else:
            new_time = self.get_time(dpath.get(result, self.update_time_path))
            if new_time > self.time():
                logger.info('update available {}'.format(type(self).__name__))
                self.needs_update = True

    def set_forecast(self):
        self.forecast = dpath.get(self.data, self.forecast_path)

    def write(self):
        with open(self.datafile, 'w') as f:
            json.dump(self.data, f, ensure_ascii=False)

    def process_forecast(self):
        pass

    @abstractmethod
    def check_location(self, site_name):
        pass

    @abstractmethod
    def get_update_time_data(self, site_name):
        pass

    @abstractmethod
    def get_data(self, site_name):
        pass


class DailyForecast(Forecast):
    updatedelta = pendulum.Interval(minutes=90)
    update_time_path = 'Resource/dataDate'
    time_path = 'SiteRep/DV/dataDate'
    forecast_path = 'SiteRep/DV/Location'
    res = 'daily'

    def get_data(self):
        return WeatherClient.get(
            MAIN_URL + self.weather.site_id, params={'res': self.res})

    def get_update_time_data(self):
        return WeatherClient.get(
                MAIN_URL + 'capabilities', params={'res': self.res})

    def check_location(self, site_name):
        if self.data is not None:
            if self.forecast['name'] != site_name.upper():
                self.needs_update = True

    def process_forecast(self):
        for period in self.forecast['Period']:
            period['value'] = self.get_date(period['value']).format('%A:')
            for rep in period['Rep']:
                rep['W'] = WEATHER_TYPES[rep['W']].split('(')[0]
                rep['V'] = VISIBILITY_TYPES[rep['V']]
                for field in ['FDm', 'FNm', 'Gm', 'Gn']:
                    if field in rep:
                        rep[field] = f"({rep[field]})".rjust(4)


class ThreeHourForecast(DailyForecast):
    res = '3hourly'

    def process_forecast(self):
        for period in self.forecast['Period']:
            day = self.get_date(period['value'])
            for rep in period['Rep']:
                rep['$'] = (
                        day + pendulum.Interval(minutes=int(rep['$']))
                ).in_tz(TIMEZONE).hour
                rep['W'] = WEATHER_TYPES[rep['W']].split('(')[0]
                rep['V'] = VISIBILITY_TYPES[rep['V']]

                rep['F'] = f"({rep['F']})".rjust(4)
                rep['G'] = f"({rep['G']})".rjust(4)


class RegionalForecast(Forecast):
    updatedelta = pendulum.Interval(hours=12)
    update_time_path = 'RegionalFcst/issuedAt'
    time_path = 'RegionalFcst/issuedAt'
    forecast_path = 'RegionalFcst/FcstPeriods/Period'

    def get_data(self):
        return WeatherClient.get(TEXT_URL + self.weather.region_id)

    def get_update_time_data(self):
        return WeatherClient.get('/'.join([TEXT_URL, 'capabilities']))

    def check_location(self, region):
        if self.data is not None:
            if self.data['RegionalFcst']['regionId'] != region:
                self.needs_update = True


class WeatherForecast(object):

    def __init__(self, api_key, site_name, datadir):
        self.datadir = datadir
        self.site_file = '{}/met-loc-site-id.json'.format(datadir)

        WeatherClient.api_key = api_key
        self.site_name = site_name
        self.site_id = None

    def load_site_id_and_region(self):
        try:
            with open(self.site_file) as f:
                data = json.load(f)
        except IOError:
            self.get_site_id_and_region()
        else:
            name = data['name']
            if name != self.site_name:
                self.get_site_id_and_region()
            self.site_id = data['site_id']
            self.region_name = data['region_name']
            self.region_id = data['region_id']

    def get_site_id_and_region(self):
        logger.info(
            'Getting site information for {}...'.format(self.site_name))

        sites_future = WeatherClient.get(MAIN_URL + 'sitelist')
        regions_future = WeatherClient.get(TEXT_URL + 'sitelist')

        sites = WeatherClient.get_result(sites_future)['Locations']['Location']
        regions = WeatherClient.get_result(
            regions_future)['Locations']['Location']

        for site in sites:
            if site['name'] == self.site_name:
                self.site_id = site['id']
                self.region_name = site['region']
                break
        else:
            raise Exception('Site {} not found'.format(self.site_name))

        for region in regions:
            if region['@name'] == self.region_name:
                self.region_id = region['@id']
                break
        else:
            raise Exception('Region {} not found'.format(self.region_name))

        with open(self.site_file, 'w') as f:
            json.dump({
                'name': self.site_name,
                'site_id': self.site_id,
                'region_id': self.region_id,
                'region_name': self.region_name,
                }, f, ensure_ascii=False)

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

        missing_forecasts = any([
            fc.needs_update for fc in self.forecasts.values()])

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
            if missing_forecasts:
                raise Exception('Could not retreive forecasts')
            else:
                logger.warning(
                    'Retreival error - Continuing with cached forecasts')
