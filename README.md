# HTTPy
Lightweight and simple HTTP server written in Python.

HTTPy was originally hosted here: http://bazaar.launchpad.net/~corbin/httpy


#************************ ABOUT HTTPY ************************#

    HTTPy is a lightweight web-server, written in python.
    It is rather basic, and is not capable of parsing any
    server-side scripts. It simply serves any page that
    the client asks for, or returns a 404 error. It is also
    able to serve non-HTLM items, such as images, programs,
    and videos.
    HTTPy is able to run in two modes: terminal, and daemon.
    In terminal mode, HTTPy will still log all messages to
    a text log. You have to disable text logs in the config
    file to stop this.
    HTTPy communicates using HTTP headers, but it can only
    send one of three responses to a request: '200 OK', '404
    Not Found', or '403 Forbidden.' Some effort was put into
    preventing directory transversal, but as always, it may
    still be vulnerable in many ways. You are encouraged to
    look for vulnerabilities and bugs. If you find any, don't
    hesitate to report them on HTTPy's bug tracker:

    https://bugs.launchpad.net/httpy

    If your bug report does not receive a response in a few
    days, or if you have any questions, comments, critiques,
    or I-hate-yous, please email me at:

    jdgregson@gmail.com




#********************* INSTALLATION/SETUP ********************#

    For HTTPy to run, the files 'const.py', 'daemon.py'
    and '__init__.py' must be in the 'bin' directory,
    which must be in the same directory as 'httpy.'

    1.  Edit the 'httpy' file and change the variable
        "CONFIG_FILE" near the top of the file to the
        path of HTTPy's configuration file on your
        system.

    2.  Edit the 'httpy.conf' config file to fit your
        system. Make sure that the SERVER_PORT,
        LISTEN_IP_ADDRESS, DOCUMENT_ROOT, and LOG_LOCATION
        variables are set correctly.

    3.  Start HTTPy by calling the file 'httpy' with 'start'
        as the argument ('httpy start'). Use '--no-daemon'
        instead of 'start' if you would like to see console
        messages.
