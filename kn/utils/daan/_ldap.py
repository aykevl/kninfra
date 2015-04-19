import ldap
import ldap.modlist
import smbpasswd

from kn import settings

def ldap_setpass(daan, user, password):
    if not password:
        return
    l = ldap.open(settings.LDAP_HOST)
    l.bind_s(settings.LDAP_USER, settings.LDAP_PASS)
    udn = 'uid=%s,%s' % (user, settings.LDAP_BASE)
    try:
        # Set LDAP password
        l.passwd_s(udn, None, password)
        # Set SAMBA password entries (to support MSCHAPv2 authentication
        # for WiFi via FreeRADIUS via LDAP).
        res = l.search_s(settings.LDAP_BASE, ldap.SCOPE_ONELEVEL,
                                'uid=%s' % user)
        if not res:
            return
        _o = res[0][1]
        if 'sambaNTPassword' in _o:
            l.modify_s(udn, ldap.modlist.modifyModlist(
                {'sambaNTPassword': _o['sambaNTPassword'][0]},
                {'sambaNTPassword': [smbpasswd.nthash(password)]}))
        else:
            # NOTE See /doc/ldap/scheme.ldif
            #      We added the scheme *after* the creation of the database.
            #      Thus, the user may still miss the objectClass knAccount.
            l.modify_s(udn, ldap.modlist.modifyModlist(
                {'objectClass': _o['objectClass']},
                {'objectClass': _o['objectClass'] + ['knAccount'],
                 'sambaNTPassword': [smbpasswd.nthash(password)]}))
    finally:
        l.unbind_s()

# TODO exception safety

def apply_ldap_changes(daan, changes):
    if not changes:
        return
    l = ldap.open(settings.LDAP_HOST)
    l.bind_s(settings.LDAP_USER, settings.LDAP_PASS)
    try:
        for uid in changes['remove']:
            dn = 'uid=%s,%s' % (uid, settings.LDAP_BASE)
            l.delete_s(dn)
        for uid, mail, sn, cn in changes['upsert']:
            dn = 'uid=%s,%s' % (uid, settings.LDAP_BASE)
            res = l.search_s(settings.LDAP_BASE, ldap.SCOPE_ONELEVEL,
                                    'uid=%s' % uid)
            if not res:
                entry = {'objectClass': ['inetOrgPerson'],
                         'uid': [uid],
                         'sn': [sn],
                         'cn': [cn],
                         'mail': [mail]}
                l.add_s(dn, ldap.modlist.addModlist(entry))
                continue
            _o = res[0][1]
            old = {'uid': _o['uid'][0],
                   'sn': _o['sn'][0],
                   'cn': _o['cn'][0],
                   'mail': _o['mail'][0]}
            new = {'uid': [uid],
                   'sn': [sn],
                   'cn': [cn],
                   'mail': [mail]}
            l.modify_s(dn, ldap.modlist.modifyModlist(old, new))
    finally:
        l.unbind_s()

# vim: et:sta:bs=2:sw=4:
