#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: fabfile

:Synopsis:

    eval `ssh-agent`
    ssh-add $HOME/.ssh/<priv_key>
    fab deploy_gmn -H <host>

    or

    Fabric script to deploy a DataONE Generic Member Node
    $ fab deploy_gmn -I -i /home/<user>/.ssh/id_rsa -H <host>

:Author:
    servilla

:Created:
    04/24/17
"""
from __future__ import print_function

from fabric.operations import *
from fabric.context_managers import *
from fabric.utils import puts

quiet = False

def server_reboot():
    puts('Doing Ubuntu system reboot...')
    with settings(warn_only=True):
        reboot(wait=60)

def do_patch():
    puts('Doing Ubuntu system patch and reboot...')
    sudo('apt update --yes', quiet=quiet)
    sudo('apt dist-upgrade --yes', quiet=quiet)
    sudo('apt autoremove --yes', quiet=quiet)
    with settings(warn_only=True):
        reboot(wait=60)

def add_gmn_user():
    puts('Adding user GMN...')
    sudo('adduser --ingroup www-data --gecos "GMN" gmn', quiet=False)

def add_gmn_sudo():
    puts('Adding sudo to user GMN...')
    local('cp 01_gmn.template 01_gmn')
    local('sed -i \'s/USER/' + env.user + '/\' 01_gmn')
    put('./01_gmn', '/etc/sudoers.d/01_gmn', use_sudo=True)
    sudo('chown root:root /etc/sudoers.d/01_gmn', quiet=quiet)
    sudo('chmod 644 /etc/sudoers.d/01_gmn', quiet=quiet)

def add_dist_tool_chain():
    puts('Adding operating system tools...')
    tool_chain = 'build-essential python-dev libssl-dev libxml2-dev ' \
                 'libxslt1-dev libffi-dev postgresql-server-dev-9.5 ' \
                 'openssl curl'
    sudo('apt install --yes ' + tool_chain, quiet=quiet)

def add_pip():
    puts('Adding pypi version of pip and virtualenv...')
    sudo('apt install --yes python-pip', quiet=quiet)
    sudo('pip install --upgrade pip virtualenv', quiet=quiet)
    sudo('apt remove --yes python-pip', quiet=quiet)

def add_gmn_package(versions):
    puts('Installing GMN...')
    sudo('mkdir -p /var/local/dataone/gmn_venv', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/gmn_object_store', quiet=quiet)
    sudo('chown gmn:www-data /var/local/dataone/gmn_venv', quiet=quiet)
    with settings(sudo_user='gmn'):
        sudo('virtualenv /var/local/dataone/gmn_venv', quiet=quiet)
        if versions is None:
            sudo('/var/local/dataone/gmn_venv/bin/pip install --upgrade --no-cache-dir dataone.gmn')
        else:
            common_version, libclient_version, cli_version, gmn_version = versions
            sudo('/var/local/dataone/gmn_venv/bin/pip install --no-cache-dir dataone.cli')
            sudo('/var/local/dataone/gmn_venv/bin/pip install --no-cache-dir dataone.libclient==' + libclient_version)
            sudo('/var/local/dataone/gmn_venv/bin/pip install --no-cache-dir dataone.gmn==' + gmn_version)
            # Moving the install of dataone.common to last is a hack to deal with the dataone.cli dependency issues for common
            sudo('/var/local/dataone/gmn_venv/bin/pip install --no-cache-dir dataone.common==' + common_version)
        sudo('sed -i "$ a PATH=/var/local/dataone/gmn_venv/bin/:\$\"PATH\"" /home/gmn/.bashrc', quiet=quiet)

def add_apache2(gmn_path):
    puts('Adding apache2...')
    sudo('apt install --yes apache2 libapache2-mod-wsgi', quiet=quiet)
    sudo('a2enmod --quiet wsgi ssl rewrite', quiet=quiet)
    sudo('cp ' + gmn_path + 'deployment/gmn2-ssl.conf /etc/apache2/sites-available/', quiet=quiet)
    sudo('cp ' + gmn_path + 'deployment/forward_http_to_https.conf /etc/apache2/conf-available', quiet=quiet)
    sudo('a2enconf --quiet forward_http_to_https', quiet=quiet)
    sudo('sudo a2ensite --quiet gmn2-ssl', quiet=quiet)

def add_postgres():
    puts('Adding postgresql...')
    sudo('apt install --yes postgresql', quiet=quiet)
    sudo('passwd -d postgres', quiet=quiet)
    with settings(sudo_user='postgres'):
        sudo('passwd', quiet=False)
        sudo('createuser gmn', quiet=quiet)
        sudo('createdb -E UTF8 gmn2', quiet=quiet)

def add_cron():
    puts('Adding GMN cron entry...')
    put('./gmn_cron', '/var/spool/cron/crontabs/gmn', use_sudo=True)
    sudo('chown gmn:crontab /var/spool/cron/crontabs/gmn', quiet=quiet)
    sudo('chmod 600 /var/spool/cron/crontabs/gmn', quiet=quiet)

def add_local_ca(gmn_path):
    puts('Making local CA...')
    sudo('mkdir -p /var/local/dataone/certs/local_ca/certs', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/certs/local_ca/newcerts', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/certs/local_ca/private', quiet=quiet)
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('cp ' + gmn_path + 'deployment/openssl.cnf .', quiet=quiet)
        sudo('touch index.txt', quiet=quiet)
        sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -keyout private/ca_key.pem -out ca_csr.pem', quiet=False)
        sudo('openssl ca -config ./openssl.cnf -create_serial -keyfile private/ca_key.pem -selfsign -extensions v3_ca_has_san -out ca_cert.pem -infiles ca_csr.pem', quiet=False)
        sudo('rm ca_csr.pem')

def add_client_cert():
    puts('Making self-signed client certificate...')
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -nodes -keyout private/client_key.pem -out client_csr.pem', quiet=False)
        sudo('openssl rsa -in private/client_key.pem -out private/client_key_nopassword.pem', quiet=False)
        sudo('openssl rsa -in private/client_key_nopassword.pem -pubout -out client_public_key.pem', quiet=False)
        sudo('openssl ca -config ./openssl.cnf -in client_csr.pem -out client_cert.pem', quiet=False)
        get('private/client_key_nopassword.pem', 'client_key_nopassword.pem', use_sudo=True)
        get('client_cert.pem', 'client_cert.pem', use_sudo=True)
        sudo('rm client_csr.pem', quiet=quiet)

def add_trust_local_ca():
    puts('Installing local CA to GMN...')
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('mkdir -p ../ca', quiet=quiet)
        sudo('cp ca_cert.pem ../ca/local_ca.pem', quiet=quiet)
        sudo('c_rehash ../ca', quiet=quiet)

def install_non_trusted_client():
    puts('Installing self-signed client certificate...')
    with cd('/var/local/dataone/certs/local_ca'):
        sudo('mkdir -p ../client', quiet=quiet)
        sudo('cp client_cert.pem private/client_key_nopassword.pem ../client', quiet=quiet)

def install_non_trusted_server():
    puts('Installing self-signed server certificate...')
    sudo('apt install --yes ssl-cert', quiet=quiet)
    sudo('mkdir -p /var/local/dataone/certs/server', quiet=quiet)
    sudo('cp /etc/ssl/certs/ssl-cert-snakeoil.pem /var/local/dataone/certs/server/server_cert.pem', quiet=quiet)
    sudo('cp /etc/ssl/private/ssl-cert-snakeoil.key /var/local/dataone/certs/server/server_key_nopassword.pem', quiet=quiet)

def make_ssl_cert():
    # Only run if the server name or IP address changes.
    # Then, copy the new versions to the GMN standard locations as described above.
    sudo('make-ssl-cert generate-default-snakeoil --force-overwrite', quiet=quiet)

def install_trusted_client(cert=None, key=None):
    puts('Installing trusted client certificate...')
    put(cert, '/tmp/client_cert.pem')
    put(key, '/tmp/client_key_nopassword.pem')
    sudo('mkdir -p /var/local/dataone/certs/client')
    with cd('/var/local/dataone/certs/client'):
        sudo('mv /tmp/client_cert.pem .')
        sudo('mv /tmp/client_key_nopassword.pem .')

def install_dataone_chainfile(env='test'):
    puts('Installing DataONE chainfile...')
    sudo('mkdir -p /var/local/dataone/certs/ca')
    with cd('/var/local/dataone/certs/ca'):
        chain = 'https://repository.dataone.org/software/tools/trunk/ca/DataONETestCAChain.crt'
        sudo('wget ' + chain)
        sudo('c_rehash .')


def do_basic_config(gmn_path):
    puts('Performing basic configuration...')
    with cd(gmn_path):
        if '/gmn/' in gmn_path:
            sudo('cp settings_site_template.py settings_site.py', quiet=quiet)
        else:
            sudo('cp settings_template.py settings.py', quiet=quiet)

def do_final_config(gmn_path):
    puts('Performing final configuration...')
    sudo('chown -R gmn:www-data /var/local/dataone/', quiet=quiet)
    sudo('chmod -R g+w /var/local/dataone', quiet=quiet)
    puts('Creating gmn2 database...')
    with settings(sudo_user='gmn'):
        sudo('/var/local/dataone/gmn_venv/bin/python ' + gmn_path + '/manage.py migrate --run-syncdb', quiet=quiet)
    puts('Changing TZ to UTC...')
    sudo('echo "Etc/UTC" > /etc/timezone', quiet=quiet)
    sudo('rm /etc/localtime', quiet=quiet) # Necessary due to Debian/Ubuntu bug
    sudo('dpkg-reconfigure -f noninteractive tzdata', quiet=quiet)
    puts('Openning HTTPS through UFW...')
    sudo('ufw allow 443', quiet=quiet)
    puts('Restarting apache2...')
    sudo('service apache2 restart', quiet=quiet)

def deploy_gmn(
    gmn_version=None,
    use_local_ca=True,
    do_os_patch=False,
    client_cert=None,
    client_key=None
    ):

    versions = None

    if gmn_version is None:
        gmn_path = '/var/local/dataone/gmn_venv/lib/python2.7/site-packages/d1_gmn/'
    else:
        major, minor, debug = gmn_version.split('.')
        if int(minor) < 3:
            gmn_path = '/var/local/dataone/gmn_venv/lib/python2.7/site-packages/gmn/'
            versions = ['2.1.0rc2', '2.1.0rc2', '1.2.5', gmn_version]
        else:
            gmn_path = '/var/local/dataone/gmn_venv/lib/python2.7/site-packages/d1_gmn/'
            versions = [gmn_version, gmn_version, gmn_version, gmn_version]

    if do_os_patch:
        do_patch()

    if client_cert is not None and client_key is not None:
        use_local_ca = False

    add_gmn_user()
    add_gmn_sudo()
    add_dist_tool_chain()
    add_pip()
    add_gmn_package(versions=versions)
    add_apache2(gmn_path=gmn_path)
    add_postgres()
    add_cron()

    if use_local_ca:
        add_local_ca(gmn_path=gmn_path)
        add_client_cert()
        add_trust_local_ca()
        install_non_trusted_client()
        install_non_trusted_server()
    else:
        install_trusted_client(cert=client_cert, key=client_key)
        install_dataone_chainfile(env='test')
        install_non_trusted_server() # Needed for Apache start

    do_basic_config(gmn_path=gmn_path)
    do_final_config(gmn_path=gmn_path)

def main():
    return 0

if __name__ == "__main__":
    main()