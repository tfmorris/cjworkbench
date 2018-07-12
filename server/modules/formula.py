import itertools
import re
from .moduleimpl import ModuleImpl
from .utils import build_globals_for_eval
import pandas as pd
from formulas import Parser
from django.utils.translation import gettext as _

# ---- Formula ----

def letter_ref_to_number(letter_ref):
    if re.search(r"[^a-zA-Z]+", letter_ref):
        raise ValueError(_("%s is not a valid reference" % letter_ref))

    return_number = 0

    for idx, letter in enumerate(reversed(letter_ref)):
        return_number += (ord(letter.upper()) - 64) * (26**idx)

    return return_number - 1  # 0-indexed


def python_formula(table, formula):
    colnames = [x.replace(" ", "_") for x in table.columns]  # spaces to underscores in column names

    code = compile(formula, '<string>', 'eval')
    custom_code_globals = build_globals_for_eval()

    # Much experimentation went into the form of this loop for good performance.
    # Note we don't use iterrows or any pandas indexing, and construct the values dict ourselves
    newcol = pd.Series(list(itertools.repeat(None, len(table))))
    for i, row in enumerate(table.values):
        newcol[i] = eval(code, custom_code_globals, dict(zip(colnames, row)))

    return newcol


def flatten_single_element_lists(x):
    """ If passed a list with only one element, returns that element, else the original list"""
    if isinstance(x, list) and len(x)==1:
        return x[0]
    else:
        return x

def eval_excel_one_row(code, table):

    # Generate a list of input table values for each range in the expression
    formula_args = []
    for token, obj in code.inputs.items():
        if obj is None:
            raise ValueError(_('Invalid cell range: %s') % token)
        ranges = obj.ranges
        if len(ranges) != 1:
            raise ValueError(_('Excel range must be a rectangular block of values'))  # ...not sure what input would get us here
        range = ranges[0]

        # Unpack start/end row/col
        r1 = int(range['r1'])-1
        r2 = int(range['r2'])
        c1 = int(range['n1'])-1
        c2 = int(range['n2'])

        nrows, ncols = table.shape
        if r1<0 or r1>=nrows or c1<0 or c1>=ncols:
            return '#REF!' # expression references non-existent data

        table_part = list(table.iloc[r1:r2,c1:c2].values.flat)
        formula_args.append(flatten_single_element_lists(table_part))

    # evaluate the formula just once
    try:
        val = code(*formula_args)
    except Exception as e:
        if type(e).__name__ == 'DispatcherError':
            raise ValueError(_('Unknown function: %s') % e.args[1])
        else:
            raise
    return val


def eval_excel_all_rows(code, table):
    col_idx = []
    for token, obj in code.inputs.items():
        # If the formula is valid but no object comes back it means the reference is no good
        # Missing row number?
        # with only A-Z. But just in case:
        if obj is None:
            raise ValueError(_('Bad cell reference %s') % token)

        ranges = obj.ranges
        for rng in ranges:
            # r1 and r2 refer to which rows are referenced by the range.
            if rng['r1'] != '1' or rng['r2'] != '1':
                raise ValueError(_('Excel formulas can only reference the first row when applied to all rows'))

            col_first = rng['n1']
            col_last = rng['n2']

            col_idx.append(list(range(col_first - 1, col_last)))

    newcol = []
    for i, row in enumerate(table.values):
        args_to_excel = []
        for col in col_idx:
            args_to_excel.append(flatten_single_element_lists([row[idx] for idx in col]))
        newcol.append(code(*args_to_excel))

    return newcol


def excel_formula(table, formula, all_rows):
    try:
        # 0 is a list of tokens, 1 is the function builder object
        code = Parser().ast(formula)[1].compile()
    except Exception as e:
        raise  ValueError(_("Couldn't parse formula: %s") % str(e))

    if all_rows:
        newcol = eval_excel_all_rows(code, table)
    else:
        newcol = list(itertools.repeat(None, len(table))) # the whole column is blank except first row
        newcol[0] = eval_excel_one_row(code, table)

    return newcol


class Formula(ModuleImpl):

    def render(wf_module, table):

        if table is None:
            return None     # no rows to process

        syntax = wf_module.get_param_menu_idx('syntax')
        if syntax== 0:
            formula = wf_module.get_param_string('formula_excel').strip()
            if formula=='':
                return table
            all_rows = wf_module.get_param_checkbox('all_rows')
            try:
                newcol = excel_formula(table, formula, all_rows)
            except Exception as e:
                return str(e)
        else:
            formula = wf_module.get_param_string('formula_python').strip()
            if formula=='':
                return table
            try:
                newcol = python_formula(table, formula)
            except Exception as e:
                return str(e)

        # if no output column supplied, use result0, result1, etc.
        out_column = wf_module.get_param_string('out_column')
        if out_column == '':
            if 'result' not in table.columns:
                out_column = 'result'
            else:
                n = 0
                while 'result' + str(n) in colnames:
                    n += 1
                out_column = 'result' + str(n)
        table[out_column] = newcol

        wf_module.set_ready(notify=False)
        return table
