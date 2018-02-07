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


def add_gmn_package(d1_path=None, gmn_venv=None, gmn_path=None):
    puts('Installing GMN...')
    sudo('mkdir -p ' + d1_path + '/' + gmn_venv, quiet=quiet)
    sudo('mkdir -p ' + d1_path + '/gmn_object_store', quiet=quiet)
    sudo('chown gmn:www-data ' + d1_path + '/' + gmn_venv, quiet=quiet)
    with settings(sudo_user='gmn'):
        sudo('virtualenv ' + d1_path + '/' + gmn_venv, quiet=quiet)
        sudo(d1_path + '/' + gmn_venv + '/bin/pip install --upgrade --no-cache-dir dataone.gmn')
        sudo('sed -i "$ a PATH=' + d1_path + '/' + gmn_venv + '/bin/:\$\"PATH\"" /home/gmn/.bashrc', quiet=quiet)
    puts('Performing basic configuration...')
    with cd(gmn_path):
        sudo('cp settings_template.py settings.py', quiet=quiet)


def add_apache2(d1_path=None, gmn_venv=None, gmn_path=None):
    puts('Adding apache2...')
    sudo('apt install --yes apache2 libapache2-mod-wsgi', quiet=quiet)
    sudo('a2enmod --quiet wsgi ssl rewrite', quiet=quiet)
    sudo('cp ' + gmn_path + 'deployment/gmn2-ssl.conf /etc/apache2/sites-available/', quiet=quiet)
    sudo('sed -i "s_/var/local/dataone_' + d1_path + '_g" /etc/apache2/sites-available/gmn2-ssl.conf', quiet=quiet)
    sudo('sed -i "s/gmn_venv/' + gmn_venv + '/g" /etc/apache2/sites-available/gmn2-ssl.conf', quiet=quiet)
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


def add_local_ca(d1_path=None, gmn_path=None):
    puts('Making local CA...')
    sudo('mkdir -p ' + d1_path + '/certs/local_ca/certs', quiet=quiet)
    sudo('mkdir -p ' + d1_path + '/certs/local_ca/newcerts', quiet=quiet)
    sudo('mkdir -p ' + d1_path + '/certs/local_ca/private', quiet=quiet)
    with cd(d1_path + '/certs/local_ca'):
        sudo('cp ' + gmn_path + 'deployment/openssl.cnf .', quiet=quiet)
        sudo('touch index.txt', quiet=quiet)
        sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -keyout private/ca_key.pem -out ca_csr.pem', quiet=False)
        sudo('openssl ca -config ./openssl.cnf -create_serial -keyfile private/ca_key.pem -selfsign -extensions v3_ca_has_san -out ca_cert.pem -infiles ca_csr.pem', quiet=False)
        sudo('rm ca_csr.pem')


def add_client_cert(d1_path=None):
    puts('Making self-signed client certificate...')
    with cd(d1_path + '/certs/local_ca'):
        sudo('openssl req -config ./openssl.cnf -new -newkey rsa:2048 -nodes -keyout private/client_key.pem -out client_csr.pem', quiet=False)
        sudo('openssl rsa -in private/client_key.pem -out private/client_key_nopassword.pem', quiet=False)
        sudo('openssl rsa -in private/client_key_nopassword.pem -pubout -out client_public_key.pem', quiet=False)
        sudo('openssl ca -config ./openssl.cnf -in client_csr.pem -out client_cert.pem', quiet=False)
        get('private/client_key_nopassword.pem', 'client_key_nopassword.pem', use_sudo=True)
        get('client_cert.pem', 'client_cert.pem', use_sudo=True)
        sudo('rm client_csr.pem', quiet=quiet)


def add_trust_local_ca(d1_path=None):
    puts('Installing local CA to GMN...')
    with cd(d1_path + '/certs/local_ca'):
        sudo('mkdir -p ../ca', quiet=quiet)
        sudo('cp ca_cert.pem ../ca/local_ca.pem', quiet=quiet)
        sudo('c_rehash ../ca', quiet=quiet)


def install_non_trusted_client(d1_path=None):
    puts('Installing self-signed client certificate...')
    with cd(d1_path + '/certs/local_ca'):
        sudo('mkdir -p ../client', quiet=quiet)
        sudo('cp client_cert.pem private/client_key_nopassword.pem ../client', quiet=quiet)


def install_non_trusted_server(d1_path=None):
    puts('Installing self-signed server certificate...')
    sudo('apt install --yes ssl-cert', quiet=quiet)
    sudo('mkdir -p ' + d1_path + '/certs/server', quiet=quiet)
    sudo('cp /etc/ssl/certs/ssl-cert-snakeoil.pem ' + d1_path + '/certs/server/server_cert.pem', quiet=quiet)
    sudo('cp /etc/ssl/private/ssl-cert-snakeoil.key ' + d1_path + '/certs/server/server_key_nopassword.pem', quiet=quiet)


def make_ssl_cert():
    # Only run if the server name or IP address changes.
    # Then, copy the new versions to the GMN standard locations as described above.
    sudo('make-ssl-cert generate-default-snakeoil --force-overwrite',
         quiet=quiet)


def install_trusted_client(d1_path=None, cert=None, key=None):
    puts('Installing trusted client certificate...')
    put(cert, '/tmp/client_cert.pem')
    put(key, '/tmp/client_key_nopassword.pem')
    sudo('mkdir -p ' + d1_path + '/certs/client')
    with cd(d1_path + '/certs/client'):
        sudo('mv /tmp/client_cert.pem .')
        sudo('mv /tmp/client_key_nopassword.pem .')


def install_dataone_chainfile(d1_path=None, test_env=True):
    puts('Installing DataONE chainfile...')
    sudo('mkdir -p ' + d1_path + '/certs/ca')
    with cd(d1_path + '/certs/ca'):
        chain_url = 'https://repository.dataone.org/software/tools/trunk/ca/'
        if test_env:
            chain = chain_url + 'DataONETestCAChain.crt'
        else:
            chain = chain_url + 'DataONECAChain.crt'
        sudo('wget ' + chain)
        sudo('c_rehash .')


def do_final_config(d1_path=None, gmn_python=None, gmn_path=None):
    puts('Performing final configuration...')
    sudo('chown -R gmn:www-data ' + d1_path, quiet=quiet)
    sudo('chmod -R g+w ' + d1_path, quiet=quiet)
    puts('Creating gmn2 database...')
    with settings(sudo_user='gmn'):
        django_db = '/manage.py migrate --run-syncdb'
        sudo(gmn_python + ' ' + gmn_path + django_db, quiet=quiet)
    puts('Changing TZ to UTC...')
    sudo('echo "Etc/UTC" > /etc/timezone', quiet=quiet)
    sudo('rm /etc/localtime', quiet=quiet)  # Necessary due to Debian/Ubuntu bug
    sudo('dpkg-reconfigure -f noninteractive tzdata', quiet=quiet)
    puts('Restarting apache2...')
    sudo('service apache2 restart', quiet=quiet)


def do_ufw():
    puts('Configuring UFW firewall...')
    puts('Opening HTTPS through UFW...')
    sudo('ufw allow https', quiet=quiet)
    puts('Opening HTTP through UFW...')
    sudo('ufw allow http', quiet=quiet)
    puts('Opening SSH through UFW...')
    sudo('ufw allow ssh', quiet=quiet)
    puts('Starting UFW...')
    sudo('ufw enable', quiet=False)


def deploy_gmn(
        do_os_patch=False,
        enable_ufw=True,
        test_env=True,
        gmn_venv='gmn_venv',
        client_cert=None,
        client_key=None
        ):

    d1_path = '/var/local/dataone'
    gmn_path = d1_path + '/' + gmn_venv + '/lib/python2.7/site-packages/d1_gmn/'
    gmn_python = d1_path + '/' + gmn_venv + '/bin/python2.7'

    if do_os_patch:
        do_patch()

    add_gmn_user()
    add_gmn_sudo()
    add_dist_tool_chain()
    add_pip()
    add_gmn_package(d1_path=d1_path, gmn_venv=gmn_venv, gmn_path=gmn_path)
    add_apache2(d1_path=d1_path, gmn_venv=gmn_venv, gmn_path=gmn_path)
    add_postgres()
    add_cron()

    if client_cert is None or client_key is None:
        add_local_ca(d1_path=d1_path, gmn_path=gmn_path)
        add_client_cert(d1_path=d1_path)
        add_trust_local_ca(d1_path=d1_path)
        install_non_trusted_client(d1_path=d1_path)
        install_non_trusted_server(d1_path=d1_path)
    else:
        install_trusted_client(d1_path=d1_path, cert=client_cert, key=client_key)
        install_dataone_chainfile(d1_path=d1_path, test_env=test_env)
        install_non_trusted_server(d1_path=d1_path)  # Needed for Apache start

    do_final_config(d1_path=d1_path, gmn_python=gmn_python, gmn_path=gmn_path)

    if enable_ufw:
        do_ufw()


def main():
    return 0


if __name__ == "__main__":
    main()
