# -*- coding: utf-8 -*-

import pep8
import unittest

class TestCodeFormat(unittest.TestCase):

    def test_pep8(self):
        pep8style = pep8.StyleGuide()
        result = pep8style.check_files(['rabbitmq.py'])
        self.assertEqual(result.total_errors, 0,
                         "Found code style errors (and warnings).")

