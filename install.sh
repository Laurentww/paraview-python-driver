#!/usr/bin/env bash

# # Installs ParaView 5.10 (into ~/local by default)
# # Installing requires significant time and compute resources.
# # (+-40 minutes, depending on available core count)

# Script arguments:
#   --prefix:      Path to folder where ParaView modules and dependencies will be installed

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --prefix) prefix="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Install directory. Change this if you want to install ParaView to a different folder
if [ -z "$prefix" ]; then
    PREFIX=~/local
else
    PREFIX=prefix
fi


# Check if ParaView-batch already exists
PV_EXEC_FILE=$PREFIX/bin/pvbatch
while :
do
  read -t10 -rep 'ParaView executable `'$PV_EXEC_FILE$'` exists, overwrite? [y/n]\n' yn
  if [ $? -gt 128 ]; then
      echo "Timed out waiting for response, exiting .."
      exit 1
  fi

  case $yn in
  [yY]*)
      break
      ;;
  [nN]*)
      echo "Exiting .."
      exit 1
      ;;
  *) echo "Please enter y or n"
      ;;
  esac
done

# Ensure install folder exists
mkdir -p $PREFIX


# If $PREFIX/bin not found in $PATH, add it to $PATH
IFS=':' read -r -a paths <<< "$PATH"
if [[ ! " ${paths[*]} " =~ ${PREFIX/bin} ]]; then
    command='export PATH='$PREFIX/bin:\$PATH
    echo "$command" >> ~/.bashrc
    eval "$command"
fi

# Same; ensure $PREFIX/lib and $PREFIX/lib64 in $LD_LIBRARY_PATH
add_dirs=( lib lib64 )
IFS=':' read -r -a ld_paths <<< "$LD_LIBRARY_PATH"
for d_idx in in ${!add_dirs[*]}; do
    d_str=$PREFIX/${add_dirs[d_idx]}

    if [[ ! " ${ld_paths[*]} " =~ ${d_str} ]]; then
        command='export LD_LIBRARY_PATH='$d_str:\$LD_LIBRARY_PATH
        echo "$command" >> ~/.bashrc
        eval "$command"
    fi
done

# If sudo privileges, can also install dependencies using:
#sudo apt install -y \
#    openmpi-bin openmpi-common libopenmpi-dev \
#    bison flex libwayland-dev wayland-protocols libpciaccess-dev libglvnd-dev


# Ensure ninja exists
if ! command -v ninja &> /dev/null; then
    cd ~/ && git clone --single-branch -b release git://github.com/ninja-build/ninja.git
    cd ninja || { echo "ninja not cloned into ""$HOME"", exiting .." 1>&2 ; exit 1; }
    cmake -Bbuild-cmake
    cmake --build build-cmake -j "$(nproc --all)"
    cp build-cmake/ninja $PREFIX/bin/
fi


# Ensure meson exists
if ! command -v meson &> /dev/null; then
    pip3 install --user meson
    cp ~/{.l,l}ocal/bin/meson
fi



# Install intel libdrm; needed for Mesa
# Install only if libdrm does not exist or version is lower or equal to 2.4.106
libdrm_ver=$(grep -Po 'Version: \K.*' $PREFIX/lib64/pkgconfig/libdrm.pc)
if [ -z "$libdrm_ver" ] || printf "$libdrm_ver\n2.4.106" | sort -C -V ; then
    curl -O --output-dir ~ https://dri.freedesktop.org/libdrm/libdrm-2.4.107.tar.xz
    tar xf ~/libdrm-2.4.107.tar.xz -C ~ && rm -f !:2
    cd ~/libdrm-2.4.107 || { echo "libdrm not unpacked correctly into ""$HOME"", exiting .." 1>&2 ; exit 1; }
    mkdir build && cd "$_" || exit
    meson --PREFIX=$PREFIX --buildtype=release -Dintel=true
    ninja install
fi

export PKG_CONFIG_PATH=$PREFIX/lib64/pkgconfig


# Install wayland scanner and protocols if not existing
if ! command -v wayland-scanner &> /dev/null; then
    wget --no-check-certificate -P ~ https://wayland.freedesktop.org/releases/wayland-1.19.0.tar.xz
    tar xf ~/wayland-1.19.0.tar.xz -C ~
    rm -f !:2
    cd wayland-1.19.0 || { echo "wayland not unpacked correctly into ""$HOME"", exiting .." 1>&2 ; exit 1; }
    mkdir build && cd "$_" || exit
    meson --PREFIX=$PREFIX --buildtype=release -Ddocumentation=false
    ninja
    ninja install

    cd ~ && git clone https://gitlab.freedesktop.org/wayland/wayland-protocols.git
    cd wayland-protocols || { echo "wayland-protocols not cloned into ""$HOME"", exiting .." 1>&2 ; exit 1; }
    meson build/ --PREFIX=$PREFIX
    ninja -C build/ install
fi

export PKG_CONFIG_PATH=$PKG_CONFIG_PATH:$PREFIX/share/pkgconfig


echo -n -e "Downloading and decompressing llvm and mesa simultaneously "  # parallel saves time
( (echo \
"wget -P ~ https://github.com/llvm/llvm-project/releases/download/llvmorg-13.0.0/llvm-13.0.0.src.tar.xz ; " \
"tar xf ~/llvm-13.0.0.src.tar.xz -C ~ ; " \
"rm -f ~/llvm-13.0.0.src.tar.xz"; \
echo \
"curl -O --output-dir ~ https://archive.mesa3d.org//mesa-21.2.5.tar.xz ; " \
"tar xf ~/mesa-21.2.5.tar.xz -C ~ ; " \
"rm -f ~/mesa-21.2.5.tar.xz" \
) | parallel >/dev/null 2>&1 ) &

# Show spinner while waiting
pid=$!
while ps -a | awk '{print $1}' | grep -q "${pid}"; do
    c=$((i % 4))
    case ${c} in
       0) echo  -n -e "/\c" ;;
       1) echo  -n -e "-\c" ;;
       2) echo  -n -e "\\ \b\c" ;;
       3) echo  -n -e "|\c" ;;
    esac
    i=$((i + 1))
    sleep 1
    echo  -n -e "\b\c"
done
echo ""


# build llvm
cd ~/llvm-13.0.0.src || { echo "llvm-13.0.0 not unpacked correctly into ""$HOME"", exiting .." 1>&2 ; exit 1; }
mkdir -p build && cd "$_" || exit
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON \
    -DLLVM_TARGETS_TO_BUILD:STRING=X86 \
    -DCMAKE_INSTALL_PREFIX=~/mesa-21.2.5/subprojects/llvm \
    -DLLVM_INSTALL_UTILS:BOOL=ON
numcores=$(lscpu | grep 'Core(s) per socket\|Socket(s)\|Thread(s)' | awk 'NF>1{{print $NF}}' | tr '\n' '*' | sed 's/*$/\n/' | bc)
cmake --build . -j $numcores || exit 1
cmake --build . -j $numcores --target install || exit 1



# Install Mesa with osmesa +llvmpipe
cd ~/mesa-21.2.5 || { echo "mesa not unpacked correctly into ""$HOME"", exiting .." 1>&2 ; exit 1; }

# Install Mako to python3 if not existing
if [ -z "$(python3 -m pip show Mako | grep Mako)" ]; then
    python3 -m ensurepip
    python3 -m pip install Mako
fi

# Create `custom-llvm.ini` and `meson.build` to tell meson how to link against LLVM
cat > custom-llvm.ini <<EOF
[binaries]
llvm-config = '$(pwd)/subprojects/llvm/bin/llvm-config'
python = '$(which python3)'
EOF

cat > subprojects/llvm/meson.build <<EOF
project('llvm', ['cpp'])

cpp = meson.get_compiler('cpp')

_deps = []
_search = join_paths(meson.current_source_dir(), 'lib')
foreach d : ['libLLVMCodeGen', 'libLLVMScalarOpts', 'libLLVMAnalysis',
             'libLLVMTransformUtils', 'libLLVMCore', 'libLLVMX86CodeGen',
             'libLLVMSelectionDAG', 'libLLVMipo', 'libLLVMAsmPrinter',
             'libLLVMInstCombine', 'libLLVMInstrumentation', 'libLLVMMC',
             'libLLVMGlobalISel', 'libLLVMObjectYAML', 'libLLVMDebugInfoPDB',
             'libLLVMVectorize', 'libLLVMPasses', 'libLLVMSupport',
             'libLLVMLTO', 'libLLVMObject', 'libLLVMDebugInfoCodeView',
             'libLLVMDebugInfoDWARF', 'libLLVMOrcJIT', 'libLLVMProfileData',
             'libLLVMObjCARCOpts', 'libLLVMBitReader', 'libLLVMCoroutines',
             'libLLVMBitWriter', 'libLLVMRuntimeDyld', 'libLLVMMIRParser',
             'libLLVMX86Desc', 'libLLVMAsmParser', 'libLLVMTableGen',
             'libLLVMFuzzMutate', 'libLLVMLinker', 'libLLVMMCParser',
             'libLLVMExecutionEngine', 'libLLVMCoverage', 'libLLVMInterpreter',
             'libLLVMTarget', 'libLLVMX86AsmParser', 'libLLVMSymbolize',
             'libLLVMDebugInfoMSF', 'libLLVMMCJIT', 'libLLVMXRay',
             'libLLVMX86Disassembler',
             'libLLVMMCDisassembler', 'libLLVMOption', 'libLLVMIRReader',
             'libLLVMLibDriver', 'libLLVMDlltoolDriver', 'libLLVMDemangle',
             'libLLVMBinaryFormat', 'libLLVMLineEditor',
             'libLLVMWindowsManifest', 'libLLVMX86Info']
  _deps += cpp.find_library(d, dirs : _search)
endforeach

dep_llvm = declare_dependency(
  include_directories : include_directories('include'),
  dependencies : _deps,
  version : '13.0.0',
)

has_rtti = false
irbuilder_h = files('include/llvm/IR/IRBuilder.h')
EOF


# Fix method name compatibility with llvm 13.0.0
method_strs_old=(
    TargetInfo
    Target
    TargetMC
    AsmPrinter
    AsmParser
    Disassembler
)
method_strs_new=(
    AllTargetInfos
    NativeTarget
    AllTargetMCs
    NativeAsmPrinter
    NativeAsmParser
    NativeDisassembler
)
files_to_change=(
    amd/llvm/ac_llvm_util.c
    gallium/drivers/radeonsi/si_pipe.c
    amd/compiler/tests/main.cpp
    amd/vulkan/radv_device.c
)
for cur_file in "${files_to_change[@]}"; do
    for suffix in "()" ","; do
        for m_idx in ${!method_strs_old[*]}; do
            old_str=LLVMInitializeAMDGPU${method_strs_old[$m_idx]}$suffix
            new_str=LLVMInitialize${method_strs_new[$m_idx]}$suffix

#             echo "Replacing "$old_str" into "$new_str" in "$cur_file".."
            sed -i "s|$old_str|$new_str|g" "src/$cur_file"  || exit 1
        done
    done
done

meson --prefix=$PREFIX \
    build/ \
    --native-file custom-llvm.ini \
    -Dglx=disabled \
    -Dbuildtype=release \
    -Dcpp_rtti=false \
    -Dvulkan-drivers=intel,swrast \
    -Dosmesa=true \
    -Dshared-llvm=enabled \
    -Dgallium-drivers=r300,r600,radeonsi,virgl,svga,swrast,iris
ninja -C build/ install || exit 1


# Install ParaView
osmesa_lib=$(find ~/mesa-* -name libOSMesa.so -print -quit)
osmesa_dir=$(find ~/mesa-* -name GL -print -quit)

cd ~ || exit
rm -rf ~/paraview
git clone --recursive https://gitlab.kitware.com/paraview/paraview.git
cd ~/paraview || { echo "ParaView not cloned into ""$HOME"", exiting .." 1>&2 ; exit 1; }
mkdir -p build && cd "$_" || exit

cp -r "$osmesa_dir" ~/paraview/VTK/ThirdParty/glew/

cmake \
    -GNinja \
    -DCMAKE_INSTALL_PREFIX=$PREFIX \
    -Dvtk_undefined_symbols_allowed=OFF \
    -DVTK_OPENGL_HAS_OSMESA:BOOL=ON \
    -DOSMESA_LIBRARY:FILEPATH="$osmesa_lib" \
    -DOSMESA_INCLUDE_DIR:PATH="$osmesa_dir" \
    -DVTK_USE_X:BOOL=FALSE \
    -DPARAVIEW_INSTALL_DEVELOPMENT_FILES:BOOL=OFF \
    -DPARAVIEW_USE_QT:BOOL=OFF \
    -DPARAVIEW_USE_PYTHON:BOOL=ON \
    -DPARAVIEW_USE_MPI:BOOL=ON \
    -DVTK_SMP_IMPLEMENTATION_TYPE:STRING=OpenMP \
    -DCMAKE_BUILD_TYPE:STRING=Release ../
ninja || exit 1


# Copy required LLVM and ParaView libraries into $PREFIX install folder
cp -r ~/paraview/build/lib64/* $PREFIX/lib64/  || exit 1
cp ~/llvm-13.0.0.src/build/lib/libLLVM* $PREFIX/lib64/  || exit 1
#cp ~/mesa-21.2.5/subprojects/llvm/lib/libLLVM* $PREFIX/lib64/

# Copy ParaView executables into $PREFIX install folder
cp ~/paraview/build/bin/p* $PREFIX/bin/ || exit 1


# Clean up downloaded package folders
cd ~ && rm -rf ninja libdrm-2.4.107 wayland-* llvm-13.0.0.src
