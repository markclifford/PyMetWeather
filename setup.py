import os.path
from setuptools import setup


def read(fname):
        return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='PyMetWeather',
    version='0.1',
    description='Text based weather forecast from Met Office data',
    long_description=read('README'),
    author='tracyjacks',
    packages=['pymetweather'],
    entry_points={'console_scripts': [
        'metweather = pymetweather.pymetweather:main']},
    install_requires=['dpath', 'pendulum', 'requests_futures'],
)
