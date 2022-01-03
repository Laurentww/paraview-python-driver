#!/usr/bin/env python3

# Installs ParaView to the Python3.x environment in which this script is run

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from os import system, scandir, DirEntry
from os.path import expanduser, isfile, dirname, realpath, abspath, join
from shutil import copyfile, copytree
from subprocess import getoutput
from sys import version_info as py_ver, exec_prefix
from textwrap import dedent

parser = ArgumentParser(
    description='ParaView install script',
    prog=abspath(__file__),
    formatter_class=RawDescriptionHelpFormatter,
    epilog=dedent("""\
         Additional information:
             See https://github.com/Laurentww/paraview-python-driver for more info
             \n""")
)
parser.add_argument(
    '--prefix', type=str,
    help="Path to folder where ParaView modules and dependencies will be installed",
    default='~/local'
)
args = parser.parse_args()

# Install ParaView to system
install_script = join(dirname(realpath(__file__)), 'install.sh')
system(f"chmod +x {install_script} && bash {install_script} --prefix {args.prefix}")

# Find source location of packages and library files
find_folder = lambda w_dir, s: getoutput(f"find {w_dir} -maxdepth 1 -type d -name {s}")
python_src = lambda w_dir: find_folder(w_dir, 'python*')

paraview_locations = [
    find_folder("~/paraview/build", 'lib*'),
    join(args.prefix, "lib"),
    join(args.prefix, "lib64")
]
src_lib_dir, src_python_dir = None, None
for location in [expanduser(loc) for loc in paraview_locations]:
    src_lib_dir = location
    src_python_dir = python_src(location)
    if isfile(f"{src_python_dir}/site-packages/vtk.py"):
        break

dest_lib = f"{exec_prefix}/lib"

# Copy ParaView python packages and library files into current python environment
for file in scandir(f"{src_python_dir}/site-packages/"):  # type: DirEntry
    dest = f"{dest_lib}/python{py_ver.major}.{py_ver.minor}/site-packages/{file.name}"
    if file.is_file():
        copyfile(file.path, dest)
    else:
        copytree(file.path, dest, dirs_exist_ok=True)

for file in [
    "RemotingCore",
    "CommonMisc",
    "CommonCore",
    f"WrappingPythonCore{src_python_dir.rsplit('python')[-1]}",
    "FiltersProgrammable",
    "RemotingServerManager",
    "RemotingSettings",
    "RemotingApplication",
    "PVInSitu",
]:
    filename = f"libvtk{file}-pv5.10.so.1"

    # print(f'Copying `{f"{src_lib_dir}/{filename}"}` to {exec_prefix}/lib/ ..')
    copyfile(f"{src_lib_dir}/{filename}", f"{exec_prefix}/lib/{filename}")

print(
    ".. Done installing ParaView Python packages and library files "
    f"from `{src_lib_dir}` into `{dest_lib}` .."
)
