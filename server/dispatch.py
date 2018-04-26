# Module dispatch table and implementations
import pandas as pd
from django.conf import settings
from server.models.ParameterSpec import ParameterSpec
from server.models.ParameterVal import ParameterVal
from .dynamicdispatch import DynamicDispatch
from .importmodulefromgithub import original_module_lineno
from .utils import sanitize_dataframe, truncate_table_if_too_big
import os, sys, traceback, types, inspect
from django.utils.translation import gettext as _

from .modules.counybydate import CountByDate
from .modules.formula import Formula
from .modules.loadurl import LoadURL
from .modules.moduleimpl import ModuleImpl
from .modules.pastecsv import PasteCSV
from .modules.pythoncode import PythonCode
from .modules.selectcolumns import SelectColumns
from .modules.twitter import Twitter
from .modules.uploadfile import UploadFile
from .modules.googlesheets import GoogleSheets
from .modules.editcells import EditCells
from .modules.refine import Refine
from .modules.urlscraper import URLScraper
from .modules.scrapetable import ScrapeTable

# ---- Test Support ----


class NOP(ModuleImpl):
    pass


class DoubleMColumn(ModuleImpl):
    @staticmethod
    def render(wfmodule, table):
        table['M'] *= 2
        return table


# ---- Interal modules Dispatch Table ----

module_dispatch_tbl = {
    'loadurl':      LoadURL,
    'pastecsv':     PasteCSV,
    'formula':      Formula,
    'selectcolumns':SelectColumns,
    'pythoncode':   PythonCode,
    'twitter':      Twitter,
    'countbydate':  CountByDate,
    'uploadfile':   UploadFile,
    'googlesheets': GoogleSheets,
    'editcells':    EditCells,
    'refine':       Refine,
    'urlscraper':   URLScraper,
    'scrapetable':  ScrapeTable,

    # For testing
    'NOP':          NOP,
    'double_M_col': DoubleMColumn
}

# ---- Parameter Dictionary Sanitization ----

# Column sanitization: remove invalid column names
# We can get bad column names if the module is reordered, for example
# Never make the render function deal with this.

def sanitize_column_param(pval, table_cols):
    col = pval.get_value()
    if col in table_cols:
        return col
    else:
        return ''

def sanitize_multicolumn_param(pval, table_cols):
    cols = pval.get_value().split(',')
    cols = [c.strip() for c in cols]
    cols = [c for c in cols if c in table_cols]

    return ','.join(cols)


# Extracts all parameter values from the Wf Module, does some error checking,
# and stores in a dict ready for the (dynamically loaded) module's render function
def create_parameter_dict(wf_module, table):
    pdict = {}
    for p in ParameterVal.objects.filter(wf_module=wf_module):
        type = p.parameter_spec.type
        id_name = p.parameter_spec.id_name

        if type == ParameterSpec.COLUMN:
            pdict[id_name] = sanitize_column_param(p, table.columns)
        elif type == ParameterSpec.MULTICOLUMN:
            pdict[id_name] = sanitize_multicolumn_param(p, table.columns)
        else:
            pdict[id_name] = p.get_value()

    return pdict


# ---- Dispatch Entrypoints ----

dynamic_dispatch = DynamicDispatch()

#the wf_module should have both attributes: the module and the version.
def load_dynamically(wf_module):
    # check if this module is loadable dynamically; if so, load it.
    return dynamic_dispatch.load_module(wf_module=wf_module)

# Main render entrypoint.
def module_dispatch_render(wf_module, table):
    if wf_module.module_version is None:
        return pd.DataFrame()  # happens if module deleted

    dispatch = wf_module.module_version.module.dispatch
    error = None
    tableout = None

    # External module -- gets only a parameter dictionary
    if dispatch not in module_dispatch_tbl.keys():

        loadable = load_dynamically(wf_module=wf_module)
        if not loadable:
            raise ValueError('Unknown render dispatch %s for module %s' % (dispatch, wf_module.module.name))

        params = create_parameter_dict(wf_module, table)
        try:
            tableout = loadable.render(table, params)
        except Exception as e:
            # Catch exceptions in the module render function, and return error message + line number to user
            exc_name = type(e).__name__
            exc_type, exc_obj, exc_tb = sys.exc_info()
            tb = traceback.extract_tb(exc_tb)[1]    # [1] = where the exception ocurred, not the render() just above
            fname = os.path.split(tb[0])[1]
            lineno = original_module_lineno(tb[1])
            error = ('{}: {} at line {} of {}'.format(exc_name, str(e), lineno, fname))
            tableout = error

    # Internal module -- has access to internal data structures
    else:
        tableout = module_dispatch_tbl[dispatch].render(wf_module, table)

    error = None
    if isinstance(tableout, str):
        # If the module returns a string, it's an error message. Return the input table (NOP)
        error = tableout
        tableout = table # NOP

    elif isinstance(tableout, tuple) and isinstance(tableout[0], pd.DataFrame) and isinstance(tableout[1], str):
        # tuple with a table and a warning message
        error = tableout[1]
        tableout = tableout[0]

    elif (tableout is not None) and (not isinstance(tableout, pd.DataFrame)):
        # if it's not a string or a tuple it needs to be a table
        error = _('Module did not return a table or an error message')
        tableout = None

    if tableout is None:
        tableout = pd.DataFrame()

    # Restrict to row limit. We set an error, but still return the output table
    nrows = len(tableout)
    if truncate_table_if_too_big(tableout):
        error = _('Output has %d rows, truncated to %d' % (nrows, settings.MAX_ROWS_PER_TABLE))

    if error:
        wf_module.set_error(error, notify=True)
    else:
        wf_module.set_ready(notify=False)  # don't notify, module is (probably?) already in ready state

    tableout = sanitize_dataframe(tableout)  # Ensure correct column types etc.
    return tableout


def module_dispatch_event(wf_module, **kwargs):
    dispatch = wf_module.module_version.module.dispatch
    if dispatch not in module_dispatch_tbl.keys():
        raise ValueError("Unknown dispatch id '%s' while handling event for module '%s'" % (dispatch, str(wf_module)))

    # Clear errors on every new event. (The other place they are cleared is on parameter change)
    wf_module.set_ready(notify=False)
    return module_dispatch_tbl[dispatch].event(wf_module, **kwargs)

def module_dispatch_output(wf_module, table, **kwargs):
    dispatch = wf_module.module_version.module.dispatch
    if dispatch not in module_dispatch_tbl.keys():
        html_file_path = dynamic_dispatch.html_output_path(wf_module)
    else:
        module_path = os.path.dirname(inspect.getfile(module_dispatch_tbl[dispatch]))
        for f in os.listdir(module_path):
            if f.endswith(".html"):
                html_file_path = os.path.join(module_path, f)
                break

    tableout = module_dispatch_render(wf_module, table)
    params = create_parameter_dict(wf_module, table)
    # got some error handling in here if, for some reason, someone tries to call
    # output on this and it doesn't have any defined html output
    html_file = open(html_file_path, 'r+', encoding="utf-8")
    html_str = html_file.read()

    return (html_str, tableout, params)
