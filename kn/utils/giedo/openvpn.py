import logging
import os
import string
import subprocess
from glob import glob
from shutil import copy2, copytree, rmtree
from tempfile import mkdtemp

from django.conf import settings
from django.core.mail import EmailMessage

import kn.leden.entities as Es


class CreateCertificateException(Exception):
    pass


class CreateInstallerException(Exception):
    pass


def get_commonName(user):
    return str(user.name) + settings.VPN_COMMONNAME_POSTFIX


def user_has_certificate(user):
    commonName = get_commonName(user)
    return os.path.isfile(os.path.join(settings.VPN_KEYSTORE,
                                       commonName + '.key'))


def mail_result(user, filename):
    msg = "Beste %s,\n\nOp\n  %s\nkun je je download vinden.\n\n" \
        "Karpe Noktems ledenadministratie"
    # TODO this crashes
    # url = reverse('ik-openvpn-download', kwargs={'file': filename})
    url = 'http://karpenoktem.nl/smoelen/ik/openvpn/%s' % filename
    em = EmailMessage('OpenVPN', msg % (user.first_name, url),
                      to=[user.canonical_email])
    # em.attach_file(os.path.join(settings.VPN_INSTALLER_STORAGE, filename))
    em.send()


def create_certificate(user):
    assert not user_has_certificate(user)
    commonName = get_commonName(user)

    env = dict(os.environ)
    env.update({
        'KEY_DIR': settings.VPN_KEYSTORE,
        # This filters accents
        'KEY_NAME': ''.join(x for x in user.humanName
                            if x in string.printable),
        'KEY_CN': commonName})

    if not os.path.isfile(settings.VPN_OPENSSL_CONFIG):
        logging.warning('vpn: no config file available, skipping')
        return False
    ph = subprocess.Popen(['openssl', 'req', '-batch', '-days', '1000',
                           '-nodes', '-new', '-newkey', 'rsa:1024',
                           '-keyout', commonName + '.key',
                           '-out', commonName + '.csr', '-config',
                           settings.VPN_OPENSSL_CONFIG],
                          cwd=settings.VPN_KEYSTORE, env=env,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    ph.communicate()
    if ph.returncode != 0:
        raise CreateCertificateException("CSR creation failed")
    ph = subprocess.Popen(['openssl',
                           'ca',
                           '-batch',
                           '-days',
                           '1000',
                           '-out',
                           commonName + '.crt',
                           '-in',
                           commonName + '.csr',
                           '-md',
                           'sha1',
                           '-config',
                           'kn-openssl.cnf'],
                          cwd=settings.VPN_KEYSTORE,
                          env=env,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    ph.communicate()
    if ph.returncode != 0:
        raise CreateCertificateException("Signing failed")
    return True

# TODO reuse code between create_openvpn_{installer,zip}


def create_openvpn_installer(giedo, user):
    # Remove old .exe's
    for filename in glob('openvpn-install-*-%s.exe' % str(user.name)):
        os.unlink(filename)
    # Set up a clean export of the openvpn-installer-repos
    _dir = mkdtemp(prefix='openvpn-installer-')
    os.rmdir(_dir)
    copytree(os.path.join(settings.VPN_INSTALLER_REPOS, 'installer/'), _dir)
    # Create the certificate
    if not user_has_certificate(user):
        if not create_certificate(user):
            return False
    commonName = get_commonName(user)
    # Personalize the installer and config-file
    # Check the git-revision
    ph = subprocess.Popen(['git', 'reflog'],
                          cwd=settings.VPN_INSTALLER_REPOS,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    version = ph.communicate()[0].splitlines()[0].split(' ')[0]
    if ph.returncode != 0:
        raise CreateInstallerException("Version check failed")
    # Write the .nsi
    with open(os.path.join(_dir, 'openvpn-gui.nsi.base'), 'r') as fh:
        nsi = fh.read()
    nsi = nsi.replace('KNUSERNAME', str(user.name))
    nsi = nsi.replace('KNOPENVPNVERSION', version)
    with open(os.path.join(_dir, 'openvpn-gui.nsi'), 'w') as fh:
        fh.write(nsi)
    # Write the OpenVPN config
    with open(os.path.join(_dir, 'client.conf'), 'r') as fh:
        config = fh.read()
    config = config.replace('KNUSERNAME', str(user.name))
    with open(os.path.join(_dir, 'openvpn/config', commonName + '.ovpn'),
              'w') as fh:
        fh.write(config)
    # Copy the keypair
    copy2(os.path.join(settings.VPN_KEYSTORE, commonName + '.key'),
          os.path.join(_dir, 'openvpn/config/'))
    copy2(os.path.join(settings.VPN_KEYSTORE, commonName + '.crt'),
          os.path.join(_dir, 'openvpn/config/'))
    # Run makensis
    ph = subprocess.Popen(['makensis', 'openvpn-gui.nsi'], cwd=_dir,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ph.communicate()
    if ph.returncode != 0:
        raise CreateInstallerException("Makensis failed")
    zip_outfile = False
    fn = 'openvpn-install-%s-%s.exe' % (version, str(user.name))
    if zip_outfile:
        fn_zip = 'openvpn-install-%s-%s.zip' % (version, str(user.name))
        # Run zip
        ph = subprocess.Popen(['zip', os.path.join(
            settings.VPN_INSTALLER_STORAGE, fn_zip), fn], cwd=_dir,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ph.communicate()
        if ph.returncode != 0:
            raise CreateInstallerException("Zip failed")
        fn = fn_zip
    else:
        # Copy the installer to the storage dir
        copy2(os.path.join(_dir, fn), settings.VPN_INSTALLER_STORAGE)
    # Clean up
    rmtree(_dir)
    # Return
    mail_result(user, fn)
    return True


def _create_zip(user):
    # Create a temporary working directory
    _dir = mkdtemp(prefix='openvpn-zip-')
    os.mkdir(os.path.join(_dir, 'config'))
    # Create the certificate
    if not user_has_certificate(user):
        if not create_certificate(user):
            return False
    commonName = get_commonName(user)
    # Personalize the installer and config-file
    # Write the OpenVPN config
    with open(os.path.join(settings.VPN_INSTALLER_REPOS,
                           'installer/client.conf'), 'r') as fh:
        config = fh.read()
    config = config.replace('KNUSERNAME', str(user.name))
    with open(os.path.join(_dir, 'config', commonName + '.ovpn'), 'w') as fh:
        fh.write(config)
    # Copy the keypair
    copy2(os.path.join(settings.VPN_KEYSTORE, commonName + '.key'),
          os.path.join(_dir, 'config/'))
    copy2(os.path.join(settings.VPN_KEYSTORE, commonName + '.crt'),
          os.path.join(_dir, 'config/'))
    # Add ca.crt
    copy2(os.path.join(settings.VPN_KEYSTORE, 'ca.crt'),
          os.path.join(_dir, 'config/'))
    # Run zip
    ph = subprocess.Popen(['zip', '-r', os.path.join(
        settings.VPN_INSTALLER_STORAGE,
        'openvpn-config-%s.zip' % str(user.name)), 'config'], cwd=_dir,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ph.communicate()
    if ph.returncode != 0:
        raise CreateInstallerException("Zip failed")
    # Clean up
    rmtree(_dir)


def create_openvpn_zip(giedo, user):
    # Remove old .zip's
    _file = 'openvpn-config-%s.zip' % str(user.name)
    if os.path.exists(_file):
        os.unlink(_file)
    # Create the zipfile
    _create_zip(user)
    # Return
    mail_result(user, _file)
    return True


def generate_openvpn_zips(giedo):
    for u in Es.users():
        if not u.is_active:
            continue
        if not os.path.isfile(
            os.path.join(
                settings.VPN_INSTALLER_STORAGE,
                'openvpn-config-%s.zip' % str(u.name))):
            _create_zip(u)


if __name__ == '__main__':
    create_openvpn_installer(None, Es.by_name('jille'))

# vim: et:sta:bs=2:sw=4:
