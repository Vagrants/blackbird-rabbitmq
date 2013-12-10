#!/usr/bin/env python
# -*- encodig: utf-8 -*-

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='blackbird-rabbitmq',
    version='0.1.0',
    description=(
        'Get monitorring stats of rabbitmq for blackbird '
    ),
    author='makocchi',
    author_email='makocchi@gmail.com',
    url='https://github.com/Vagrants/blackbird-rabbitmq',
    data_files=[
        ('/opt/blackbird/plugins', ['rabbitmq.py'])
    ]
)

