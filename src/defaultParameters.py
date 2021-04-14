#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import pandas
import numpy
import datetime

from syncro import *
from headerFile import *

env = ssimEnvironment()
myScenario = scenario()

modelChoice = datasheet(myScenario, "modelKarlenPypm_ModelChoices").drop(columns=['InputID']).iloc[0]
modelsAvail = datasheet(myScenario, "modelKarlenPypm_PypmcaJuris").drop(columns=['InputID'])

chosenModel = modelChoice.Location
theURL = modelsAvail[ modelsAvail.Name == chosenModel ].URL.iloc[0]

varNameFile = modelChoice.FileName
renamingMap = pandas.read_csv(varNameFile).drop_duplicates()
renamingMap['Show'] = 'No'
renamingMap.loc[
    renamingMap.Standard.isin([
        'Cases - Daily', 'Cases - Cumulative',
        'Mortality - Daily', 'Mortality - Cumulative',
        'Infected - Daily', 'Infected - Cumulative',
        'Infected (Variants) - Daily', 'Infected (Variants)  - Cumulative',
        'Cases (Variants) - Daily', 'Cases (Variants) - Cumulative',
        'Hospitalized - Cumulative',
        'In Hospital - Daily',
        'In ICU - Daily',
        'ICU Admissions - Cumulative'
    ]),
    'Show'
] = 'Yes'
renamingMap = renamingMap[['Show', 'Standard', 'Description', 'Stock']]

saveDatasheet(myScenario, renamingMap, 'modelKarlenPypm_PopulationSelectionTable')

epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction").drop(columns=['JurisdictionID'])

if chosenModel not in list(epiJurisdiction.Name):
    saveDatasheet(myScenario,
        pandas.DataFrame.from_dict({'Name' : [chosenModel], 'Description' : ['']}),
        'epi_Jurisdiction'
    )

model = downloadModel(theURL)

fileName = '{}\\{}.pypm'.format(env.TransferDirectory, model.name)
model.save_file(fileName)

PARAMETER_ATTIBUTES = ['name', 'description', 'initial_value', 'parameter_min', 'parameter_max', 'mcmc_step']
Parameters = dict()

for key in PARAMETER_ATTIBUTES:
    Parameters[key] = []

Parameters['prior_function'] = []
Parameters['prior_mean'] = []
Parameters['prior_second'] = []
Parameters['status'] = []

for param_name in model.parameters:

    param = model.parameters[param_name]

    for attr_name in PARAMETER_ATTIBUTES:
        Parameters[attr_name].append( getattr(param, attr_name) )

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
varsWithNPriors = list(ParameterFrame[ParameterFrame.prior_function == 'norm'].index)
ParameterFrame.loc[varsWithNPriors, 'mcmc_step'] = 0.5*ParameterFrame.loc[varsWithNPriors, 'prior_second']

varsWithUPriors = list(ParameterFrame[ParameterFrame.prior_function == 'uniform'].index)
ParameterFrame.loc[varsWithUPriors, 'mcmc_step'] = 1/numpy.sqrt(12)*ParameterFrame.loc[varsWithUPriors, 'prior_second']

# get the empty data sheet
defaultParameters = datasheet(myScenario, "modelKarlenPypm_ParameterValues", empty=True)

defaultParameters.Name = ParameterFrame.name
defaultParameters.Description = ParameterFrame.description
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
pypmInfo = datasheet(myScenario, "modelKarlenPypm_ModelFile", empty=True).drop(columns=['InputID'])

pypmInfo.Region = [chosenModel]
pypmInfo.Name = [model.name]
pypmInfo.URL = [theURL]
pypmInfo.PypmFile = [fileName]
pypmInfo.DateTime = [datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")]

saveDatasheet(myScenario, pypmInfo.loc[0:0], "modelKarlenPypm_ModelFile")
