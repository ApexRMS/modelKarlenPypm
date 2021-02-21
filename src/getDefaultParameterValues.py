#!/usr/bin/python

import requests
import os
import sys
import pickle
import pypmca

import pandas as pd

from headerFile import *

from syncrosim import SyncrosimDB

try:
    foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19');
except requests.exceptions.RequestException as error:
    print('Error retrieving model folder list over network:')
    print()
    print(error)

regionModelFolders = foldersResponse.json();
regionList = list(regionModelFolders.keys());

# desiredRegion = input('Models are available for the following regions: %s.\nChoose one:  ' % ', '.join(regionList));
desiredRegion = 'Canada';

try:
    if desiredRegion not in regionList:
        raise Halt();
except Halt as hl:
    print('Error: country not found')

folder = regionModelFolders[desiredRegion];
modelsResponse = requests.get('http://data.ipypm.ca/list_models/' + folder);

modelFilenames = modelsResponse.json();
listOfModels = list(modelFilenames.keys());

# desiredModel = input('\nChoose a pre-tuned model from: %s.\nChoice: ' % ', '.join(listOfModels));
desiredModel = 'bcc_2_6_1224';

modelFn = modelFilenames[desiredModel]

try:
    pypmResponse = requests.get('http://data.ipypm.ca/get_pypm/' + modelFn, stream=True);
except requests.exceptions.RequestException as error:
    print('Error retrieving model over network:')
    print()
    print(error)

myPickle = pypmResponse.content
filename = modelFn.split('/')[-1]
model = openModel(filename, myPickle);

try:
    if isinstance(model, type(None)):
        raise Halt('Error: model not retrieved');
except Halt as hl:
    print(hl);

model.save_file('{}\\{}.pypm'.format(OUTPUT_FOLDER, DOWNLOADED_MODEL_NAME))

PARAMETER_ATTIBUTES = ['name', 'description', 'parameter_type', 'initial_value', 'parameter_min', 'parameter_max', 'mcmc_step', 'prior_function']
Parameters = dict()

for key in PARAMETER_ATTIBUTES:
    Parameters[key] = []

Parameters['prior_mean'] = []
Parameters['prior_second'] = []
Parameters['status'] = []

for param_name in model.parameters:

    param = model.parameters[param_name]

    for attr_name in PARAMETER_ATTIBUTES:
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

# changing the order of the output table
ParameterFrame = ParameterFrame[['name', 'description', 'parameter_type', 'initial_value', 'parameter_min', 'parameter_max', 'status', 'prior_function', 'prior_mean', 'prior_second', 'mcmc_step']]

ParameterFrame.to_csv('{}\\{}.csv'.format(OUTPUT_FOLDER, PARAMETER_FILE_NAME), index=False)

''' not sure how to run  both files from the XML as written, so I'll call it below until further advice '''

import getResults
