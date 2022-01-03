#!/usr/bin/env python3

from argparse import Namespace
from gc import collect
from os import makedirs, dup, dup2, open as osopen, close, devnull, O_WRONLY
from os.path import join, abspath, dirname, isabs, basename, curdir
from typing import Tuple

import matplotlib.pyplot as plt
import numpy as np

try:
    from paraview.simple import (
        OpenDataFile, GetActiveViewOrCreate, Connect, Disconnect, Show, Hide,
        GetColorTransferFunction, GetOpacityTransferFunction, GetScalarBar,
        HideScalarBarIfNotNeeded, LoadPalette, GetLayout, GetActiveCamera, ExportView,
        SaveScreenshot, _DisableFirstRenderCameraReset, MeshQuality
    )
    from paraview.vtk.numpy_interface.dataset_adapter import WrapDataObject
    from paraview.servermanager import Fetch, vtkProcessModule, ProxyManager

except ImportError as e:
    raise ImportError(
        'ParaView Python library not found; '
        'See ParaView installation script in install.py \n\n'
    ) from e


class ParaViewDriver:
    """ ParaView driver for printing and extracting statistics of meshes """

    filetype_out_default = 'pdf'
    n_pixels = 2.56e6
    color = (0, 0.66666666, 0)  # green

    # Default filenames
    print_filenames = Namespace(
        mesh="mesh_ParaView",
        quality="mesh_quality_ParaView",
        distribution="mesh_quality_distribution",
    )
    strs = Namespace(
        mesh='Mesh',
        quality='Quality',
    )

    # Quality print defaults
    # Quad measure options: 'Aspect Ratio' | 'Skew' | 'Area' | 'Radius Ratio'
    measure_quad = 'Skew'
    # Triangle measure options: 'Aspect Ratio' | 'Edge Ratio' | 'Area' | 'Radius Ratio'
    measure_triangle = 'Radius Ratio'
    #   Other Color bar preset options: 'Viridis (matplotlib)' | 'Rainbow Uniform'
    color_bar_preset = 'Blue Orange (divergent)'

    # Placeholders
    print_filename = None
    color_bar = None

    def __init__(self, mesh_flow_src, out_filetype=None, n_pixels=None, out_dir=None):
        """
        Parameters
        ----------
        mesh_flow_src : str
            Full path to the SU2 result flow file (e.g. SU2_CFD's flow.dat output)

        out_filetype : str
            Print file type

        n_pixels : int
            Output image pixel count

        out_dir : str
            Path to output directory

        """

        self.mesh_flow_src = mesh_flow_src
        self.filetype = out_filetype or self.filetype_out_default
        self.n_pixels = n_pixels or self.n_pixels
        self.out_dir = out_dir or curdir

    def __enter__(self):

        Connect()
        _DisableFirstRenderCameraReset()  # disable automatic camera reset on 'Show'

        # Open data file
        self.data = OpenDataFile([self.mesh_flow_src], registrationName=self.strs.mesh)
        self.data.DataArrayStatus = ['Density']  # Change to any quantity of interest

        # get active view
        self.view = GetActiveViewOrCreate('RenderView')
        self.view.InteractionMode = '2D'

        return self

    def print_mesh_wireframe(self, file_out=None, color=None, out_dir=None):
        """ Prints a view of a 2D mesh wireframe to disk using ParaView

        Parameters
        ----------
        file_out : str
            Name of the output print file. Without file type extension.

        color : Tuple[int]
            Mesh print color (r,g,b)

        out_dir : str
            Optional; If given, and `file_out` is not a full path, `w_dir` is used as
                        saving folder.
                      else: the same folder as input `flow.dat` is assumed
        """

        self._set_print_filename(file_out or self.print_filenames.mesh, out_dir)
        print(
            f"Printing mesh wireframe into `{self._out_dir(out_dir)}` using ParaView .."
        )

        # show data in view
        flow_display = Show(self.data, self.view, 'UnstructuredGridRepresentation')
        flow_display.Representation = 'Wireframe'
        flow_display.LineWidth = 0.1
        flow_display.Opacity = 0.85

        color = color or self.color
        flow_display.AmbientColor = color
        flow_display.DiffuseColor = color

        self._print()

        Hide(self.data, self.view)

    def print_quality(
            self,
            file_out=None,
            color_bar_preset=None,
            color_bar_title=None,
            color_bar_pos='bottom left',
            out_dir=None,
            log_scale=False,
            invert_colors=False,
            **measure
    ):
        """ Prints a view of the quality of a 2D mesh to disk using ParaView

        Parameters
        ----------
        file_out : str
            Name of the output print file

        color_bar_preset : str
            Color bar preset name. Defaults to `self.color_bar_preset`

        color_bar_title : str
            Color bar title

        color_bar_pos : str
            Screen position of the color bar. Options: `bottom left` | `top right`

        out_dir : str
            Full path to where output figures are saved

        log_scale : bool
            Whether color bar has log scaling

        invert_colors : bool
            Whether to invert the color bar colors

        measure
            if contains 'quad': overrides `self.measure_quad`
            if contains 'triangle': overrides `self.measure_triangle`
        """

        self._set_print_filename(file_out or self.print_filenames.quality)
        print(
            f"Printing mesh quality into `{self._out_dir(out_dir)}` using ParaView .."
        )

        # create a new 'Mesh Quality'
        mesh_quality = self._setup_mesh_quality(**measure)

        # get color transfer function/color map for 'Quality'
        quality_LUT = GetColorTransferFunction('Quality')

        # show data in view
        quality_disp = Show(mesh_quality, self.view, 'UnstructuredGridRepresentation')

        # show color bar/color legend
        quality_disp.SetScalarBarVisibility(self.view, True)

        # change representation type
        quality_disp.SetRepresentationType('Wireframe')

        # get color legend/bar for quality_LUT in view renderView1
        self.color_bar = GetScalarBar(quality_LUT, self.view)
        self.color_bar.WindowLocation = 'Any Location'
        self.color_bar.Position = \
            [0.8, 0.6] if color_bar_pos == 'top right' else [0.05, 0.08]
        self.color_bar.Title = (
            color_bar_title or
            f'Quality - Quad: {self.measure_quad} - Tri: {self.measure_triangle}'
        )
        self.color_bar.ScalarBarThickness = 36
        self.color_bar.TitleFontSize = 36
        self.color_bar.LabelFontSize = 36

        # Apply a preset using its name
        quality_LUT.ApplyPreset(color_bar_preset or self.color_bar_preset, True)

        # Rescale transfer function
        # quality_LUT.RescaleTransferFunction(0.364, 4.059)
        # qualityPWF.RescaleTransferFunction(0.364, 4.059)

        if log_scale:
            quality_LUT.MapControlPointsToLogSpace()  # convert to log space
            quality_LUT.UseLogScale = 1
        else:
            quality_LUT.MapControlPointsToLinearSpace()  # convert from log to linear
            quality_LUT.UseLogScale = 0

        if invert_colors:
            # invert the transfer function
            quality_LUT.InvertTransferFunction()

        self._print()

        Hide(mesh_quality, self.view)
        # Hide the scalar bar for this color map if no visible data is colored by it
        HideScalarBarIfNotNeeded(self.color_bar, self.view)

        if invert_colors:
            # Re-invert the transfer function
            quality_LUT.InvertTransferFunction()

    def _setup_mesh_quality(self, **measure):
        """ Sets up the mesh quality data source in ParaView

        Parameters
        ----------
        measure : dict
            if contains 'quad': overrides `self.measure_quad`
            if contains 'triangle': overrides `self.measure_triangle`

        """

        quality_src = MeshQuality(self.data, registrationName=self.strs.quality)
        if measure:
            self.measure_quad = measure.get('quad', self.measure_quad)
            self.measure_triangle = measure.get('tri', self.measure_triangle)
            self.measure_triangle = measure.get('triangle', self.measure_triangle)
        quality_src.QuadQualityMeasure = self.measure_quad
        quality_src.TriangleQualityMeasure = self.measure_triangle

        return quality_src

    def get_quality(self, **measure_kwds):
        """ Gets the quality of the mesh cells, defined by `measure`

        Parameters
        ----------
        measure_kwds
            if contains `quad`: overrides `self.measure_quad`
            if contains `triangle`: overrides `self.measure_triangle`

        Returns
        -------
        quality_array : np.ndarray
            1D array containing the quality of mesh cells
        """

        # create a new 'Mesh Quality' data source
        mesh_quality = self._setup_mesh_quality(**measure_kwds)

        vtk_data = WrapDataObject(Fetch(mesh_quality))

        quality_array = vtk_data.GetCellData().GetArray('Quality').Arrays[0]

        # data = vtk_data.PointData[0]
        # vtk_data.Points.Arrays[0]
        # vtk_data.GetFieldData().GetArray('Mesh Quadrilateral Quality')[0].Arrays[0]

        # # Save to .csv file
        # from paraview.simple import SaveData
        # SaveData(
        #     join(dirname(self.mesh_flow_src), 'mesh_data.csv'),
        #     proxy=quality,
        #     PointDataArrays=['Pressure'],
        #     CellDataArrays=['Quality'],
        #     FieldDataArrays=
        #     [
        #         'Mesh Hexahedron Quality',
        #         'Mesh Quadrilateral Quality',
        #         'Mesh Tetrahedron Quality',
        #         'Mesh Triangle Quality'
        #     ],
        #     FieldAssociation='Cell Data'
        # )

        return quality_array

    def print_quality_distribution(
            self,
            qoi_array=None,
            title=None,
            n_bins=50,
            size=(9, 6),
            fmt='pdf',
            filename=None,
            out_dir=None,
            plot_counts=False,
            plot_gaussian=False,
            **quality_kwds
    ):

        if qoi_array is None:
            qoi_array = self.get_quality(**quality_kwds)

        # matplotlib histogram
        plt.figure(figsize=size)
        counts, bins, patches = plt.hist(  # noqa
            qoi_array,
            color='blue',
            edgecolor='black',
            bins=n_bins,
            log=True
        )
        plt.title(title or f'Mesh quality quads: {self.measure_quad}')
        plt.xlabel('value [-]')
        plt.ylabel('count [-]')
        plt.tight_layout(pad=0.5)

        # Maybe plot count numbers above the bars
        if plot_counts:
            offset = 1/15  # of figure size
            ax = plt.gca()
            bin_w = bins[1] - bins[0]
            for count, p in zip(counts, patches):
                ax.annotate(
                    str(int(count)),
                    xy=(p.get_x() + bin_w * offset, p.get_height() * (1+offset)),
                    rotation=75
                )

        # Maybe plot gaussian
        if plot_gaussian:
            from scipy.stats import gaussian_kde
            xs = np.linspace(*plt.xlim(), 200)
            density = gaussian_kde(qoi_array)
            density.covariance_factor = lambda: .25
            density._compute_covariance()  # noqa
            plt.plot(xs, density(xs))

        # Determine plot filename
        if filename is not None:
            if '.' in filename:
                fmt = filename.rsplit('.', 1)[-1]
            else:
                filename += f'.{fmt}'
        else:
            filename = f"{self.print_filenames.distribution}_{self.measure_quad}.{fmt}"

        makedirs(self._out_dir(out_dir), exist_ok=True)
        filename = self._make_abs_path(filename, out_dir)

        plt.savefig(filename, bbox_inches="tight", format=fmt, dpi=2000)

    def _print(self):
        """ Prints the mesh figure to disk

        Automatically sets the output image size using the image resolution in pixels

        """

        # update the view to ensure updated data information
        self.view.Update()

        # Ensure white background
        LoadPalette('WhiteBackground')

        # Hide OrientationAxesVisibility
        self.view.OrientationAxesVisibility = 0

        # Set view size in pixels
        GetLayout().SetSize(*self._image_resolution)

        # Reset view to fit data
        self.view.ResetCamera(True)
        GetActiveCamera().Zoom(1.1)

        makedirs(dirname(self.print_filename), exist_ok=True)

        # Save print
        if self.filetype in ['pdf', 'eps', 'ps', 'svg']:
            # Exported image is always rasterized rather than vectorized
            with IgnoreOutput():
                ExportView(
                    self.print_filename,
                    view=self.view,
                    Plottitle='ParaBladeParaViewPrint',
                    # Drawbackground=0,
                    # Linewidthscalingfactor=0.25,
                    # Pointsizescalingfactor=0.25,
                    GL2PSdepthsortmethod='No sorting (fastest, poor)',
                    Compressoutputfile=1,
                    Rasterize3Dgeometry=0,
                    Dontrasterizecubeaxes=1,
                    Rendertextaspaths=1
                )

        else:
            SaveScreenshot(
                self.print_filename,
                self.view,
                ImageResolution=self._image_resolution,
                # TransparentBackground=1,
                CompressionLevel='9'
            )

        print(f'.. Printed {basename(self.print_filename)}')

    def _set_print_filename(self, file_out, out_dir=None):
        file_out = self._make_abs_path(file_out, out_dir)
        self.print_filename = f"{file_out}.{self.filetype}"

    def _make_abs_path(self, filename_out, out_dir=None):
        """
        Parameters
        ----------
        filename_out : str
            Name of the output print file. Without file type extension.
                If not a full path, the same folder as input `flow.dat` is assumed

        out_dir : str
            Optional; If given, and `file_out` is not a full path, `out_dir` is used as
                        save folder.
                      else: the same folder as input `flow.dat` is assumed

        Returns
        -------
        filename_out : str
            Absolute path of output file
        """

        if not isabs(filename_out):
            return join(self._out_dir(out_dir), filename_out)

        return filename_out

    def _out_dir(self, out_dir=None):
        return abspath(out_dir or self.out_dir or dirname(self.mesh_flow_src))

    @property
    def _image_resolution(self):
        bds = self.data.GetDataInformation().GetBounds()
        w_frac, h_frac = (bds[1] - bds[0]), (bds[3] - bds[2])
        pixel_factor = np.sqrt(self.n_pixels / (w_frac*h_frac))
        return int(w_frac * pixel_factor), int(h_frac * pixel_factor)

    def __exit__(self, *_):
        Disconnect()
        collect()


class IgnoreOutput:
    """ Captures stdout or stderr from called c programs.

    Used to capture ParaView console errors when printing .pdf's
    """

    def __init__(self, id_n=2):
        self.id_n = id_n  # 1:stdout, 2:stderr

        self._devnull = osopen(devnull, O_WRONLY)
        self._newstderr = dup(self.id_n)

    def __enter__(self):
        dup2(self._devnull, self.id_n)
        close(self._devnull)

    def __exit__(self, *_):
        dup2(self._newstderr, self.id_n)


if __name__ == '__main__':

    with ParaViewDriver('flow.dat', out_filetype='png') as pv_driver:
        pv_driver.print_mesh_wireframe()
        pv_driver.print_quality(quad='Edge Ratio')
        # quality = pv_driver.get_quality()
        pv_driver.print_quality_distribution()
