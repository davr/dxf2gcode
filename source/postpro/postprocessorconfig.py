# -*- coding: utf-8 -*-

############################################################################
#
#   Copyright (C) 2008-2016
#    Christian Kohlöffel
#    Vinzenz Schulz
#    Jean-Paul Schouwstra
#    Xavier Izard
#
#   This file is part of DXF2GCODE.
#
#   DXF2GCODE is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   DXF2GCODE is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with DXF2GCODE.  If not, see <http://www.gnu.org/licenses/>.
#
############################################################################

import os

from globals.configobj.configobj import ConfigObj, flatten_errors
from globals.configobj.validate import Validator

import globals.globals as g
from globals.d2gexceptions import *
from gui.configwindow import *

from globals.six import text_type
import globals.constants as c
if c.PYQT5notPYQT4:
    from PyQt5 import QtCore
else:
    from PyQt4 import QtCore

import logging
logger = logging.getLogger("PostPro.PostProcessorConfig")

POSTPRO_VERSION = "6"
"""
version tag - increment this each time you edit CONFIG_SPEC

compared to version number in config file so
old versions are recognized and skipped
"""

POSTPRO_SPEC = str('''
#  Section and variable names must be valid Python identifiers
#      do not use whitespace in names

# do not edit the following section name:
    [Version]
    # do not edit the following value:
    config_version = string(default="'''  +
    str(POSTPRO_VERSION) + '")\n' +
    '''
    [General]
    # This extension is used in the save file export dialog.
    output_format = string(default=".ngc")
    # This title is shown in the export dialog and is used by the user to differentiate between the possibly different postprocessor configurations.
    output_text = string(default="G-CODE for LinuxCNC")
    # This type defines the output format used in the export dialog.
    output_type = option('g-code', 'dxf', 'text', default = 'g-code')

    # This may be used for G90 or G91 code which switches between absolute and relative coordinates.
    abs_export = boolean(default=True)
    # If the cutter compensation is used e.g. G41 or G42 this option may cancel the compensation while the depth (Z-Axis) is used and enable the compensation again after the depth is reached.
    cancel_cc_for_depth = boolean(default=False)
    # If the cutter compensation is used this will enable (G41-G42) / cancel (G40) the cutter compensation after the tool is outside of the piece.
    cc_outside_the_piece = boolean(default=True)
    # This may be used for the export to dxf which only accepts arcs which are in counterclockwise direction. Turning this on for normal G-Code will cause in unintended outputs.
    export_ccw_arcs_only = boolean(default=False)
    # This values indicated which arc's with radius higher than this value will be exported as a line. 
    max_arc_radius = float(min = 0, default=10000)

    code_begin_units_mm = string(default="G21 (Units in millimeters)")
    code_begin_units_in = string(default="G20 (Units in inches)")
    code_begin_prog_abs = string(default="G90 (Absolute programming)")
    code_begin_prog_inc = string(default="G91 (Incremental programming)")
    # This is code which will be written at the beginning of the exported file. 
    code_begin = string(default="G64 (Default cutting) G17 (XY plane) G40 (Cancel radius comp.) G49 (Cancel length comp.)")
    # This is code which will be written at the end of the exported file. 
    code_end = string(default="M2 (Program end)")

    [Number_Format]
    # Gives the indentation for the values.
    pre_decimals = integer(min = 0, default=4)
    # Gives the accuracy of the output after which it will be rounded.
    post_decimals = integer(min = 0, default=3)
    # Give the separator which is used in the exported values (e.g. '.' or ',').
    decimal_separator = string(default=".")
    # If true all values will be padded with zeros up to pre_decimals (e.g. 0001.000).
    pre_decimal_zero_padding = boolean(default=False)
    # If false e.g. 1.000 will be given as 1 only.
    post_decimal_zero_padding = boolean(default=True)
    # If True 1.000 will be written as +1.000 
    signed_values = boolean(default=False)

    [Line_Numbers]
    # Enables lines numbers into the exported G-Code file.
    use_line_nrs = boolean(default=False)
    line_nrs_begin = integer(default=10)
    line_nrs_step = integer(default=10)

    [Program]
    # This will be done after each layer, if different tools are used.
    tool_change = string(default=T%tool_nr M6%nlS%speed%nl)
    # This will be done after each change between cutting in plane or cutting in depth.
    feed_change = string(default=F%feed%nl)
    # This will be done between each shape to cut.
    rap_pos_plane = string(default=G0 X%XE Y%YE%nl)
    # This will be done between each shape to cut.
    rap_pos_depth = string(default=G0 Z%ZE %nl)
    # This will be used for shape cutting.
    lin_mov_plane = string(default= G1 X%XE Y%YE%nl)
    # This will be used for shape cutting.
    lin_mov_depth = string(default= G1 Z%ZE%nl)
    # This will be used for shape cutting.
    arc_int_cw = string(default=G2 X%XE Y%YE I%I J%J%nl)
    # This will be used for shape cutting.
    arc_int_ccw = string(default=G3 X%XE Y%YE I%I J%J%nl)
    # Generally set to G40%nl
    cutter_comp_off = string(default=G40%nl)
    # Generally set to G41%nl
    cutter_comp_left = string(default=G41%nl)
    # Generally set to G42%nl
    cutter_comp_right = string(default=G42%nl)
    # This will be done before starting to cut a shape or a contour.
    pre_shape_cut = string(default=M3 M8%nl)
    # This will be done after cutting a shape or a contour.
    post_shape_cut = string(default=M9 M5%nl)
    # Defines comments' format. Comments are written at some places during the export in order to make the g-code better readable.
    comment = string(default=%nl(%comment)%nl)

''').splitlines()
""" format, type and default value specification of the global config file"""


class MyPostProConfig(object):
    """
    This class hosts all functions related to the PostProConfig File.
    """
    def __init__(self, filename='postpro_config' + c.CONFIG_EXTENSION):
        """
        initialize the varspace of an existing plugin instance
        init_varspace() is a superclass method of plugin
        @param filename: The filename for the creation of a new config
        file and the filename of the file to read config from.
        """
        self.folder = os.path.join(g.folder, c.DEFAULT_POSTPRO_DIR)
        self.filename = os.path.join(self.folder, filename)

        self.version_mismatch = '' # no problem for now
        self.default_config = False  # whether a new name was generated
        self.var_dict = dict()
        self.spec = ConfigObj(POSTPRO_SPEC, interpolation=False, list_values=False, _inspec=True)

    def load_config(self):
        """
        This method tries to load the defined postprocessor file given in
        self.filename. If this fails it will create a new one
        """

        try:
            # file exists, read & validate it
            self.var_dict = ConfigObj(self.filename, configspec=POSTPRO_SPEC)
            _vdt = Validator()
            result = self.var_dict.validate(_vdt, preserve_errors=True)
            validate_errors = flatten_errors(self.var_dict, result)

            if validate_errors:
                logger.error(tr("errors reading %s:") % self.filename)
            for entry in validate_errors:
                section_list, key, error = entry
                if key is not None:
                    section_list.append(key)
                else:
                    section_list.append('[missing section]')
                section_string = ', '.join(section_list)
                if error == False:
                    error = tr('Missing value or section.')
                logger.error(section_string + ' = ' + error)

            if validate_errors:
                raise BadConfigFileError(tr("syntax errors in postpro_config file"))

            # check config file version against internal version

            if POSTPRO_VERSION:
                fileversion = self.var_dict['Version']['config_version'] # this could raise KeyError

                if fileversion != POSTPRO_VERSION:
                    raise VersionMismatchError(fileversion, POSTPRO_VERSION)

        except VersionMismatchError:
            # version mismatch flag, it will be used to display an error.
            self.version_mismatch = tr("The postprocessor configuration file version ({0}) doesn't match the software expected version ({1}).\n\nYou have to delete (or carefully edit) the configuration file \"{2}\" to solve the problem.").format(fileversion, POSTPRO_VERSION, self.filename)

        except Exception as inst:
            #logger.error(inst)
            (base, ext) = os.path.splitext(self.filename)
            badfilename = base + c.BAD_CONFIG_EXTENSION
            logger.debug(tr("trying to rename bad cfg %s to %s") % (self.filename, badfilename))
            try:
                os.rename(self.filename, badfilename)
            except OSError as e:
                logger.error(tr("rename(%s,%s) failed: %s") % (self.filename, badfilename, e.strerror))
                raise
            else:
                logger.debug(tr("renamed bad varspace %s to '%s'") % (self.filename, badfilename))
                self.create_default_config()
                self.default_config = True
                logger.debug(tr("created default varspace '%s'") % self.filename)
        else:
            self.default_config = False
            logger.debug(tr("read existing varspace '%s'") % self.filename)

        # convenience - flatten nested config dict to access it via self.config.sectionname.varname
        self.var_dict.main.interpolation = False  # avoid ConfigObj getting too clever
        self.update_config()


    def update_config(self):
        """
        Call this function each time the self.var_dict is updated (eg when the postprocessor configuration window changes some settings)
        """
        # convenience - flatten nested config dict to access it via self.config.sectionname.varname
        self.vars = DictDotLookup(self.var_dict)
        # add here any update needed for the internal variables of this class
        

    def make_settings_folder(self):
        """
        This method creates the postprocessor settings folder if necessary
        """
        try:
            os.mkdir(self.folder)
        except OSError:
            pass

    def create_default_config(self):
        """
        If no postprocessor config file exists this function is called
        to generate the config file based on its specification.
        """
        # check for existing setting folder or create one
        self.make_settings_folder()

        # derive config file with defaults from spec
        logger.debug(POSTPRO_SPEC)

        self.var_dict = ConfigObj(configspec=POSTPRO_SPEC)
        _vdt = Validator()
        self.var_dict.validate(_vdt, copy=True)
        self.var_dict.filename = self.filename
        self.var_dict.write()


    def save_varspace(self):
        self.var_dict.filename = self.filename
        self.var_dict.write()


    def print_vars(self):
        """
        Print all the variables with their values
        """
        print("Variables:")
        for k, v in self.var_dict['Variables'].items():
            print(k, "=", v)


def tr(string_to_translate):
    """
    Translate a string using the QCoreApplication translation framework
    @param string_to_translate: a unicode string
    @return: the translated unicode string if it was possible to translate
    """
    return text_type(QtCore.QCoreApplication.translate('MyPostProConfig', string_to_translate))


def makeConfigWidgets():
    """
    Build the postprocessor configuration widgets and store them into a dictionary.
    The structure of the dictionnary must match the structure of the postprocessor configuration file. The names of the keys must be identical to those used in the configfile.
    If a name is declared in the configfile but not here, it simply won't appear in the config window (the config_version for example must not be modified by the user, so it is not declared here)
    """
    cfg_widget_def = \
    {
        'General':
        {
            '__section_title__': tr("Software config"),
            'output_format': CfgLineEdit(tr('Output file extension:')),
            'output_text': CfgLineEdit(tr('Output format description:')),
            'output_type': CfgComboBox(tr('Output type:')),
            'abs_export': CfgCheckBox(tr('Export absolute coordinates')),
            'cancel_cc_for_depth': CfgCheckBox(tr('Cancel cutter compensation at each slice')),
            'cc_outside_the_piece': CfgCheckBox(tr('Perform cutter compensation outside of the piece')),
            'export_ccw_arcs_only': CfgCheckBox(tr('Export only counter clockwise arcs')),
            'max_arc_radius': CfgDoubleSpinBox(tr('Maximum arc radius:')),
            'code_begin_units_mm': CfgLineEdit(tr('Units in millimeters G-code:')),
            'code_begin_units_in': CfgLineEdit(tr('Units in inch G-code:')),
            'code_begin_prog_abs': CfgLineEdit(tr('Absolute programming G-code:')),
            'code_begin_prog_inc': CfgLineEdit(tr('Incremental programming G-code:')),
            'code_begin': CfgTextEdit(tr('Startup G-code:')),
            'code_end': CfgTextEdit(tr('End G-code:')),
        },
        'Number_Format':
        {
            '__section_title__': tr("Output formatting"),
            'pre_decimals': CfgSpinBox(tr('Number of digit before the decimal separator:')),
            'post_decimals': CfgSpinBox(tr('Number of digit after the decimal separator:')),
            'pre_decimal_zero_padding': CfgCheckBox(tr("Pad with '0' digit berfore the decimal separator")),
            'post_decimal_zero_padding': CfgCheckBox(tr("Pad with '0' digit after the decimal separator")),
            'decimal_separator': CfgLineEdit(tr('Decimal separator:')),
            'signed_values': CfgCheckBox(tr("Prepend the numbers with the '+' sign for positive values")),
        },
        'Line_Numbers':
        {
            '__section_title__': tr("Output formatting"),
            'use_line_nrs': CfgCheckBox(tr('Export lines numbers')),
            'line_nrs_begin': CfgSpinBox(tr('Line number starts at:')),
            'line_nrs_step': CfgSpinBox(tr('Line number step:')),
        },
        'Program':
        {
            '__section_title__': tr("G-code codes"),
            'tool_change': CfgLineEdit(tr('Tool change:')),
            'feed_change': CfgLineEdit(tr('Feed rate change:')),
            'rap_pos_plane': CfgLineEdit(tr('Rapid positioning for XY plane:')),
            'rap_pos_depth': CfgLineEdit(tr('Rapid positioning for Z plane:')),
            'lin_mov_plane': CfgLineEdit(tr('Linear feed move for XY plane:')),
            'lin_mov_depth': CfgLineEdit(tr('Linear feed move for Z plane:')),
            'arc_int_cw': CfgLineEdit(tr('Clockwise feed move:')),
            'arc_int_ccw': CfgLineEdit(tr('Counter clockwise feed move:')),
            'cutter_comp_off': CfgLineEdit(tr('Disable cutter compensation:')),
            'cutter_comp_left': CfgLineEdit(tr('Left cutter compensation:')),
            'cutter_comp_right': CfgLineEdit(tr('Right cutter compensation:')),
            'pre_shape_cut': CfgLineEdit(tr('G-code placed before any shape cutting:')),
            'post_shape_cut': CfgLineEdit(tr('G-code placed after any shape cutting:')),
            'comment': CfgLineEdit(tr('Comment for the current shape:')),
        },
    }
    
    return cfg_widget_def
    

class DictDotLookup(object):
    """
    Creates objects that behave much like a dictionaries, but allow nested
    key access using object '.' (dot) lookups.
    """
    def __init__(self, d):
        for k in d:
            if isinstance(d[k], dict):
                self.__dict__[k] = DictDotLookup(d[k])
            elif isinstance(d[k], (list, tuple)):
                l = []
                for v in d[k]:
                    if isinstance(v, dict):
                        l.append(DictDotLookup(v))
                    else:
                        l.append(v)
                self.__dict__[k] = l
            else:
                self.__dict__[k] = d[k]

    def __getitem__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]

    def __iter__(self):
        return iter(self.__dict__.keys())

#    def __repr__(self):
#        return pprint.pformat(self.__dict__)
