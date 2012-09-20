from setuptools import setup, find_packages
import sys, os

version = '0.3.4'

setup(name='powerupdater',
      version=version,
      description="Update route53 dns zone with new info from AWS",
      #long_description="""\
#""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Dominic LoBue',
      author_email='dominic.lobue@gmail.com',
      url='',
      license='GPLv3',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      scripts = ['bin/powerupdater'],
      install_requires=[
          'boto>=2.0rc1',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
