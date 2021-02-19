#!/usr/bin/python

import os
import pypmca

import pandas as pd

model = pypmca.Model.open_file('{}\\downloaded_model.pypm'.format('C:\\Users\\User\\Documents\\SyncroSim\\Packages\\modelKarlenPypm'))

try:
    if isinstance(model, type(None)):
        raise Halt('Error: model not retrieved')
except Halt as hl:
    print(hl)

PARAM_ATTRIBUTES = ['name', 'description', 'parameter_type', 'initial_value', 'parameter_min', 'parameter_max', 'mcmc_step', 'prior_function']
Parameters = dict()

for key in PARAM_ATTRIBUTES:
    Parameters[key] = []

Parameters['prior_mean'] = []
Parameters['prior_second'] = []
Parameters['status'] = []

for param_name in model.parameters:

    param = model.parameters[param_name]

    for attr_name in PARAM_ATTRIBUTES:
        Parameters[attr_name].append( getattr(param, attr_name) )
    if param.prior_function == None:
        Parameters['prior_mean'].append('')
        Parameters['prior_second'].append('')
    else:
        Parameters['prior_mean'].append(param.prior_parameters['mean'])
        Parameters['prior_second'].append(list(param.prior_parameters.values())[1])

    Parameters['status'].append(param.get_status())

ParameterFrame = pd.DataFrame()

for key in Parameters.keys():
    ParameterFrame[key] = Parameters[key]

ParameterFrame = ParameterFrame[['name', 'description', 'parameter_type', 'initial_value', 'parameter_min', 'parameter_max', 'status', 'prior_function', 'prior_mean', 'prior_second', 'mcmc_step']]

ParameterFrame.to_csv('{}\\model_parameters.csv'.format('C:\\Users\\User\\Documents\\SyncroSim\\Packages\\modelKarlenPypm'), index=False)
