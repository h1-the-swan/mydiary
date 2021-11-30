# -*- coding: utf-8 -*-

DESCRIPTION = """core.py"""

import sys, os, time
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

# from pocket import Pocket

JOPLIN_BASE_URL = os.environ.get('JOPLIN_BASE_URL') or "http://localhost:41184"
