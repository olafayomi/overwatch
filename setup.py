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
# @Author : Brendon Jones (Original Disaggregate Router)
# @Author : Dimeji Fayomi


try:
    from setuptools import setup, find_packages, Extension
except ImportError:
    from distutils.core import setup, Extension

requires = [
    "dpkt",
    "py-radix",
    "pyyaml",
    "prometheus_client",
]

modules = [
    Extension("Prefix", ["bgpcontroller/Prefix.c"],
            extra_compile_args=["-D_GNU_SOURCE"]),
    Extension("RouteEntry", ["bgpcontroller/RouteEntry.c"]),
]

setup(name="Overwatch",
        version="1.0.0",
        description="A controller for a centralised BGP control plane.",
        packages=find_packages(),
        ext_modules=modules,
        install_requires=requires,
        test_suite="tests",
        # replace the setuptools ScanningLoader with a normal TestLoader,
        # otherwise it tries to load every single file in the test directories
        test_loader="unittest:TestLoader",
        author="Brendon Jones",
        author_email="brendonj@waikato.ac.nz",
        url="http://www.wand.net.nz",
     )
