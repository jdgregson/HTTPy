#!/usr/bin/env python3
#*************************************************************************
#
# HTTPy version 0.2.1
#
# Copyright (c) 2020 Jonathan Gregson <jonathan@jdgregson.com>
#                                     <jdgregson@gmail.com>
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

import sys
import os
import socket
import logging
import threading
import queue
import mimetypes as types
from subprocess import Popen
from subprocess import PIPE
from subprocess import STDOUT
from email import message_from_string
from bin import const
from bin import daemon

# Globals
sock = None
handlers = []
CWD = os.getcwd()
CONFIG_FILE = CWD + "/httpy.conf"


def load_configuration():
    """
    Loads the configuration file. The file's path is set using the "CONFIG_FILE"
    variable.
    """
    try:
        conf_file = open(CONFIG_FILE, "r")
    except IOError as e:
        error, strerr = e.args
        print(f"Could not load config file at '{CONFIG_FILE}': {strerr}")
        sys.exit(1)
    config = conf_file.read()
    exec(config)
    return


# TODO: Currently does not respect the LOG_MAX_SIZE config setting. It simply
# appends always.
def log(message, message_type=None):
    """
    logs messages to the console and the log file. The first argument is the
    message to be logged. The second is the log entry type, and is not required.
    Valid types are 'info', 'error', 'warning', and 'debug.' If no value is
    supplied, or the value supplied is not defined, it defaults to 'debug.'
    """
    print(message)
    if const.USE_TEXT_LOG:
        logger = logging.getLogger("httpy")
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
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


def safe_exit():
    """
    Closes all open connections, closes the socket, and then exits 0.
    """
    print("\nClosing socket and exiting...\n")
    if sock:
        for handler in handlers:
            handler.close()
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
    sys.exit(0)


def get_file_contents(filename):
    """
    Attempts to read files and returns content. If initial read fails, tries to
    read again in binary mode.
    """
    try:
        with open(filename) as f:
            return f.read()
    except:
        with open(filename, mode="rb") as f:
            return f.read()


def send_data(client, http_status, content_type, data):
    """
    Sends the specified data to the specified client. Will also craft and send
    an HTTP header using the content type and HTTP status specified.
    """
    header = make_header(http_status, content_type, len(data))
    client.send(bytes(header, "utf-8"))
    if not isinstance(data, (bytes, bytearray)):
        data = bytes(data, "utf-8")
    client.send(data)


def send_redirect(client, http_status, content_type, data):
    """
    Sends the specified data to the specified client. Will also craft and send
    an HTTP header using the content type and HTTP status specified.
    """
    redirect_location = data
    data = f"Permanently moved <a href='{data}'>here</a>."
    header = make_header(http_status, content_type, len(data),
        {"Location": redirect_location})
    client.send(bytes(header, "utf-8"))
    client.send(bytes(data, "utf-8"))


def read_header(header):
    """
    Takes an HTTP request as a string and returns the headers as a dict.
    """
    request = str(header, "ASCII").split("\r\n", 1)[0]
    request_headers = str(header, "ASCII").split("\r\n", 1)[1]
    request_headers = message_from_string(request_headers)
    request_headers = dict(request_headers)
    request_headers["Method"] = request.split(" ")[0]
    request_headers["Request"] = request.split(" ")[1]
    request_headers["Protocol"] = request.split(" ")[2]
    return request_headers


def make_header(http_status, content_type, content_length, extra_headers={}):
    """
    Builds and returns an HTTP header as a string. All arguments are required,
    and must be strings.
    """
    header = f"HTTP/1.1 {http_status}\r\n"
    header += f"Server: {const.SERVER_INFO}\r\n"
    header += f"Content-Length: {content_length}\r\n"
    header += f"Connection: close\r\n"
    for header_name in extra_headers:
        header += f"{header_name}: {extra_headers[header_name]}\r\n"
    header += f"Content-Type: {content_type}\r\n\n"
    return header


def get_dir_index(path, page):
    """
    Creates an index of a directory and returns it as HTML.
    """
    if page[0] is not "/":
        page = f"/{page}"
    if page is "/":
        page = ""
    index_html = "<pre>\n"
    files = os.listdir(path)
    for file in files:
        index_html += f"<a href='{page}/{file}'>{file}</a>\n"
    index_html += "</pre>"
    return index_html


def get_response(requested_page):
    """
    Reads the contents of the requested file and returns them along with the
    accompanying file MIME type, and a helpful HTTP status code. If a directory
    is requested, get_response will look for the default file as defined by
    const.DEFAULT_PAGE. If the default page is not found, it return a directory
    listing (if allowed by const.DIRECTORY_INDEXING). Else, it will return a 404
    page.
    """
    path_requested = const.DOCUMENT_ROOT + os.path.abspath(requested_page)
    path_default = f"{path_requested}/{const.DEFAULT_PAGE}"
    http_status = 200
    response_type = "text/html"

    try:
        if os.path.exists(path_requested):
            if os.path.isfile(path_requested):
                response_data = get_file_contents(path_requested)
                response_type = types.guess_type(path_requested)[0]
            elif os.path.isdir(path_requested):
                if requested_page[-1] is not "/":
                    response_data = f"{requested_page}/"
                    http_status = 301
                elif os.path.exists(path_default):
                    response_data = get_file_contents(path_default)
                elif const.DIRECTORY_INDEXING:
                    response_data = get_dir_index(path_requested,
                        requested_page)
                else:
                    response_data = get_error_html("403 Forbidden")
                    http_status = 403
        else:
            response_data = get_error_html("404 Not Found")
            http_status = 404
    except Exception as e:
        errno, strerr = e.args
        if errno == 13:
            response_data = get_error_html("403 Forbidden")
            http_status = 403
            log(f"403 Forbidden: {strerr}", "warning")
        else:
            response_data = get_error_html("500 Internal Server Error")
            http_status = 500
            log(f"Error {errno}: {strerr}", "error")

    return http_status, response_type, response_data


def get_error_html(message):
    """
    Returns HTML conveying the specified message as an H1 tag without deprecated
    serif fonts.
    """
    return f"""
        <!DOCYTPE html>
        <html>
        <head>
            <title>{message}</title>
            <style>* {{font-family: Arial, Sans-Serif;}}</style>
        </head>
        <body>
            <h1>{message}</h1>
        </body>
        </html>
    """


class ClientHandler(threading.Thread):
    """
    Gets clients from the queue and answers them. This is threaded to allow
    multiple page requests to be answered at once. Be default, HTTPy threads
    five instances of this class.
    """
    def __init__(self, q):
        threading.Thread.__init__(self)
        self.q = q
        self.client = None

    def close(self):
        if self.client:
            self.client.close()

    def run(self):
        while True:
            # get a client from the queue
            self.client, address = self.q.get()
            self.client.settimeout(0.1)
            try:
                header = self.client.recv(1024)
            except:
                log("The connection to %s timed out"
                     % address[0], "info")
                header = None
            if header:
                try:
                    header_data = read_header(header)
                except Exception as e:
                    error, strerr = e.args
                    log(f"Error parsing header from {str(address)}: {strerr}",
                        "error")
                    error_message = get_error_html("500 Internal Server Error")
                    send_data(self.client, "500", "text/html", error_message)
                    self.client.close()
                    header_data = None
                if header_data:
                    try:
                        request = header_data["Request"]
                        log(f"Serving '{request}' to {str(address)}", "info")
                        http_status, response_type, response_data = (
                            get_response(request))
                        if http_status == 301:
                            send_redirect(self.client, http_status, "text/html",
                                response_data)
                        else:
                            send_data(self.client, http_status, response_type,
                                response_data)
                    except Exception as e:
                        errno, strerr = e.args
                        print(strerr)
                        log("Error getting requested file for " +
                            f"{str(address)}: {strerr}", "error")
                        error_message = get_error_html(
                            "500 Internal Server Error")
                        send_data(self.client, "500", "text/html",
                            error_message)
            self.client.close()
            self.q.task_done()


def main():
    """
    Main() just prepares everything, including the socket, port, threads and
    queue, then waits for connections, which it then puts on the queue for the
    ClientHandler threads to answer.
    """
    global sock
    global handlers

    load_configuration()
    log("%s, starting..." % const.SERVER_INFO, "info")
    # create queue for threading
    q = queue.Queue()
    for i in range(const.THREADS):
        handler = ClientHandler(q)
        handler.setDaemon(True)
        handler.start()
        handlers.append(handler)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((const.LISTEN_IP_ADDRESS, const.SERVER_PORT))
        log("Listening on port %s\n" % str(const.SERVER_PORT), "info")
    except socket.error as e:
        errno, strerr = e.args
        log("Could not bind port %s: %s. Exiting..." % (const.SERVER_PORT,
                                                        strerr), "error")
        sys.exit(1)
    else:
        sock.listen(5)
        while True:
            client, address = sock.accept()
            log("accepted connection from %s" % str(address), "info")
            q.put((client, address))
    finally:
        safe_exit()


class HTTPyDaemon(daemon.Daemon):
    """
    Overrides the Daemon class's default run method. This tells the daemon to
    start main() after it is daemonized.
    """
    def run(self):
        while True:
            main()


if __name__ == "__main__":
    daemon = HTTPyDaemon("/tmp/httpy-daemon.pid")
    if len(sys.argv) == 2:
        if "start" == sys.argv[1]:
            daemon.start()
        elif "stop" == sys.argv[1]:
            daemon.stop()
        elif "restart" == sys.argv[1]:
            daemon.restart()
        elif "--no-daemon" == sys.argv[1]:
            try:
                main()
            except KeyboardInterrupt:
                safe_exit()
        else:
            print("Unknown command")
            sys.exit(2)
        sys.exit(0)
    else:
        print("Usage: %s start|stop|restart\n" % sys.argv[0])
        print("    --no-daemon  Stay in the foreground. For debugging.\n")
        sys.exit(2)
