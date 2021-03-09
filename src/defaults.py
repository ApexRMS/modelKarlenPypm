#!/usr/bin/python

import requests
import numpy as np
import pandas as pd

# "C:\Users\User\AppData\Local\Programs\Python\Python39\Scripts\spyder.exe"

import headerFile
import syncro

console_path = 'C:\\Program Files\\SyncroSim'
library_path = 'C:\\Users\\User\\Documents\\SyncroSim\\Libraries\\epi.ssim'
theConsole = '{}\\SyncroSim.Console.exe'.format(console_path)

ss = syncro.Syncro(console_path, library_path)
hereProj = ss.newProject('Definitions')
myScenario = ss.newScenario('myScenario', hereProj)

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
model = headerFile.openModel(filename, myPickle);

try:
    if isinstance(model, type(None)):
        raise Halt('Error: model not retrieved');
except Halt as hl:
    print(hl);

# model.save_file('{}.temp\\downloadedScenario.pypm'.format(library_path))
model.save_file('C:\\Users\\User\\Documents\\SyncroSim\\Libraries\\epi.ssim.temp\\downloadedScenario.pypm')

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

# suggest MCMC step values
# recommended MCMC step is half of the standard deviation
variables_with_N_priors = list(ParameterFrame[ParameterFrame.prior_function == 'norm'].index)
ParameterFrame.loc[variables_with_N_priors, 'mcmc_step'] = 0.5*ParameterFrame.loc[variables_with_N_priors, 'prior_second']

variables_with_U_priors = list(ParameterFrame[ParameterFrame.prior_function == 'uniform'].index)
ParameterFrame.loc[variables_with_U_priors, 'mcmc_step'] = 1/np.sqrt(12)*ParameterFrame.loc[variables_with_U_priors, 'prior_second']

# changing the order of the output table
ParameterFrame = ParameterFrame[['name', 'description', 'parameter_type', 'initial_value', 'parameter_min', 'parameter_max', 'status', 'prior_function', 'prior_mean', 'prior_second', 'mcmc_step']]

# get the empty data sheet
defaultParameters = ss.getDatasheet(myScenario, "modelKarlenPypm_ParameterValues", empty=True)

# assignn the values
defaultParameters.Name = ParameterFrame.name
defaultParameters.Description = ParameterFrame.description
defaultParameters.Type = ParameterFrame.parameter_type
defaultParameters.Initial = ParameterFrame.initial_value
defaultParameters.Min = ParameterFrame.parameter_min
defaultParameters.Max = ParameterFrame.parameter_max
defaultParameters.Status = ParameterFrame.status
defaultParameters.PriorDist = ParameterFrame.prior_function
defaultParameters.PriorMean = ParameterFrame.prior_mean
defaultParameters.PriorSecond = ParameterFrame.prior_second
defaultParameters.MCMCStep = ParameterFrame.mcmc_step

# save the datasheet
ss.saveDatasheet(myScenario, defaultParameters, "modelKarlenPypm_ParameterValues")
