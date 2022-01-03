paraview-python-driver
============
Driver which enables running of [ParaView](http://www.paraview.org) code natively in your Python environment.

Allowing to integrate ParaView macro code in your python script and be executed in your Python environment, instead of the  `$ pvpython your_macro.py` usage.


Installation
============

[install.sh](install.sh) Installs ParaView 5.10 and all missing dependencies onto your system. Into ~/local by default. 

```
$ ./install.sh --prefix <INSTALL_FOLDER>
```

The `--prefix` argument prescribes where ParaView and dependencies will be installed.

Note: 
- Installation requires significant time; more than 30 minutes on a 20-core system.
- Ensure that $prefix/lib and prefix/lib64 are in `$LD_LIBRARY_PATH` after running install.sh

[install.py](install.py) Installs ParaView into the Python environment which is used to run the script. It also automaticaly executes install.sh with the same supplied `--prefix` option:

```
$ <your/env/python3> install.py --prefix <INSTALL_FOLDER>
```

Installation into your Python environment is done by copying the installed ParaView Python packages and library files into the Python environment folder. 

Another option to integrating ParaView into Python is to append the ParaView library folder to PYTHONPATH, however, this results in a segmentation error for the use case in driver.py


Usage
=====

```
    with ParaViewDriver('flow.dat', out_filetype='png') as pv_driver:
        pv_driver.print_mesh_wireframe()
        pv_driver.print_quality(quad='Edge Ratio')
        # quality = pv_driver.get_quality()
        pv_driver.print_quality_distribution()
```


Compatibility
=============
Only tested with ParaView 5.10 on Ubuntu 20.04 and Python 3.8. 

ParaView dependencies and versions used:
 - LLVM 13.0.0
 - Mesa 21.2.5 (+osmesa +llvmpipe)
 - libdrm 2.4.107


Files
=========

 - [driver.py](driver.py) - example driver
 - [flow.dat](flow.dat) - example 2D simulation output data from SU2_CFD


********************************************************************************

ParaView
========

[ParaView](http://www.paraview.org) is an open-source, multi-platform data analysis and
visualization application based on [Visualization Toolkit (VTK)](http://www.vtk.org).

ParaView is distributed under the BSD 3-clause License. For licenses of ParaView dependencies, refer to
http://www.paraview.org/paraview-license/.