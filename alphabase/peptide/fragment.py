# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/peptide/fragment.ipynb (unless otherwise specified).

__all__ = ['get_charged_frag_types', 'parse_charged_frag_type', 'init_zero_fragment_dataframe',
           'init_fragment_dataframe_from_other', 'init_fragment_by_precursor_dataframe',
           'update_sliced_fragment_dataframe', 'get_sliced_fragment_dataframe', 'update_sliced_fragment_dataframe',
           'get_sliced_fragment_dataframe', 'concat_precursor_fragment_dataframes',
           'calc_fragment_mz_values_for_same_nAA', 'reset_precursor_df',
           'create_fragment_mz_dataframe_ignore_old_idxes', 'create_fragment_mz_dataframe',
           'create_fragment_mz_dataframe_by_sort_nAA', 'update_precursor_mz']

# Cell
import numpy as np
import pandas as pd
from typing import List, Union, Tuple
import warnings

from alphabase.peptide.mass_calc import *
from alphabase.constants.modification import (
    calc_modloss_mass
)
from alphabase.constants.element import (
    MASS_H2O, MASS_PROTON,
    MASS_NH3, CHEM_MONO_MASS
)

def get_charged_frag_types(
    frag_types:List[str],
    max_frag_charge:int = 2
)->List[str]:
    '''
    Combine fragment types and charge states.

    Args:
        frag_types (List[str]): e.g. ['b','y','b_modloss','y_modloss']
        max_frag_charge (int): max fragment charge. (default: 2)
    Returns:
        List[str]: for `frag_types=['b','y','b_modloss','y_modloss']` and `max_frag_charge=2`,
        return `['b_z1','b_z2','y_z1','y_z2','b_modloss_z1','b_modloss_z2','y_modloss_z1','y_modloss_z2']`.
    '''
    charged_frag_types = []
    for _type in frag_types:
        for _ch in range(1, max_frag_charge+1):
            charged_frag_types.append(f"{_type}_z{_ch}")
    return charged_frag_types

def parse_charged_frag_type(
    charged_frag_type: str
)->Tuple[str,int]:
    '''
    Oppsite to `get_charged_frag_types`.
    Args:
        charged_frag_type (str): e.g. 'y_z1', 'b_modloss_z1'
    Returns:
        str: fragment type, e.g. 'b','y'
        int: charge state, can be a negative value
    '''
    items = charged_frag_type.split('_')
    _ch = items[-1]
    _type = '_'.join(items[:-1])
    return _type, int(_ch[1:])

# Cell
def init_zero_fragment_dataframe(
    peplen_array:np.array,
    charged_frag_types:List[str],
    dtype=np.float64
)->Tuple[pd.DataFrame, np.array, np.array]:
    '''
    Args:
        peplen_array (np.array): peptide lengths for the fragment dataframe
        charged_frag_types (List[str]):
            `['b_z1','b_z2','y_z1','y_z2','b_modloss_z1','y_H2O_z1'...]`
    Returns:
        pd.DataFrame: `fragment_df` with zero values
        np.array (int64): the start indices point to the `fragment_df` for each peptide
        np.array (int64): the end indices point to the `fragment_df` for each peptide
    '''
    indices = np.zeros(len(peplen_array)+1, dtype=np.int64)
    indices[1:] = peplen_array-1
    indices = np.cumsum(indices)
    fragment_df = pd.DataFrame(
        np.zeros((indices[-1],len(charged_frag_types)), dtype=dtype),
        columns = charged_frag_types
    )
    return fragment_df, indices[:-1], indices[1:]

def init_fragment_dataframe_from_other(
    reference_fragment_df: pd.DataFrame,
    dtype=np.float64
):
    '''
    Init zero fragment dataframe from the `reference_fragment_df`
    '''
    return pd.DataFrame(
        np.zeros_like(reference_fragment_df.values, dtype=dtype),
        columns = reference_fragment_df.columns
    )

def init_fragment_by_precursor_dataframe(
    precursor_df,
    charged_frag_types: List[str],
    reference_fragment_df: int = None,
    dtype=np.float64
):
    '''
    Init zero fragment dataframe for the `precursor_df`. If
    the `reference_fragment_df` is provided, it will generate
    the dataframe based on the reference. Otherwise it
    generates the dataframe from scratch.
    Args:
        precursor_df (pd.DataFrame): precursors to generate fragment masses,
            if `precursor_df` contains the 'frag_start_idx' column,
            it is better to provide `reference_fragment_df` as
            `precursor_df.frag_start_idx` and `precursor.frag_end_idx`
            point to the indices in `reference_fragment_df`
        charged_frag_types (List):
            `['b_z1','b_z2','y_z1','y_z2','b_modloss_z1','y_H2O_z1'...]`
        reference_fragment_df (pd.DataFrame): generate fragment_mz_df based
            on this reference (default: None)
    Returns:
        pd.DataFrame: zero `fragment_df` with given `charged_frag_types`
    '''
    if 'frag_start_idx' not in precursor_df.columns:
        fragment_df, start_indices, end_indices = init_zero_fragment_dataframe(
            precursor_df.nAA.values,
            charged_frag_types,
            dtype=dtype
        )
        precursor_df['frag_start_idx'] = start_indices
        precursor_df['frag_end_idx'] = end_indices
    else:
        if reference_fragment_df is None:
            raise ValueError(
                "`precursor_df` contains 'frag_start_idx' column, "\
                "please provide `reference_fragment_df` argument"
            )
            fragment_df = pd.DataFrame(
                np.zeros((
                    precursor_df.frag_end_idx.max(), len(charged_frag_types)
                )),
                columns = charged_frag_types
            )
        else:
            fragment_df = init_fragment_dataframe_from_other(
                reference_fragment_df[[
                    _fr for _fr in charged_frag_types
                    if _fr in reference_fragment_df.columns
                ]],
                dtype=dtype
            )
    return fragment_df

# Cell
def update_sliced_fragment_dataframe(
    fragment_df: pd.DataFrame,
    values: np.array,
    frag_start_end_list: List[Tuple[int,int]],
    charged_frag_types: List[str],
)->pd.DataFrame:
    '''
    Set the values of the slices `frag_start_end_list=[(start,end),(start,end),...]` of fragment_df.
    Args:
        fragment_df (pd.DataFrame): fragment dataframe to be set
        frag_start_end_list (List[Tuple[int,int]]): e.g. `[(start,end),(start,end),...]`
        charged_frag_types (List[str]): e.g. `['b_z1','b_z2','y_z1','y_z2']`
    Returns:
        pd.DataFrame: fragment_df after the values are set
    '''
    frag_slice_list = [slice(start,end) for start,end in frag_start_end_list]
    frag_slices = np.r_[tuple(frag_slice_list)]
    fragment_df.loc[frag_slices, charged_frag_types] = values
    return fragment_df

def get_sliced_fragment_dataframe(
    fragment_df: pd.DataFrame,
    frag_start_end_list:Union[List,np.array],
    charged_frag_types:List = None,
)->pd.DataFrame:
    '''
    Get the sliced fragment_df from `frag_start_end_list=[(start,end),(start,end),...]`.
    Args:
        fragment_df (pd.DataFrame): fragment dataframe to be set
        frag_start_end_list (List[Tuple[int,int]]): e.g. `[(start,end),(start,end),...]`
        charged_frag_types (List[str]): e.g. `['b_z1','b_z2','y_z1','y_z2']` (default: None)
    Returns:
        pd.DataFrame: sliced fragment_df. If `charged_frag_types` is None,
        return fragment_df with all columns
    '''
    frag_slice_list = [slice(start,end) for start,end in frag_start_end_list]
    frag_slices = np.r_[tuple(frag_slice_list)]
    if charged_frag_types is None or len(charged_frag_types)==0:
        charged_frag_types = slice(None)
    return fragment_df.loc[frag_slices, charged_frag_types]

# Cell
def update_sliced_fragment_dataframe(
    fragment_df: pd.DataFrame,
    values: np.array,
    frag_start_end_list: List[Tuple[int,int]],
    charged_frag_types: List[str],
)->pd.DataFrame:
    '''
    Set the values of the slices `frag_start_end_list=[(start,end),(start,end),...]` of fragment_df.
    Args:
        fragment_df (pd.DataFrame): fragment dataframe to be set
        frag_start_end_list (List[Tuple[int,int]]): e.g. `[(start,end),(start,end),...]`
        charged_frag_types (List[str]): e.g. `['b_z1','b_z2','y_z1','y_z2']`
    Returns:
        pd.DataFrame: fragment_df after the values are set
    '''
    frag_slice_list = [slice(start,end) for start,end in frag_start_end_list]
    frag_slices = np.r_[tuple(frag_slice_list)]
    fragment_df.loc[frag_slices, charged_frag_types] = values
    return fragment_df

def get_sliced_fragment_dataframe(
    fragment_df: pd.DataFrame,
    frag_start_end_list:Union[List,np.array],
    charged_frag_types:List = None,
)->pd.DataFrame:
    '''
    Get the sliced fragment_df from `frag_start_end_list=[(start,end),(start,end),...]`.
    Args:
        fragment_df (pd.DataFrame): fragment dataframe to be set
        frag_start_end_list (List[Tuple[int,int]]): e.g. `[(start,end),(start,end),...]`
        charged_frag_types (List[str]): e.g. `['b_z1','b_z2','y_z1','y_z2']` (default: None)
    Returns:
        pd.DataFrame: sliced fragment_df. If `charged_frag_types` is None,
        return fragment_df with all columns
    '''
    frag_slice_list = [slice(start,end) for start,end in frag_start_end_list]
    frag_slices = np.r_[tuple(frag_slice_list)]
    if charged_frag_types is None or len(charged_frag_types)==0:
        charged_frag_types = slice(None)
    return fragment_df.loc[frag_slices, charged_frag_types]

# Cell
def concat_precursor_fragment_dataframes(
    precursor_df_list: List[pd.DataFrame],
    fragment_df_list: List[pd.DataFrame],
    *other_fragment_df_lists
)->Tuple[pd.DataFrame,...]:
    '''
    Since fragment_df is indexed by precursor_df, when we concatenate multiple
    fragment_df, the indexed positions will change for in precursor_dfs,
    this function keeps the correct indexed positions of precursor_df when
    concatenating multiple fragment_df dataframes.
    Args:
        precursor_df_list (List[pd.DataFrame]): precursor dataframe list to concatenate
        fragment_df_list (List[pd.DataFrame]): fragment dataframe list to concatenate
        *other_fragment_df_lists: arbitray other fragment dataframe list to concatenate,
            e.g. fragment_mass_df, fragment_inten_df, ...
    Returns:
        Tuple[pd.DataFrame,...]: concatenated precursor_df, fragment_df, *other_fragment_df ...
    '''
    fragment_df_lens = [len(fragment_df) for fragment_df in fragment_df_list]
    cum_frag_df_lens = np.cumsum(fragment_df_lens)
    for i,precursor_df in enumerate(precursor_df_list[1:]):
        precursor_df[['frag_start_idx','frag_end_idx']] += cum_frag_df_lens[i]
    return (
        pd.concat(precursor_df_list).reset_index(drop=True),
        pd.concat(fragment_df_list).reset_index(drop=True),
        *[pd.concat(other_list).reset_index(drop=True)
            for other_list in other_fragment_df_lists
        ]
    )

# Cell
def calc_fragment_mz_values_for_same_nAA(
    df_group:pd.DataFrame,
    nAA:int,
    charged_frag_types:list
):
    mod_list = df_group.mods.str.split(';').apply(
        lambda x: [m for m in x if len(m)>0]
    ).values
    site_list = df_group.mod_sites.str.split(';').apply(
        lambda x: [int(s) for s in x if len(s)>0]
    ).values

    if 'mod_deltas' in df_group.columns:
        mod_delta_list = df_group.mod_deltas.str.split(';').apply(
            lambda x: [float(m) for m in x if len(m)>0]
        ).values
        mod_delta_site_list = df_group.mod_delta_sites.str.split(';').apply(
            lambda x: [int(s) for s in x if len(s)>0]
        ).values
    else:
        mod_delta_list = None
        mod_delta_site_list = None
    (
        b_mass, y_mass, pepmass
    ) = calc_b_y_and_peptide_masses_for_same_len_seqs(
        df_group.sequence.values.astype('U'),
        mod_list, site_list,
        mod_delta_list,
        mod_delta_site_list
    )
    b_mass = b_mass.reshape(-1)
    y_mass = y_mass.reshape(-1)

    # if (
    #     'charge' in df_group.columns and
    #     'precursor_mz' not in df_group.columns
    # ):
    #     df_group['precursor_mz'] = pepmass/df_group[
    #         'charge'
    #     ].values + MASS_PROTON

    for charged_frag_type in charged_frag_types:
        if charged_frag_type.startswith('b_modloss'):
            b_modloss = np.concatenate([
                calc_modloss_mass(nAA, mods, sites, True)
                for mods, sites in zip(mod_list, site_list)
            ])
            break
    for charged_frag_type in charged_frag_types:
        if charged_frag_type.startswith('y_modloss'):
            y_modloss = np.concatenate([
                calc_modloss_mass(nAA, mods, sites, False)
                for mods, sites in zip(mod_list, site_list)
            ])
            break

    mz_values = []
    add_proton = MASS_PROTON
    for charged_frag_type in charged_frag_types:
        frag_type, charge = parse_charged_frag_type(charged_frag_type)
        if frag_type =='b':
            mz_values.append(b_mass/charge + add_proton)
        elif frag_type == 'y':
            mz_values.append(y_mass/charge + add_proton)
        elif frag_type == 'b_modloss':
            _mass = (b_mass-b_modloss)/charge + add_proton
            _mass[b_modloss == 0] = 0
            mz_values.append(_mass)
        elif frag_type == 'y_modloss':
            _mass = (y_mass-y_modloss)/charge + add_proton
            _mass[y_modloss == 0] = 0
            mz_values.append(_mass)
        elif frag_type == 'b_H2O':
            _mass = (b_mass-MASS_H2O)/charge + add_proton
            mz_values.append(_mass)
        elif frag_type == 'y_H2O':
            _mass = (y_mass-MASS_H2O)/charge + add_proton
            mz_values.append(_mass)
        elif frag_type == 'b_NH3':
            _mass = (b_mass-MASS_NH3)/charge + add_proton
            mz_values.append(_mass)
        elif frag_type == 'y_NH3':
            _mass = (y_mass-MASS_NH3)/charge + add_proton
            mz_values.append(_mass)
        elif frag_type == 'c':
            _mass = (b_mass+MASS_NH3)/charge + add_proton
            mz_values.append(_mass)
        elif frag_type == 'z':
            _mass = (
                y_mass-(MASS_NH3-CHEM_MONO_MASS['H'])
            )/charge + add_proton
            mz_values.append(_mass)
        else:
            raise NotImplementedError(
                f'Fragment type "{frag_type}" is not in fragment_mz_df.'
            )
    return np.array(mz_values).T

# Cell
def reset_precursor_df(df:pd.DataFrame):
    """ For faster precursor/fragment calculation """
    df.sort_values('nAA', inplace=True)
    df.reset_index(drop=True, inplace=True)

def create_fragment_mz_dataframe_ignore_old_idxes(
    precursor_df: pd.DataFrame,
    charged_frag_types:List,
    batch_size=500000,
):
    """Sort nAA in precursor_df for faster fragment mz dataframe creation.

    Because the fragment mz values are continous in memory, so it is faster
    when setting values in pandas.

    Note that this function will change the order and index of precursor_df

    Args:
        precursor_df (pd.DataFrame): precursor dataframe
        charged_frag_types (List): fragment types list
        batch_size (int, optional): Calculate fragment mz values in batch.
            Defaults to 500000.
    """
    if 'frag_start_idx' in precursor_df.columns:
        del precursor_df['frag_start_idx']
        del precursor_df['frag_end_idx']

    if 'nAA' not in precursor_df.columns:
        precursor_df['nAA'] = precursor_df.sequence.str.len()
        precursor_df.sort_values('nAA', inplace=True)
    elif not precursor_df.nAA.is_monotonic:
        precursor_df.sort_values('nAA', inplace=True)
    precursor_df.reset_index(drop=True, inplace=True)

    fragment_mz_df = init_fragment_by_precursor_dataframe(
        precursor_df, charged_frag_types
    )

    _grouped = precursor_df.groupby('nAA')
    for nAA, big_df_group in _grouped:
        for i in range(0, len(big_df_group), batch_size):
            batch_end = i+batch_size

            df_group = big_df_group.iloc[i:batch_end,:]

            mz_values = calc_fragment_mz_values_for_same_nAA(
                df_group, nAA, charged_frag_types
            )

            fragment_mz_df.iloc[
                df_group.frag_start_idx.values[0]:
                df_group.frag_end_idx.values[-1], :
            ] = mz_values
    return precursor_df, fragment_mz_df

#wrapper
create_fragment_mz_dataframe_by_sort_nAA = create_fragment_mz_dataframe_ignore_old_idxes

def create_fragment_mz_dataframe(
    precursor_df: pd.DataFrame,
    charged_frag_types:List,
    reference_fragment_df: pd.DataFrame = None,
    batch_size=500000,
)->Tuple[pd.DataFrame, pd.DataFrame]:
    '''
    Generate fragment mass dataframe for the precursor_df. If
    the `reference_fragment_df` is provided and precursor_df contains `frag_start_idx`,
    it will generate  the mz dataframe based on the reference. Otherwise it
    generates the mz dataframe from scratch.
    Args:
        precursor_df (pd.DataFrame): precursors to generate fragment masses,
            if `precursor_df` contains the 'frag_start_idx' column,
            `reference_fragment_df` must be provided
        charged_frag_types (List):
            `['b_z1','b_z2','y_z1','y_z2','b_modloss_1','y_H2O_z1'...]`
        reference_fragment_df (pd.DataFrame): generate fragment_mz_df based
            on this reference, as `precursor_df.frag_start_idx` and
            `precursor.frag_end_idx` point to the indices in
            `reference_fragment_df`
    Returns:
        pd.DataFrame: `precursor_df`. `precursor_df` contains the 'charge' column,
        this function will automatically assign the 'precursor_mz' to `precursor_df`
        pd.DataFrame: `fragment_mz_df` with given `charged_frag_types`
    Raises:
        ValueError: when `precursor_df` contains 'frag_start_idx' but
        `reference_fragment_df` is not None
    '''
    if reference_fragment_df is None:
        if 'frag_start_idx' in precursor_df.columns:
            raise ValueError(
                "`precursor_df` contains 'frag_start_idx' column, "\
                "please provide `reference_fragment_df` argument"
            )
    if 'nAA' not in precursor_df.columns:
        precursor_df['nAA'] = precursor_df.sequence.str.len()
        reset_precursor_df(precursor_df)

    if  'frag_start_idx' not in precursor_df.columns:
        return create_fragment_mz_dataframe_by_sort_nAA(
            precursor_df, charged_frag_types, batch_size
        )

    if (precursor_df['nAA'].is_monotonic and
        reference_fragment_df is None
    ):
        return create_fragment_mz_dataframe_by_sort_nAA(
            precursor_df, charged_frag_types, batch_size
        )

    if reference_fragment_df is not None:
        fragment_mz_df = init_fragment_dataframe_from_other(
            reference_fragment_df[[
                _fr for _fr in charged_frag_types
                if _fr in reference_fragment_df.columns
            ]]
        )
    else:
        fragment_df_list = []

    precursor_df_list = []

    _grouped = precursor_df.groupby('nAA')
    for nAA, big_df_group in _grouped:
        for i in range(0, len(big_df_group), batch_size):
            batch_end = i+batch_size

            df_group = big_df_group.iloc[i:batch_end,:]

            mz_values = calc_fragment_mz_values_for_same_nAA(
                df_group, nAA, charged_frag_types
            )

            if reference_fragment_df is not None:
                update_sliced_fragment_dataframe(
                    fragment_mz_df, mz_values,
                    df_group[['frag_start_idx','frag_end_idx']].values,
                    charged_frag_types,
                )
            else:
                _fragment_mz_df = init_fragment_by_precursor_dataframe(
                    df_group,
                    charged_frag_types
                )
                _fragment_mz_df[:] = mz_values
                fragment_df_list.append(_fragment_mz_df)
            precursor_df_list.append(df_group)

    if reference_fragment_df is not None:
        return pd.concat(precursor_df_list), fragment_mz_df
    else:
        return concat_precursor_fragment_dataframes(
            precursor_df_list, fragment_df_list
        )


# Cell
def update_precursor_mz(
    precursor_df: pd.DataFrame,
    batch_size = 500000,
)->pd.DataFrame:
    """
    Calculate precursor_mz for the precursor_df
    Args:
        precursor_df (pd.DataFrame):
          precursor_df with the 'charge' column

    Returns:
        pd.DataFrame: precursor_df with 'precursor_mz'
    """

    if 'nAA' not in precursor_df:
        precursor_df['nAA'] = precursor_df.sequence.str.len()
        reset_precursor_df(precursor_df)
        _calc_in_order = True
    elif precursor_df.nAA.is_monotonic and precursor_df.index.is_monotonic:
        _calc_in_order = True
    else:
        _calc_in_order = False
    precursor_df['precursor_mz'] = 0.
    _grouped = precursor_df.groupby('nAA')
    for nAA, big_df_group in _grouped:
        for i in range(0, len(big_df_group), batch_size):
            batch_end = i+batch_size

            df_group = big_df_group.iloc[i:batch_end,:]

            pep_mzs = calc_peptide_masses_for_same_len_seqs(
                df_group.sequence.values.astype('U'),
                df_group.mods.values,
                df_group.mod_deltas.values if 'mod_deltas' in df_group.columns else None
            )/df_group.charge + MASS_PROTON
            if _calc_in_order:
                precursor_df.loc[:,'precursor_mz'].values[
                    df_group.index.values[0]:
                    df_group.index.values[-1]+1
                ] = pep_mzs
            else:
                precursor_df.loc[
                    df_group.index, 'precursor_mz'
                ] = pep_mzs
    return precursor_df