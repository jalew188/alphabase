# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/constants/modification.ipynb (unless otherwise specified).

__all__ = ['load_mod_yaml', 'load_modloss_importance', 'calc_modification_mass', 'calc_modification_mass_sum',
           'calc_modloss_mass']

# Cell
import os
import numba
import numpy as np
import pandas as pd
from typing import Union, List
from copy import deepcopy

from alphabase.yaml_utils import load_yaml
from alphabase.constants.element import calc_formula_mass

_base_dir = os.path.dirname(__file__)

def _update_all_by_MOD_INFO_DICT():
    global MOD_CHEM
    global MOD_MASS
    global MOD_LOSS_MASS

    MOD_CHEM = {}
    MOD_MASS = {}
    MOD_LOSS_MASS = {}
    for mod, val in MOD_INFO_DICT.items():
        MOD_CHEM[mod] = val['composition']
        MOD_MASS[mod] = val['mass']
        MOD_LOSS_MASS[mod] = val['modloss']

def load_mod_yaml(yaml_file):
    global MOD_INFO_DICT
    global MOD_DF
    MOD_INFO_DICT = load_yaml(yaml_file)

    # Add lower-case modifications for future usages
    for key, modinfo in list(MOD_INFO_DICT.items()):
        MOD_INFO_DICT[key]['upper_case_AA'] = True
        modname, site = key.split('@')
        if len(site) == 1:
            MOD_INFO_DICT[modname+'@'+site.lower()] = deepcopy(modinfo)
            MOD_INFO_DICT[modname+'@'+site.lower()]['upper_case_AA'] = False
        elif '^' in site:
            site = site[0].lower()+site[1:]
            MOD_INFO_DICT[modname+'@'+site] = deepcopy(modinfo)
            MOD_INFO_DICT[modname+'@'+site]['upper_case_AA'] = False

    for mod, val in MOD_INFO_DICT.items():
        MOD_INFO_DICT[mod]['unimod_mass'] = MOD_INFO_DICT[mod]['mono_mass']
        MOD_INFO_DICT[mod]['unimod_modloss'] = MOD_INFO_DICT[mod]['modloss']
        MOD_INFO_DICT[mod]['mass'] = calc_formula_mass(val['composition'])
        MOD_INFO_DICT[mod]['modloss'] = calc_formula_mass(val['modloss_composition'])
        MOD_INFO_DICT[mod]['modloss_importance'] = 0

    _update_all_by_MOD_INFO_DICT()

    MOD_DF = pd.DataFrame().from_dict(MOD_INFO_DICT, orient='index')
    MOD_DF['name'] = MOD_DF.index

load_mod_yaml(
    os.path.join(_base_dir,
    'used_mod.yaml')
)

def load_modloss_importance(yaml_file):
    global MOD_LOSS_IMPORTANCE
    MOD_LOSS_IMPORTANCE = load_yaml(yaml_file)
    for mod,val in MOD_LOSS_IMPORTANCE.items():
        MOD_INFO_DICT[mod]['modloss_importance'] = val
    MOD_DF['modloss_importance'] = pd.DataFrame().from_dict(
        MOD_LOSS_IMPORTANCE, orient='index'
    )
    MOD_DF.loc[pd.isna(MOD_DF['modloss_importance']), 'modloss_importance'] = 0


load_modloss_importance(
    os.path.join(_base_dir,
    'modloss_importance.yaml')
)

def _update_all_by_MOD_DF():
    global MOD_INFO_DICT
    MOD_INFO_DICT = MOD_DF.to_dict(orient='index')
    _update_all_by_MOD_INFO_DICT()


# Cell
def calc_modification_mass(
    peplen:int,
    mod_names:List[str],
    mod_sites:List[int]
)->np.array:
    '''
    Calculate modification masses for the given peptide length (`peplen`),
    and modified site list.
    Args:
        peplen (int): peptide length
        mod_names (List[str]): modification name list
        mod_sites (List[int]): modification site list corresponding
            to `mod_names`.
            * `site=0` refers to an N-term modification
            * `site=-1` refers to a C-term modification
            * `1<=site<=peplen` refers to a normal modification
    Returns:
        np.array: 1-D array with length=`peplen`.
            Masses of modifications through the peptide,
            `0` if sites has no modifications
    '''
    masses = np.zeros(peplen)
    for site, mod in zip(mod_sites, mod_names):
        if site == 0:
            masses[site] += MOD_MASS[mod]
        elif site == -1:
            masses[site] += MOD_MASS[mod]
        else:
            masses[site-1] += MOD_MASS[mod]
    return masses

def calc_modification_mass_sum(
    mod_names:List[str]
)->float:
    """
    Calculate summed mass of the given modification
    without knowing the sites and peptide length.
    It is useful to calculate peptide mass.
    Args:
        mod_names (List[str]): modification name list
    Returns:
        float: total mass
    """
    return np.sum([
        MOD_MASS[mod] for mod in mod_names
    ])


# Cell
@numba.jit(nopython=True, nogil=True)
def _calc_modloss(
    mod_losses: np.array,
    _loss_importance: np.array
)->np.array:
    '''
    Calculate modification loss masses (e.g. -98 Da for Phospho@S/T,
    -64 Da for Oxidation@M). Modification with higher `_loss_importance`
    has higher priorities. For example, `AM(Oxidation@M)S(Phospho@S)...`,
    importance of Phospho@S > importance of Oxidation@M, so the modloss of
    b3 ion will be -98 Da, not -64 Da.
    Args:
        mod_losses (np.array): mod loss masses of each AA position
        _loss_importance (np.array): mod loss importance of each AA position
    Returns:
        np.array: new mod_loss masses selected by `_loss_importance`
    '''
    prev_importance = _loss_importance[0]
    prev_most = 0
    for i, _curr_imp in enumerate(_loss_importance[1:]):
        if _curr_imp > prev_importance:
            prev_most = i+1
            prev_importance = _curr_imp
        else:
            mod_losses[i+1] = mod_losses[prev_most]
    return mod_losses

def calc_modloss_mass(
    peplen: int,
    mod_names: List,
    mod_sites: List,
    for_nterm_frag: bool,
)->np.array:
    '''
    Calculate modification loss masses (e.g. -98 Da for Phospho@S/T,
    -64 Da for Oxidation@M). Modifications with higher `MOD_LOSS_IMPORTANCE`
    have higher priorities. For example, `AM(Oxidation@M)S(Phospho@S)...`,
    importance of Phospho@S > importance of Oxidation@M, so the modloss of
    b3 ion will be -98 Da, not -64 Da.
    Args:
        peplen (int): peptide length
        mod_names (List[str]): modification name list
        mod_sites (List[int]): modification site list corresponding
        for_nterm_frag (bool): if `True`, the loss will be on the
            N-term fragments (mainly `b` ions); if `False`, the loss
            will be on the C-term fragments (mainly `y` ions)
    Returns:
        np.array: mod_loss masses
    '''
    if not mod_names: return np.zeros(peplen-1)
    mod_losses = np.zeros(peplen+2)
    mod_losses[mod_sites] = [MOD_LOSS_MASS[mod] for mod in mod_names]
    _loss_importance = np.zeros(peplen+2)
    _loss_importance[mod_sites] = [
        MOD_LOSS_IMPORTANCE[mod] if mod in MOD_LOSS_IMPORTANCE else 0
        for mod in mod_names
    ]

    # Will not consider the modloss if the corresponding modloss_importance is 0
    mod_losses[_loss_importance==0] = 0

    if for_nterm_frag:
        return _calc_modloss(mod_losses, _loss_importance)[1:-2]
    else:
        return _calc_modloss(mod_losses[::-1], _loss_importance[::-1])[-3:0:-1]
