# Copyright (c) 2020, WAND Network Research Group
#                     Department of Computer Science
#                     University of Waikato
#                     Hamilton
#                     New Zealand
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330,
# Boston,  MA 02111-1307  USA
#
# @Author : Brendon Jones (Original Disaggregated Router)
# @Author : Dimeji Fayomi

from errno import ENOENT
from os import makedirs, environ, umask
from shutil import rmtree
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse

# NOTE
# prometheus can't be imported until we are sure that the environment has been
# configured appropriately with "prometheus_multiproc_dir", otherwise it won't
# use the correct multiprocess value class. If we were running as part of some
# other script (an init script?) then we could probably rely on that to set it
# for us. For now though, we deal with it by waiting as long as we can.

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        from prometheus_client import multiprocess, CollectorRegistry
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)

        params = parse_qs(urlparse(self.path).query)
        if 'name[]' in params:
            registry = registry.restricted_registry(params['name[]'])
        try:
            output = generate_latest(registry)
        except:
            self.send_error(500, 'error generating metric output')
            raise
        self.send_response(200)
        self.send_header('Content-Type', CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(output)


class _ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass


def start_http_server(port, addr=""):
    httpd = _ThreadingSimpleServer((addr, port), MetricsHandler)
    thread = Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()


# suppress errors when deleting a directory that doesn't exist
def check_rmtree(function, path, excinfo):
    exctype, value, _ = excinfo
    if exctype != FileNotFoundError or value.errno != ENOENT:
        raise


class PrometheusClient(object):
    def __init__(self):
        assert "prometheus_multiproc_dir" in environ
        self.running = False

    def start(self, port=8002, address=""):
        prometheus_dir = environ["prometheus_multiproc_dir"]
        # clear out the prometheus dir from any previous data
        rmtree(prometheus_dir, onerror=check_rmtree)
        # recreate the empty directory
        oldmask = umask(0o002)
        makedirs(prometheus_dir, mode=0o755)
        umask(oldmask)

        if not self.running:
            start_http_server(port, address)
            self.running = True
