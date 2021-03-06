######################################################################
#
#  py_proximity_tests.py -- Unit tests for the PyProximity classes.
#
#  Preparing for test:
#
#    1 - cd to the dibas project home, vegas_devel/scripts/dibas
#
#    2 - copy the appropriate 'dibas.conf', either 'dibas.conf.gb' or
#        'dibas.conf.shao', to ./etc/config/dibas.conf
#
#    3 - source the dibas.bash of the installation to test against. For
#        example, 'source /home/dibas/dibas.bash', or 'source
#        /opt/dibas/dibas.bash', etc. This loads the correct python
#        environment for these tests.
#
#    4 - from the project home run nosetests
#
#  Though these tests use the sourced dibas environment, they are
#  hard-coded to use the 'dibas.conf' file installed in step 2
#  above. This is because code development may require the updated
#  'dibas.conf' that hasn't yet been installed.
#
#  Copyright (C) 2013 Associated Universities, Inc. Washington DC, USA.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#  Correspondence concerning GBT software should be addressed as follows:
#  GBT Operations
#  National Radio Astronomy Observatory
#  P. O. Box 2
#  Green Bank, WV 24944-0002 USA
#
######################################################################

import threading
import zmq
from py_proximity import PyProximityServer, PyProximityClient, _send_msgpack, _recv_msgpack
from nose import with_setup
import random

try:
    from zmq.error import ZMQError
except ImportError:
    from zmq.core import ZMQError

class Foo:
    def cat(self):
        """
        Cat process.
        """
        return "meow"

    def dog(self):
        """
        Dog process.
        """
        return "woof"

    def frog(self):
        """
        Frog process.
        """
        return "rivet!"

    def add_two(self, x, y):
        """
        Adds two values together.
        """
        return x + y

    def long_delay(self, delay):
        """
        waits 'delay' seconds before returning.
        """
        time.sleep(delay)
        return delay

    def complicated_data(self, data):
        """data is expected to be a dictionary containing the following:
           the_strings: a list of strings, to be concatenated the_ints: a
           list of strings, to be summed, and to have each element
           multiplied by two.

           the return will be a list: first element, the concatenated
           strings.  second element, the sum; third element, the list of
           ints multiplied by two.

        """

        retval = []
        retval.append(''.join(data["the_strings"]))
        retval.append(sum(data["the_ints"]))
        retval.append(map(lambda x: x + 2, data["the_ints"]))
        return retval


def get_ephemeral_port():
    f=open('/proc/sys/net/ipv4/ip_local_port_range', 'r')
    lines = f.readlines()
    f.close()
    pts = [int(p) for p in lines[0].rstrip().split('\t')]
    return random.randint(*pts)

url = ""

proxy = None
foo = None
ctx = zmq.Context()

def setup_zmq_server():
    global proxy
    global foo
    global url
    fail = True

    while fail:
        try:
            url = "tcp://127.0.0.1:" + str(get_ephemeral_port())
            proxy = PyProximityServer(ctx, url)
            fail = False
        except ZMQError:
            pass

    foo = Foo()
    proxy.expose("foo", foo)

    def threadfunc():
        proxy.run_loop()

    # Run the proxy in a separate thread. TBF: Caution! exceptions here
    # leave this running, because the 'proxy.quit_loop()' call is
    # skipped. Thus the unit test will hang.  This is why asserts come
    # after 'proxy.quit_loop()'.
    threading.Thread(target=threadfunc).start()

def stop_zmq_server():
    global proxy
    global foo
    proxy.quit_loop()
    del proxy
    del foo
    foo = None
    proxy = None

@with_setup(setup_zmq_server, stop_zmq_server)
def test_ZMQ_Proxy_Interface():

    # Now for a few tests. We're not testing the proxy client, just the
    # proxy server, so we'll create a ZMQ socket and feed it the
    # expected dictionaries, and examine the replies.

    # Test for all functions of 'Foo':
    test_sock = ctx.socket(zmq.REQ)
    test_sock.connect(url)
    msg = {"name": "foo", "proc": "cat", "args": [], "kwargs": {}}
    _send_msgpack(test_sock, msg)
    cat_ret = _recv_msgpack(test_sock)

    msg = {"name": "foo", "proc": "dog", "args": [], "kwargs": {}}
    _send_msgpack(test_sock, msg)
    dog_ret = _recv_msgpack(test_sock)

    msg = {"name": "foo", "proc": "frog", "args": [], "kwargs": {}}
    _send_msgpack(test_sock, msg)
    frog_ret = _recv_msgpack(test_sock)

    # Test to ensure 'list_methods' works. Should return method names,
    # and doc strings:
    msg = {"name": "foo", "proc": "list_methods", "args": [], "kwargs": {}}
    _send_msgpack(test_sock, msg)
    list_ret = _recv_msgpack(test_sock)

    # Test exception handling; in this case, we're asking for a function
    # in 'bar', which doesn't exist.
    msg = {"name": "bar", "proc": "cat", "args": [], "kwargs": {}}
    _send_msgpack(test_sock, msg)
    except_ret = _recv_msgpack(test_sock)

    # Test positional arguments. 'add_two' expects two arguments.
    msg = {"name": "foo", "proc": "add_two", "args": [2, 2], "kwargs": {}}
    _send_msgpack(test_sock, msg)
    add_listargs_ret = _recv_msgpack(test_sock)

    # Test keyword arguments. 'add_two' expects two arguments, 'x', 'y'.
    msg = {"name": "foo", "proc": "add_two", "args": [], "kwargs": {"x": 2, "y": 3}}
    _send_msgpack(test_sock, msg)
    add_kwargs_ret = _recv_msgpack(test_sock)

    # Test mixed args: first is bound positionally, second is keyword.
    msg = {"name": "foo", "proc": "add_two", "args": [3], "kwargs": {"y": 3}}
    _send_msgpack(test_sock, msg)
    add_mixedargs_ret = _recv_msgpack(test_sock)

    assert cat_ret == "meow"
    assert dog_ret == "woof"
    assert frog_ret == "rivet!"

    list_ret.sort() # Ensure they are in the order test thinks they are
    assert len(list_ret) == 6 # 6 functions: cat, dog, frog, add_two, long_delay
    # test for function name & doc string
    assert 'add_two' in list_ret[0]
    assert 'Adds two' in list_ret[0][1]
    assert 'cat' in list_ret[1]
    assert 'Cat process' in list_ret[1][1]
    assert 'complicated_data' in list_ret[2]
    assert 'data is expected to be' in list_ret[2][1]
    assert 'dog' in list_ret[3]
    assert 'Dog process' in list_ret[3][1]
    assert 'frog' in list_ret[4]
    assert 'Frog process' in list_ret[4][1]
    assert "KeyError" in except_ret['EXCEPTION']
    # test for use of params. Result '4' is from two positional args,
    # '5' from two keyword args, and '6' from a positional and a keyword
    # arg used together.
    assert add_listargs_ret == 4
    assert add_kwargs_ret == 5
    assert add_mixedargs_ret == 6

@with_setup(setup_zmq_server, stop_zmq_server)
def test_ZMQ_proxy_client():
    """
    Checks the client proxy class. The client proxy should obtain the
    exposed function names of the named object on the server, the doc
    strings for each of those, and should be able to call the functions
    as if they were local.
    """

    foo_proxy = PyProximityClient(ctx, 'foo', url)

    assert 'Cat process' in foo_proxy.cat.__doc__
    cat_ret = foo_proxy.cat()
    assert cat_ret == "meow"

    assert 'Dog process' in foo_proxy.dog.__doc__
    dog_ret = foo_proxy.dog()
    assert dog_ret == "woof"

    assert 'Frog process' in foo_proxy.frog.__doc__
    frog_ret = foo_proxy.frog()
    assert frog_ret == "rivet!"

    assert 'Adds two' in foo_proxy.add_two.__doc__
    add_ret = foo_proxy.add_two(2, 2)
    assert add_ret == 4
    add_ret = foo_proxy.add_two(2, y = 3)
    assert add_ret == 5
    add_ret = foo_proxy.add_two(y = 3, x = 4)
    assert add_ret == 7
