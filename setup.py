from setuptools import setup, find_packages
import sys, os

version = '0.3.1'

setup(name='powerupdater',
      version=version,
      description="Update route53 dns zone with new info from AWS",
      #long_description="""\
#""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Dominic LoBue',
      author_email='dominic@geodelic.com',
      url='',
      license='proprietary',
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
