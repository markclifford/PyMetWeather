import os
from setuptools import setup


def read(fname):
        return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(name='PyMetWeather',
      version='0.1',
      description='Text based weather forecast from Met Office data',
      long_description=read('README'),
      author='tracyjacks',
      packages=['pymetweather'],
      scripts=['scripts/metweather'],
      package_data={'pymetweather':
                    ['codes.json', 'metweatherrc', 'example-data/*']},
      install_requires=['dpath', 'pendulum', 'requests_futures'],
      zip_safe=False
      )
