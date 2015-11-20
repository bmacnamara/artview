"""
plot_points.py

Class instance used to plot information over a set of points.
"""
# Load the needed packages
import numpy as np
import os
import pyart

from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as \
    NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.colors import Normalize as mlabNormalize
from matplotlib.colorbar import ColorbarBase as mlabColorbarBase
from matplotlib.pyplot import cm

from ..core import Variable, Component, common, VariableChoose, QtGui, QtCore

# Save image file type and DPI (resolution)
IMAGE_EXT = 'png'
DPI = 200
# ========================================================================


class PointsDisplay(Component):
    '''
    Class to create a display plot, using data and a key for plot type.
    '''

    Vpoints = None  #: see :ref:`shared_variable`
    Vfield = None  #: see :ref:`shared_variable`
    Vlims = None  #: see :ref:`shared_variable`
    Vcmap = None  #: see :ref:`shared_variable`

    @classmethod
    def guiStart(self, parent=None):
        '''Graphical interface for starting this class'''
        kwargs, independent = \
            common._SimplePluginStart("PointsDisplay").startDisplay()
        kwargs['parent'] = parent
        return self(**kwargs), independent

    def __init__(self, Vpoints=None, Vfield=None, Vlims=None, Vcmap=None,
                 plot_type="hist", name="PointsDisplay", parent=None):
        '''
        Initialize the class to create display.

        Parameters
        ----------
        [Optional]
        Vpoints : :py:class:`~artview.core.core.Variable` instance
            Points signal variable. If None start new one with None.
        Vfield : :py:class:`~artview.core.core.Variable` instance
            Field signal variable. If None start new one with empty string.
        Vlims : :py:class:`~artview.core.core.Variable` instance
            Limits signal variable.
            A value of None will instantiate a limits variable.
        Vcmap : :py:class:`~artview.core.core.Variable` instance
            Colormap signal variable.
            A value of None will instantiate a colormap variable.
        plot_type : str
            Type of plot to produce (e.g. plot, barplot, etc).
        name : string
            Display window name.
        parent : PyQt instance
            Parent instance to associate to Display window.
            If None, then Qt owns, otherwise associated with parent PyQt
            instance.

        Notes
        -----
        This class records the selected button and passes the
        change value back to variable.
        '''
        super(PointsDisplay, self).__init__(name=name, parent=parent)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        if Vpoints is None:
            self.Vpoints = Variable(None)
        else:
            self.Vpoints = Vpoints

        if Vfield is None:
            self.Vfield = Variable('')
        else:
            self.Vfield = Vfield

        if Vlims is None:
            self.Vlims = Variable({})
        else:
            self.Vlims = Vlims

        if Vcmap is None:
            self.Vcmap = Variable(None)
        else:
            self.Vcmap = Vcmap

        self.sharedVariables = {"Vpoints": self.NewPoints,
                                "Vfield": self.NewField,
                                "Vlims": self.NewLims,
                                "Vcmap": self.NewCmap,
                                }

        # Connect the components
        self.connectAllVariables()

        self.plot_type = plot_type

        # Set plot title and colorbar units to defaults
        self.title = self._get_default_title()
        self.units = self._get_default_units()

        # Find the PyArt colormap names
        self.cm_names = ["pyart_" + m for m in pyart.graph.cm.datad
                         if not m.endswith("_r")]
        self.cm_names.sort()

        # Create a figure for output
        self._set_fig_ax()

        # Launch the GUI interface
        self.LaunchGUI()

        # Set up Default limits and cmap
#        if Vlims is None:
#            self._set_default_limits(strong=False)
#        if Vcmap is None:
#            self._set_default_cmap(strong=False)

        # Create the plot
        self._update_plot()
#        self.NewRadar(None, None, True)

        self.show()

    ####################
    # GUI methods #
    ####################

    def LaunchGUI(self):
        '''Launches a GUI interface.'''
        # Create layout
        self.layout = QtGui.QGridLayout()
        self.layout.setSpacing(4)

        # Create the widget
        self.central_widget = QtGui.QWidget()
        self.setCentralWidget(self.central_widget)
        self._set_figure_canvas()

        self.central_widget.setLayout(self.layout)

        # Add buttons along display for user control
        self.addButtons()
        self.setUILayout()

        # Set the status bar to display messages
        self.statusbar = self.statusBar()

    ##################################
    # User display interface methods #
    ##################################
    def addButtons(self):
        '''Add a series of buttons for user control over display.'''
        # Create the Display controls
        self._add_displayBoxUI()

    def setUILayout(self):
        '''Setup the button/display UI layout.'''
        self.layout.addWidget(self.dispButton, 0, 1)

    #############################
    # Functionality methods #
    #############################

    def _open_LimsDialog(self):
        '''Open a dialog box to change display limits.'''
        from .limits import limits_dialog
        limits, cmap, change = limits_dialog(
            self.Vlims.value, self.Vcmap.value, self.name)
        if change == 1:
            self.Vcmap.change(cmap)
            self.Vlims.change(limits)

    def _title_input(self):
        '''Retrieve new plot title.'''
        val, entry = common.string_dialog_with_reset(
            self.title, "Plot Title", "Title:", self._get_default_title())
        if entry is True:
            self.title = val
            self._update_plot()

    def _units_input(self):
        '''Retrieve new plot units.'''
        val, entry = common.string_dialog_with_reset(
            self.units, "Plot Units", "Units:", self._get_default_units())
        if entry is True:
            self.units = val
            self._update_plot()

    def _add_cmaps_to_button(self):
        '''Add a menu to change colormap used for plot.'''
        for cm_name in self.cm_names:
            cmapAction = self.dispCmapmenu.addAction(cm_name)
            cmapAction.setStatusTip("Use the %s colormap" % cm_name)
            cmapAction.triggered[()].connect(
                lambda cm_name=cm_name: self.cmapSelectCmd(cm_name))
            self.dispCmap.setMenu(self.dispCmapmenu)

    def _add_displayBoxUI(self):
        '''Create the Display Options Button menu.'''
        self.dispButton = QtGui.QPushButton("Display Options")
        self.dispButton.setToolTip("Adjust display properties")
        self.dispButton.setFocusPolicy(QtCore.Qt.NoFocus)
        dispmenu = QtGui.QMenu(self)
        dispLimits = dispmenu.addAction("Adjust Display Limits")
        dispLimits.setToolTip("Set data, X, and Y range limits")
        dispTitle = dispmenu.addAction("Change Title")
        dispTitle.setToolTip("Change plot title")
        dispUnit = dispmenu.addAction("Change Units")
        dispUnit.setToolTip("Change units string")
#        toolZoomPan = dispmenu.addAction("Zoom/Pan")
        self.dispCmap = dispmenu.addAction("Change Colormap")
        self.dispCmapmenu = QtGui.QMenu("Change Cmap")
        self.dispCmapmenu.setFocusPolicy(QtCore.Qt.NoFocus)
        dispSaveFile = dispmenu.addAction("Save Image")
        dispSaveFile.setShortcut("Ctrl+S")
        dispSaveFile.setStatusTip("Save Image using dialog")
        self.dispHelp = dispmenu.addAction("Help")

        dispLimits.triggered[()].connect(self._open_LimsDialog)
        dispTitle.triggered[()].connect(self._title_input)
        dispUnit.triggered[()].connect(self._units_input)
#        toolZoomPan.triggered[()].connect(self.toolZoomPanCmd)
        dispSaveFile.triggered[()].connect(self._savefile)
        self.dispHelp.triggered[()].connect(self.displayHelp)

        self._add_cmaps_to_button()
        self.dispButton.setMenu(dispmenu)

    def displayHelp(self):
        text = (
            "<b>Using the Simple Plot Feature</b><br><br>"
            "<i>Purpose</i>:<br>"
            "Display a plot.<br><br>"
            "The limits dialog is a common format that allows the user "
            "change:<br>"
            "<i>X and Y limits<br>"
            "Data limits</i><br>"
            "However, not all plots take each argument.<br>"
            "For example, a simple line plot has no data min/max data "
            "value.<br>")

        common.ShowLongText(text)

    def NewPoints(self, variable, value, strong):
        '''
        Slot for 'ValueChanged' signal of
        :py:class:`Vradar <artview.core.core.Variable>`.

        This will:

        * Update fields and tilts lists and MenuBoxes
        * Check radar scan type and reset limits if needed
        * Reset units and title
        * If strong update: update plot
        '''
        # test for None
        if self.Vpoints.value is None:
#            self.fieldBox.clear()
            return

        # Get field names
        self.fieldnames = self.Vpoints.value.fields.keys()

#        self._fillFieldBox()

        self.units = self._get_default_units()
        self.title = self._get_default_title()
        if strong:
            self._update_plot()
#            self._update_infolabel()

    def NewField(self, variable, value, strong):
        '''
        Slot for 'ValueChanged' signal of
        :py:class:`Vfield <artview.core.core.Variable>`.

        This will:

        * Reset colormap
        * Reset units
        * Update fields MenuBox
        * If strong update: update plot
        '''
        self._set_default_cmap(strong=False)
        self.units = self._get_default_units()
        self.title = self._get_default_title()
#        idx = self.fieldBox.findText(value)
#        self.fieldBox.setCurrentIndex(idx)
        if strong:
            self._update_plot()
            self._update_infolabel()

    def NewLims(self, variable, value, strong):
        '''
        Slot for 'ValueChanged' signal of
        :py:class:`Vlims <artview.core.core.Variable>`.

        This will:

        * If strong update: update axes
        '''
        if strong:
            self._update_axes()

    def NewCmap(self, variable, value, strong):
        '''
        Slot for 'ValueChanged' signal of
        :py:class:`Vcmap <artview.core.core.Variable>`.

        This will:

        * If strong update: update plot
        '''
        if strong:
            self._update_plot()

    ########################
    # Selectionion methods #
    ########################



#     def _create_plot(self):
#         '''
#         Create a plot
#         '''
#         # test for None
#         if self.Vradar.value is None:
#             self.fieldBox.clear()
#             self.tiltBox.clear()
#             return
#
#         # Get the tilt angles
#         self.rTilts = self.Vradar.value.sweep_number['data'][:]
#         # Get field names
#         self.fieldnames = self.Vradar.value.fields.keys()
#
#         # Check the file type and initialize limts
#         self._check_file_type()
#
#         # Update field and tilt MenuBox
#         self._fillTiltBox()
#         self._fillFieldBox()
#
#         self.units = None
#         if strong:
#             self._update_plot()

#     def NewLims(self, variable, value, strong):
#         '''
#         Slot for 'ValueChanged' signal of
#         :py:class:`Vlims <artview.core.core.Variable>`.
#
#         This will:
#
#         * If strong update: update axes
#         '''
#         if strong:
#             self._update_axes()

#     def NewCmap(self, variable, value, strong):
#         '''
#         Slot for 'ValueChanged' signal of
#         :py:class:`Vcmap <artview.core.core.Variable>`.
#
#         This will:
#
#         * If strong update: update plot
#         '''
#         if strong and self.Vradar.value is not None:
#             self._update_plot()

    def cmapSelectCmd(self, cm_name):
        '''Captures colormap selection and redraws.'''
        self.Vcmap.value['cmap'] = cm_name
        self.Vcmap.update()

#    def toolZoomPanCmd(self):
#        '''Creates and connects to a Zoom/Pan instance.'''
#        from .tools import ZoomPan
#        scale = 1.1
#        self.tools['zoompan'] = ZoomPan(
#            self.limits, self.ax,
#            base_scale=scale, parent=self.parent)
#        self.tools['zoompan'].connect()

    ####################
    # Plotting methods #
    ####################

    def _set_fig_ax(self):
        '''Set the figure and axis to plot.'''
        self.XSIZE = 5
        self.YSIZE = 5
        self.fig = Figure(figsize=(self.XSIZE, self.YSIZE))
        self.ax = self.fig.add_axes([0.2, 0.2, 0.7, 0.7])

#    def _update_fig_ax(self):
#        '''Set the figure and axis to plot.'''
#        if self.plot_type in ("radarAirborne", "radarRhi"):
#            self.YSIZE = 5
#        else:
#            self.YSIZE = 8
#        xwidth = 0.7
#        yheight = 0.7 * float(self.YSIZE) / float(self.XSIZE)
#        self.ax.set_position([0.2, 0.55-0.5*yheight, xwidth, yheight])
#        self.cax.set_position([0.2, 0.10, xwidth, 0.02])
#        self._update_axes()

    def _set_figure_canvas(self):
        '''Set the figure canvas to draw in window area.'''
        self.canvas = FigureCanvasQTAgg(self.fig)
        # Add the widget to the canvas
        self.layout.addWidget(self.canvas, 1, 0, 4, 3)

    def _update_plot(self):
        '''Draw/Redraw the plot.'''

        if self.Vpoints.value is None:
            return

        # Create the plot with PyArt PlotDisplay
        self.ax.cla()  # Clear the plot axes

        # Reset to default title if user entered nothing w/ Title button

        colorbar_flag = False

        points = self.Vpoints.value
        field = self.Vfield.value
        cmap = self.Vcmap.value

        if field not in points.fields.keys():
            self.canvas.draw()
            self.statusbar.setStyleSheet("QStatusBar{padding-left:8px;" +
                                         "background:rgba(255,0,0,255);" +
                                         "color:black;font-weight:bold;}")
            self.statusbar.showMessage("Field not Found in Radar", msecs=5000)
            return
        else:
            self.statusbar.setStyleSheet("QStatusBar{padding-left:8px;" +
                                         "background:rgba(0,0,0,0);" +
                                         "color:black;font-weight:bold;}")
            self.statusbar.clearMessage()

        if self.plot_type == "hist":
            self.plot = self.ax.hist(
                points.fields[field]['data'], bins=25,
                range=(cmap['vmin'], cmap['vmax']),
                figure=self.fig)
            self.ax.set_ylabel("Counts")

        # If limits exists, update the axes otherwise retrieve
        #self._update_axes()

        # If the colorbar flag is thrown, create it
        if colorbar_flag:
            # Clear the colorbar axes
            self.cax.cla()
            self.cax = self.fig.add_axes([0.2, 0.10, 0.7, 0.02])
            norm = mlabNormalize(vmin=cmap['vmin'],
                                 vmax=cmap['vmax'])
            self.cbar = mlabColorbarBase(self.cax, cmap=self.cm_name,
                                         norm=norm, orientation='horizontal')
            # colorbar - use specified units or default depending on
            # what has or has not been entered
            self.cbar.set_label(self.units)

        self.canvas.draw()

    def _update_axes(self):
        '''Change the Plot Axes.'''
        limits = self.Vlims.value
        lim = self.ax.get_xlim()
        limits['xmin'] = lim[0]
        limits['xmax'] = lim[1]
        lim = self.ax.get_ylim()
        limits['ymin'] = lim[0]
        limits['ymax'] = lim[1]
        return
        self.ax.set_xlim(limits['xmin'], limits['xmax'])
        self.ax.set_ylim(limits['ymin'], limits['ymax'])
        self.ax.figure.canvas.draw()

    def _set_default_cmap(self, strong=True):
        ''' Set colormap to pre-defined default.'''
        cmap = pyart.config.get_field_colormap(self.Vfield.value)
        d = {}
        d['cmap'] = cmap
        lims = pyart.config.get_field_limits(self.Vfield.value,
                                             self.Vpoints.value)
        if lims != (None, None):
            d['vmin'] = lims[0]
            d['vmax'] = lims[1]
        else:
            d['vmin'] = -10
            d['vmax'] = 65

    def _get_default_title(self):
        '''Get default title from pyart.'''
        if (self.Vpoints.value is None or
            self.Vfield.value not in self.Vpoints.value.fields):
            return ''
        return "Pyart Title" #pyart.graph.common.generate_title(self.Vpoints.value,
              #                                   self.Vfield.value,
              #                                   0)

    def _get_default_units(self):
        '''Get default units for current radar and field.'''
        if self.Vpoints.value is not None:
            try:
                return self.Vpoints.value.fields[self.Vfield.value]['units']
            except:
                return ''
        else:
            return ''

    ########################
    # Image save methods #
    ########################

    def _savefile(self, PTYPE=IMAGE_EXT):
        '''Save the current display using PyQt dialog interface.'''
        file_choices = "PNG (*.png)|*.png"
        path = unicode(QtGui.QFileDialog.getSaveFileName(
            self, 'Save file', ' ', file_choices))
        if path:
            self.canvas.print_figure(path, dpi=DPI)
            self.statusbar.showMessage('Saved to %s' % path)
