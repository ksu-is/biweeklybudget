"""
The latest version of this package is available at:
<http://github.com/jantman/biweeklybudget>

################################################################################
Copyright 2016 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

    This file is part of biweeklybudget, also known as biweeklybudget.

    biweeklybudget is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    biweeklybudget is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with biweeklybudget.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/biweeklybudget> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
################################################################################

AUTHORS:
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
################################################################################
"""

import pytest
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import socket
from distutils.spawn import find_executable
import subprocess

import biweeklybudget.settings
from biweeklybudget.tests.fixtures.sampledata import SampleDataLoader

try:
    from pytest_flask.fixtures import LiveServer
except ImportError:
    pass

connstr = os.environ.get('DB_CONNSTRING', None)
if connstr is None:
    connstr = 'mysql+pymysql://budgetTester:jew8fu0ue@127.0.0.1:3306/' \
              'budgettest?charset=utf8mb4'
    os.environ['DB_CONNSTRING'] = connstr
biweeklybudget.settings.DB_CONNSTRING = connstr

import biweeklybudget.db  # noqa
import biweeklybudget.models.base  # noqa
from biweeklybudget.db_event_handlers import init_event_listeners  # noqa
from biweeklybudget.tests.unit.test_interest import InterestData  # noqa

engine = create_engine(
    connstr, convert_unicode=True, echo=False,
    connect_args={'sql_mode': 'STRICT_ALL_TABLES'},
    pool_size=10, pool_timeout=120
)

logger = logging.getLogger(__name__)

# suppress webdriver DEBUG logging
selenium_log = logging.getLogger("selenium")
selenium_log.setLevel(logging.INFO)
selenium_log.propagate = True


@pytest.fixture(scope='session')
def dump_file_path(tmpdir_factory):
    """
    Return the path to use for the SQL dump file
    """
    return tmpdir_factory.mktemp('sqldump').join('dbdump.sql')


def do_mysqldump(fpath):
    """
    Shell out and mysqldump the database to the path specified by fpath.

    :param fpath: path to save dump file to
    :type fpath: str
    :raises: RuntimeError, AssertionError
    """
    mysqldump = find_executable('mysqldump')
    assert mysqldump is not None
    assert engine.url.drivername == 'mysql+pymysql'
    args = [
        mysqldump,
        '--create-options',
        '--routines',
        '--triggers',
        '--no-create-db',
        '--host=%s' % engine.url.host,
        '--port=%s' % engine.url.port,
        '--user=%s' % engine.url.username
    ]
    if engine.url.password is not None:
        args.append('--password=%s' % engine.url.password)
    args.append(engine.url.database)
    logger.info('Running: %s', ' '.join(args))
    res = subprocess.check_output(args)
    with open(str(fpath), 'wb') as fh:
        fh.write(res)
    logger.info('Wrote %d bytes of SQL to %s', len(res), fpath)


def restore_mysqldump(fpath):
    """
    Shell out and restore a mysqldump file to the database.

    :param fpath: path to save dump file to
    :type fpath: str
    :raises: RuntimeError, AssertionError
    """
    mysql_path = find_executable('mysql')
    assert mysql_path is not None
    assert engine.url.drivername == 'mysql+pymysql'
    args = [
        mysql_path,
        '--batch',
        '--host=%s' % engine.url.host,
        '--port=%s' % engine.url.port,
        '--user=%s' % engine.url.username,
        '--database=%s' % engine.url.database
    ]
    if engine.url.password is not None:
        args.append('--password=%s' % engine.url.password)
    logger.info('Passing %s to %s', fpath, ' '.join(args))
    with open(str(fpath), 'rb') as fh:
        proc = subprocess.Popen(args, stdin=fh)
        stdout, stderr = proc.communicate()
    logger.info('MySQL dump restore complete.')
    logger.debug('mysql STDOUT: %s', stdout)
    logger.debug('mysql STDERR: %s', stderr)


@pytest.fixture(scope="session")
def refreshdb(dump_file_path):
    """
    Refresh/Load DB data before tests; also exec mysqldump to write a
    SQL dump file for faster refreshes during test runs.
    """
    if 'NO_REFRESH_DB' not in os.environ:
        # setup the connection
        conn = engine.connect()
        logger.info('Refreshing DB (session-scoped)')
        # clean the database
        biweeklybudget.models.base.Base.metadata.reflect(engine)
        biweeklybudget.models.base.Base.metadata.drop_all(engine)
        biweeklybudget.models.base.Base.metadata.create_all(engine)
        # load the sample data
        data_sess = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=conn)
        )
        SampleDataLoader(data_sess).load()
        data_sess.flush()
        data_sess.commit()
        data_sess.close()
        # close connection
        conn.close()
    else:
        logger.info('Skipping session-scoped DB refresh')
    # write the dump file
    do_mysqldump(dump_file_path)
    yield


@pytest.fixture(scope="class")
def class_refresh_db(dump_file_path):
    """
    This fixture rolls the DB back to the previous state when the class is
    finished; to be used on classes that alter data.

    Use like:

        @pytest.mark.usefixtures('class_refresh_db', 'testdb')
        class MyClass(AcceptanceHelper):
    """
    yield
    if 'NO_CLASS_REFRESH_DB' in os.environ:
        return
    logger.info('Refreshing DB (class-scoped)')
    restore_mysqldump(dump_file_path)


@pytest.fixture
def testdb():
    """
    DB fixture to be used in tests
    """
    # setup the connection
    conn = engine.connect()
    sess = sessionmaker(autocommit=False, bind=conn)()
    init_event_listeners(sess)
    # yield the session
    yield(sess)
    sess.close()
    conn.close()


@pytest.fixture(scope="session")
def testflask():
    """
    This is a version of pytest-flask's live_server fixture, modified for
    session use.
    """
    # Bind to an open port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

    from biweeklybudget.flaskapp.app import app  # noqa
    server = LiveServer(app, port)
    server.start()
    yield(server)
    server.stop()


@pytest.fixture(scope="session")
def base_url(testflask):
    """
    Simple fixture to return ``testflask`` base URL
    """
    return testflask.url()


@pytest.fixture
def selenium(selenium):
    """
    Per pytest-selenium docs, use this to override the selenium fixture to
    provide global common setup.
    """
    selenium.set_window_size(1920, 1080)
    selenium.implicitly_wait(2)
    # from http://stackoverflow.com/a/13853684/211734
    selenium.set_script_timeout(30)
    # from http://stackoverflow.com/a/17536547/211734
    selenium.set_page_load_timeout(30)
    return selenium


@pytest.fixture
def chrome_options(chrome_options):
    chrome_options.add_argument('headless')
    return chrome_options


"""
Begin generated/parametrized tests for interest calculation.

I REALLY wish pytest still supported yield tests, this is sooooo messy!
"""


def pytest_generate_tests(metafunc):
    if (
        metafunc.function.__name__.startswith('test_calculate') and
        metafunc.module.__name__ == 'biweeklybudget.tests.unit.test_interest'
    ):
        if metafunc.cls.__name__ == 'TestDataAmEx':
            param_for_adbdaily_calc(metafunc, InterestData.amex)
        if metafunc.cls.__name__ == 'TestDataCiti':
            param_for_adbdaily_calc(metafunc, InterestData.citi)
        if metafunc.cls.__name__ == 'TestDataDiscover':
            param_for_adbdaily_calc(metafunc, InterestData.discover)


def param_for_adbdaily_calc(metafunc, s):
    dates = [d['start'].strftime('%Y-%m-%d') for d in s]
    metafunc.parametrize(
        'data',
        s,
        ids=dates
    )
