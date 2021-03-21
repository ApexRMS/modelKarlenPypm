#!/usr/bin/python

# for i in list(globals().keys()):
#     if(i[0] != '_'):
#         exec('del {}'.format(i))

import pandas
import numpy
import datetime

from syncro import *
from headerFile import * # downloadModel, tablePriorDist, tableStatus, tableType

env = ssimEnvironment()
myScenario = scenario()

allURLs = datasheet(myScenario, "epi_Jurisdiction")
runJuris = datasheet(myScenario, "epi_RuntimeJurisdiction")

chosenModel = list(set([x  for x in allURLs.Name if 'British Columbia' in x]))[2]

if runJuris.shape[0] != 0:
    chosenModel = str(runJuris.Jurisdiction[0])

theURL = pandas.unique(allURLs[allURLs.Name == chosenModel].Description)[0]

model = downloadModel(theURL)

fileName = '{}\\{}.pypm'.format(env.TransferDirectory, model.name)
model.save_file(fileName)

PARAMETER_ATTIBUTES = ['name', 'description', 'initial_value', 'parameter_min', 'parameter_max', 'mcmc_step']
Parameters = dict()

for key in PARAMETER_ATTIBUTES:
    Parameters[key] = []

Parameters['parameter_type'] = []
Parameters['prior_function'] = []
Parameters['prior_mean'] = []
Parameters['prior_second'] = []
Parameters['status'] = []

for param_name in model.parameters:

    param = model.parameters[param_name]

    for attr_name in PARAMETER_ATTIBUTES:
        Parameters[attr_name].append( getattr(param, attr_name) )

    Parameters['parameter_type'].append( tableType(param.parameter_type) )
    Parameters['prior_function'].append( tablePriorDist(param.prior_function) )

    if param.prior_function == None:
        Parameters['prior_mean'].append('')
        Parameters['prior_second'].append('')
    else:
        Parameters['prior_mean'].append(param.prior_parameters['mean'])
        Parameters['prior_second'].append(list(param.prior_parameters.values())[1])

    Parameters['status'].append( tableStatus(param.get_status()) )

ParameterFrame = pandas.DataFrame()

for key in Parameters.keys():
    ParameterFrame[key] = Parameters[key]

# recommended MCMC step is half of the standard deviation
variables_with_N_priors = list(ParameterFrame[ParameterFrame.prior_function == 'norm'].index)
ParameterFrame.loc[variables_with_N_priors, 'mcmc_step'] = 0.5*ParameterFrame.loc[variables_with_N_priors, 'prior_second']

variables_with_U_priors = list(ParameterFrame[ParameterFrame.prior_function == 'uniform'].index)
ParameterFrame.loc[variables_with_U_priors, 'mcmc_step'] = 1/numpy.sqrt(12)*ParameterFrame.loc[variables_with_U_priors, 'prior_second']

# get the empty data sheet
defaultParameters = datasheet(myScenario, "modelKarlenPypm_ParameterValues", empty=True)

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
saveDatasheet(myScenario, defaultParameters, "modelKarlenPypm_ParameterValues")

# download informnation of the Pypm file
pypmInfo = datasheet(myScenario, "modelKarlenPypm_ModelFile", empty=True)

pypmInfo.Region = [chosenModel]
pypmInfo.Name = [model.name]
pypmInfo.URL = [theURL]
pypmInfo.PypmFile = [fileName]
pypmInfo.DateTime = [datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")]

saveDatasheet(myScenario, pypmInfo.loc[0:0], "modelKarlenPypm_ModelFile")
