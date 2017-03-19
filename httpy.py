#!/usr/bin/python
#*************************************************************************
#
# HTTPy version 0.2.0
#
# Copyright (c) 2012 Corbin <jdgregson@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope  that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#*************************************************************************

# Change this to whatever it is in your tests.
# TODO: This should be changed to /etc/something
# before httpy is released
CONFIG_FILE = "/home/corbin/httpy/trunk/httpy.conf"

import sys
import os
import socket
import logging
import mimetypes as types
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
import threading
import Queue
from bin import const
from bin import daemon
#import const
#from daemon import Daemon

def load_configuration():
    """
    Loads the configuration file. The file's path
    is set using the "CONFIG_FILE" variable.
    """

    try:
        conf_file = open(CONFIG_FILE, "r")
    except IOError as (errno, strerr):
        print "Could not load config file at '%s': %s" % (CONFIG_FILE, strerr)
        sys.exit(1)
    config = conf_file.read()
    exec(config)
    return

# TODO: Currently does not respect the LOG_MAX_SIZE
#  config setting. It simply appends always.
def log(message, message_type=None):
    """
    logs messages to the console and the log file.

    The first argument is the message to be logged.
    The second is the log entry type, and is not
    required. Valid types are 'info', 'error',
    'warning', and 'debug.' If no value is supplied,
    or the value supplied is not defined, it defaults
    to 'debug.'
    """

    print message
    if const.USE_TEXT_LOG:
        logger = logging.getLogger('httpy')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr = logging.FileHandler(const.LOG_LOCATION)
        hdlr.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(hdlr)
        if message_type is "info":
            logger.info(message)
        elif message_type is "error":
            logger.error(message)
        elif message_type is "warning":
            logger.warning(message)
        elif message_type is "debug":
            logger.debug(message)
        else:
            logger.debug(message)
        logger.removeHandler(hdlr)
    return

def read_header(header):
    """
    Takes an HTTP header as a string and converts it
    into a list, then returns the list. The values
    in the list are in the same order as they were
    in the header.
    """

    # commence complex string/list manipulation! :D
    _header = ' '.join(' '.join(' '.join(' '.join(header.split("\r\n"))\
              .strip().split('?')).split('&')).split('=')).split(' ')
    header = []
    for value in _header:
        header.append(value.replace("%20", " "))
    return header

def make_header(response, content_type, content_length):
    """
    Builds and returns an HTTP header as a string.
    All arguments are required, and must be strings.
    """

    header = "HTTP/1.1 %s\r\n" % response
    header += "Server: %s\r\n" % const.SERVER_INFO
    header += "Content-Length: %s\r\n" % content_length
    header += "Connection: close\r\n"
    header += "Content-Type: %s\r\n\n" % content_type
    return header

def index(path, page):
    """
    Creates an index of a directory and returns it
    as HTML.
    """

    # This code is kind of ugly...
    cmd = "ls -p '%s'" % path
    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE,
              stderr=STDOUT, close_fds=True)
    output = p.stdout.read()
    files = output.split("\n")
    html = "<html>\n<body>\n<h1>Index of '%s'</h1><br />\n" % page
    html += "<pre>Name%sSize<br /><hr />\n" % (' ' * 16)
    html += "<a href='../'>Parent Direcroty</a><br />\n"
    if len(files) > 1:
        for name in files[:-1]:
            try:
                fin = open("%s/%s" % (path, name), "r")
                fsize = str(len(fin.read()))
                fin.close()
            except IOError, e:
                fsize = "---"
            if page == "/":
                page = ""
            html += "<a href='%s/%s'>%s</a>%s%s\n" % (page,
                     name, name, ' '*(20-len(name)),fsize)
    html += "</pre>\n<br />\n<hr />\n</body>\n</html>"
    return html

def get_html(page):
    """
    Opens the file that the client requested, reads
    the contents, and returns them. If it is not able
    to read the file, it will return a 404 error, and
    attempt to load the default 'missing' page. If no
    missing page is found it will return a very basic
    header and HTML 404 message.
    """

    path = const.DOCUMENT_ROOT + os.path.abspath(page)
    try:
        fin = open(path, "r")
        html = fin.read()
        fin.close()
        response = "200 OK"
        mtype = types.guess_type(path)[0]
    except IOError as (errno, strerr):
        # requested page is a directory
        if errno == 21:
            # try to load the default page
            try:
                fin = open("%s/%s" % (path, const.DEFAULT_PAGE), "r")
                html = fin.read()
                fin.close()
                response = "200 OK"
                mtype = types.guess_type("%s/%s"%(path, const.DEFAULT_PAGE))[0]
            except IOError, e:
                # index the directory if the
                # configuration allows it
                if const.DIRECTORY_INDEXING:
                    html = index(path, page)
                    response = "200 OK"
                    mtype = "text/html"
                # if it doesn't allow it,
                # say that the directory
                # is forbidden
                else:
                    response = "403 Forbidden"
                    mtype = "text/html"
                    html = "<h1>403 Forbidden</h1>"
                    log("[403] %s is forbidden" % page, "info")
        # requested page is not found
        elif errno == 2:
            response = "404 Not Found"
            log("[404] %s not found" % page, "info")
            try:
                mtype = types.guess_type("%s/%s"%(const.DOCUMENT_ROOT,
                                          const.DEFAULT_PAGE))[0]
                fin = open("%s/%s" % (const.DOCUMENT_ROOT,
                            const.MISSING_PAGE), "r")
                html = fin.read()
                fin.close()
            except IOError as (errno, strerr):
                mtype = "text/html"
                html = "<h1>404 Not Found</h1>"
                log("%s is missing!" % const.MISSING_PAGE, "error")
        # requested page is forbidden (permission denied)
        elif errno == 13:
            response = "403 Forbidden"
            mtype = "text/html"
            html = "<h1>403 Forbidden</h1>"
            log("[403] %s is forbidden" % page, "info")
        else:
            raise IOError(errno, strerr)
    header = make_header(response, mtype, str(html.__len__()))
    return header + html

class ClientHandler(threading.Thread):
    """
    Gets clients from the queue and answers them. This
    is threaded, to allow multiple page requests to be
    answered at once. Be default, HTTPy threads five
    instances of this class.
    """

    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            # grab a client from the queue
            client, address = self.queue.get()
            client.settimeout(0.1)
            # client communication loop
            try:
                header = client.recv(1024)
            except:
                log("The connection to %s timed out"
                     % address[0], "info")
                header = None
            if header:
                header_data = read_header(header)
                if header_data.__len__() > 1:
                    request = header_data[1]
                    log("serving '%s' to %s" % (request, address[0]), "info")
                    client.send("%s\r\n" % get_html(request))
            client.close()

            # tell queue that the client has been served
            self.queue.task_done()

def main():
    """
    Main() just prepares everything, including the
    socket, port, threads and queue, then waits for
    connections, which it then puts on the queue for
    the ClientHandler threads to answer.
    """

    load_configuration()
    log("%s, starting..." % const.SERVER_INFO, "info")
    # create queue for threading
    queue = Queue.Queue()
    for i in range(const.THREADS):
        handler = ClientHandler(queue)
        handler.setDaemon(True)
        handler.start()
    # open socket, bind port, and listen
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((const.LISTEN_IP_ADDRESS, const.SERVER_PORT))
        log("Listening on port %s\n" % str(const.SERVER_PORT), "info")
    except socket.error as (errno, strerr):
        log("Could not bind port %s: %s. Exiting..." % (const.SERVER_PORT,
                                                        strerr), "error")
        sys.exit(1)
    else:
        sock.listen(5)
        while True:
            client, address = sock.accept()
            # place the client in the queue
            queue.put((client, address))
    finally:
        sock.close()

class HTTPyDaemon(daemon.Daemon):
    """
    Overrides the Daemon class's default run method.
    This tells the daemon to start main() after it
    is daemonized.
    """
    def run(self):
        while True:
            main()

if __name__ == "__main__":
    daemon = HTTPyDaemon('/tmp/httpy-daemon.pid')
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        elif '--no-daemon' == sys.argv[1]:
            main()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "Usage: %s start|stop|restart\n" % sys.argv[0]
        print "    --no-daemon  Stay in the foreground. For debugging.\n"
        sys.exit(2)