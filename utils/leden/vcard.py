# vim: et:sta:bs=2:sw=4:
import _import  # noqa: F401
import sys
import tarfile

import vobject
from common import args_to_users
from six.moves import cStringIO


def vcard(u):
    c = vobject.vCard()
    c.add('n')
    ln = ' '.join(reversed(map(lambda x: x.strip(),
                               u.last_name.split(',', 1))))
    c.n.value = vobject.vcard.Name(ln,
                                   given=u.first_name)
    c.add('fn')
    c.fn.value = u.full_name()
    le = c.add('email', 'kn')
    le.value = u.primary_email
    le.type_paramlist = ['INTERNET']
    c.add('X-ABLabel', 'kn').value = 'kn'
    if u.telephone is not None:
        c.add('tel', 'kn')
        c.tel.value = u.telephone
        c.tel.type_param = 'CELL'
    if (u.addr_street is not None and
            u.addr_city is not None and
            u.addr_number is not None and
            u.addr_zipCode is not None):
        le = c.add('adr', 'kn')
        le.value = vobject.vcard.Address(' '.join((u.addr_street,
                                                   u.addr_number)),
                                         u.addr_city,
                                         '',
                                         u.addr_zipCode,
                                         'Nederland')
        c.add('x-abadr', 'kn').value = 'nl'
    return c.serialize()


if __name__ == '__main__':
    tb = cStringIO()
    tf = tarfile.open(mode='w', fileobj=tb)
    for u in args_to_users(sys.argv[1:]):
        ti = tarfile.TarInfo(u.username + ".vcf")
        td = vcard(u)
        ti.size = len(td)
        tf.addfile(ti, cStringIO(td))
    tf.close()
    print(tb.getvalue())
