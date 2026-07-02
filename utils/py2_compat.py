# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys

PY2 = sys.version_info[0] < 3

try:
    unicode
except NameError:
    unicode = str

try:
    basestring
except NameError:
    basestring = str