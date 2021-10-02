# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/constants/modification.ipynb (unless otherwise specified).

__all__ = ['load_mod_yaml', 'load_modloss_importance', 'get_modification_mass', 'get_modloss_mass']

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

def load_mod_yaml(yaml_file):
    global MOD_INFO_DICT
    global MOD_CHEM
    global MOD_MASS
    global MOD_LOSS_MASS
    global MOD_DF
    MOD_INFO_DICT = load_yaml(yaml_file)

    # Add lower-case modifications for future usages
    for key, modinfo in list(MOD_INFO_DICT.items()):
       modname, site = key.split('@')
       if len(site) == 1:
           MOD_INFO_DICT[modname+'@'+site.lower()] = deepcopy(modinfo)
           MOD_INFO_DICT[modname+'@'+site.lower()]['classification'] = 'Lower-case'

    MOD_CHEM = {}
    for key, val in MOD_INFO_DICT.items():
        MOD_CHEM[key] = val['composition']
        MOD_INFO_DICT[key]['unimod_mass'] = MOD_INFO_DICT[key]['mono_mass']
        MOD_INFO_DICT[key]['unimod_modloss'] = MOD_INFO_DICT[key]['modloss']


    MOD_MASS = dict(
        [
            (mod, calc_formula_mass(chem))
            for mod, chem in MOD_CHEM.items()
        ]
    )

    MOD_LOSS_MASS = dict(
        [
        (mod, calc_formula_mass(val['modloss_composition']))
        for mod, val in MOD_INFO_DICT.items()
        ]
    )

    MOD_DF = pd.DataFrame().from_dict(MOD_INFO_DICT, orient='index')
    MOD_DF['mass'] = pd.DataFrame().from_dict(MOD_MASS, orient='index')
    MOD_DF['modloss'] = pd.DataFrame().from_dict(MOD_LOSS_MASS, orient='index')

load_mod_yaml(
    os.path.join(_base_dir,
    'used_mod.yaml')
)

def load_modloss_importance(yaml_file):
    global MOD_LOSS_IMPORTANCE
    MOD_LOSS_IMPORTANCE = load_yaml(yaml_file)
    MOD_DF['modloss_importance'] = pd.DataFrame().from_dict(MOD_LOSS_IMPORTANCE, orient='index')
    MOD_DF.loc[pd.isna(MOD_DF['modloss_importance']), 'modloss_importance'] = 0


load_modloss_importance(
    os.path.join(_base_dir,
    'modloss_importance.yaml')
)

# Cell
def get_modification_mass(
    peplen:int,
    mod_names:List[str],
    mod_sites:List[int]
)->np.array:
    '''
    Get modification masses for the given peptide length (`peplen`),
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


# Cell
@numba.jit(nopython=True, nogil=True)
def _get_modloss(
    mod_losses: np.array,
    _loss_importance: np.array
)->np.array:
    '''
    Get modification loss masses (e.g. -98 Da for Phospho@S/T,
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

def get_modloss_mass(
    peplen: int,
    mod_names: List,
    mod_sites: List,
    for_nterm_frag: bool,
)->np.array:
    '''
    Get modification loss masses (e.g. -98 Da for Phospho@S/T,
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
        return _get_modloss(mod_losses, _loss_importance)[1:-2]
    else:
        return _get_modloss(mod_losses[::-1], _loss_importance[::-1])[-3:0:-1]
