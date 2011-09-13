import logging
import MySQLdb
import hashlib
import time

from kn import settings
from kn.base._random import pseudo_randstr

def forum_setpass(daan, user, password):
        creds = settings.FORUM_MYSQL_CREDS
        dc = MySQLdb.connect(creds[0], user=creds[1], passwd=creds[2],
                                db=creds[3])
        c = dc.cursor()
        salt = pseudo_randstr()
        h = hashlib.sha1(password).hexdigest()
        h = hashlib.sha1(salt + h).hexdigest()
        c.execute("UPDATE users SET password=%s, salt=%s WHERE username=%s;",
                        (h, salt, user))
        c.execute("COMMIT;")
        c.close()
        dc.close()

def apply_forum_changes(daan, changes):
        creds = settings.FORUM_MYSQL_CREDS
        dc = MySQLdb.connect(creds[0], user=creds[1], passwd=creds[2],
                                db=creds[3])
        for user, realname, email in changes['add']:
                c = dc.cursor()
                q = """INSERT INTO users (`username`,
                                          `password`,
                                          `email`,
                                          `realname`,
                                          `registered`)
                        VALUES (%s, %s, %s, %s, %s);"""
                c.execute(q, (user, '37', email, realname, int(time.time())))
                c.execute("COMMIT;")
                c.close()
        for user in changes['remove']:
                c = dc.cursor()
                c.execute("DELETE FROM `users` WHERE `username`=%s", user)
                c.execute("COMMIT;")
                c.close()
        dc.close()
