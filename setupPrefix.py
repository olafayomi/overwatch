from glob import glob
from os import path
from distutils.core import setup, Extension
from shutil import copy, rmtree

print("Building package, please wait ...")

setup(name="Prefix", version="1.0",
      ext_modules=[Extension("Prefix", ["bgpcontroller/Prefix.c"])])

setup(name="RouteEntry", version="1.0",
      ext_modules=[Extension("RouteEntry", ["bgpcontroller/RouteEntry.c"])])

print("Building completed sucesfully, moving compiled source")
dir = glob(path.join("build", "lib.*"))
if len(dir) == 1:
    dir = dir[0]
    print("Found target build directory %s" % dir)

    # Prefix
    file = glob(path.join(dir, "Prefix.*.so"))
    if len(file) == 1:
        file=file[0]
        print("Moving prefix file %s to build dir" % file)
        copy(file, ".")

    # Route Entry
    file = glob(path.join(dir, "RouteEntry.*.so"))
    if len(file) == 1:
        file=file[0]
        print("Moving route entry file %s to build dir" % file)
        copy(file, ".")

    print("Removing build directory")
    rmtree("build")
