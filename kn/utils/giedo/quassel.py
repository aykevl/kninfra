import sqlite3
import os.path
import logging

import kn.leden.entities as Es
from kn.leden.date import now
from kn.base._random import pseudo_randstr

from django.conf import settings

def generate_quassel_changes(giedo):
    db_path = os.path.join(settings.QUASSEL_CONFIGDIR, 'quassel-storage.sqlite')
    if not os.path.exists(db_path):
        logging.warn('quassel: %s does not exist. Skipping.', db_path)
        return None

    # Check which users are currently on the core
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    have = set()
    for username, in c.execute("SELECT username FROM quasseluser"):
        have.add(username)

    # Check which should be on the core
    want = set([str(e.name) for e in Es.by_name('leden').get_members()])

    # Done!
    return {'add': list(want - have),
            'remove': list(have - want)}

# vim: et:sta:bs=2:sw=4:
