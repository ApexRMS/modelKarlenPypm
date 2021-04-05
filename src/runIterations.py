#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import re
import pandas
import numpy
import datetime

from headerFile import *
from syncro import *

from pypmca.analysis.Optimizer import Optimizer

env = ssimEnvironment()
myScenario = scenario()

modelFileInfo = datasheet(myScenario, "modelKarlenPypm_ModelFile")
runParams = datasheet(myScenario, "modelKarlenPypm_FittingParams")

showThesePops = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
showThesePops = showThesePops[showThesePops.Show=='Yes'].drop(columns=['PopulationSelectionTableID', 'Show', 'Description'])
showThesePops = list(showThesePops.Standard)


epiVariable = datasheet(myScenario, "epi_Variable").drop(columns=['VariableID'])
weNeedToAdd = {}; counter = 0
for name in showThesePops:
    if name not in list(epiVariable.Name):
        weNeedToAdd[counter] = {'Name' : name, 'Description' : ''}
        counter += 1
addThisDict = pandas.DataFrame.from_dict(weNeedToAdd, orient='index')

if not addThisDict.empty:
    saveDatasheet(myScenario, addThisDict.drop_duplicates(), "epi_Variable")
    
renamingMap = pandas.read_csv(list(datasheet(myScenario, "modelKarlenPypm_ModelChoices").FileName)[0])

def standardName(pop):
    if pop in list(renamingMap.Stock):
        return list(renamingMap[renamingMap.Stock == pop].Standard)[0]
    else:
        return None
    
originalPopNames = list(renamingMap[renamingMap.Standard.isin(showThesePops)].Stock)

startDate = datetime.datetime(2020, 1, 29, 0, 0)
endDate = list(runParams.EndDate)[0]
endDate = datetime.datetime.strptime(endDate, '%Y-%m-%d')

simLength = (endDate-startDate).days

modelURL = str(modelFileInfo.URL[0])

theModel = downloadModel(modelURL)

ParameterFrame = datasheet(myScenario, "modelKarlenPypm_ParameterValues").drop(columns=['ParameterValuesID'])

for index in range(0, ParameterFrame.shape[0]):

    name = ParameterFrame.Name.loc[index]

    theModel.parameters[name].description = ParameterFrame.Description[index]

    if ParameterFrame.Status[index] == 'fixed':
        theModel.parameters[name].set_fixed()

    elif ParameterFrame.Status[index] == 'variable':

        priorFunc = ParameterFrame.PriorDist[index]

        if priorFunc == '':
            print('\t parameter {} set to variable but prior function not set (currently {}). no changes made, please adjust and rerun ***'.format(name, priorFunc))
            continue

        prior_params = dict()

        if (ParameterFrame.MCMCStep[index] == None) or (str(ParameterFrame.MCMCStep[0]).lower() == 'nan'):
            print('\t*** mcmc_step not given for variable parameter {}. Defaulting to 1/2 of one standard deviation. ***'.format(name))

            if ParameterFrame.PriorDist[index] == 'uniform':
                prior_params = {'mean': ParameterFrame.PriorMean[index], 'half_width' : ParameterFrame.PriorSecond[index]}
                # var=(b-a)/12, hw=(b-a)/2, so that sd=hw/sqrt(6)
                theModel.parameters[name].mcmc_step = 0.5*ParameterFrame.PriorSecond[index]/numpy.sqrt(6)

            elif ParameterFrame.PriorDist[index] == 'normal':
                prior_params = {'mean' : ParameterFrame.PriorMean[index], 'sigma' : ParameterFrame.PriorSecond[index]}
                # mcmc default step half the standard deviation
                theModel.parameters[name].mcmc_step = 0.5*ParameterFrame.PriorSecond[index]

            else:
                print('\t*** variable parameter {} has no prior function or parameters supplied. ***'.format(name))
                priorFunc = None
                prior_params = None

        theModel.parameters[name].set_variable(prior_function=priorFunc, prior_parameters=prior_params)

    else:
        print('*** STATUS FOR THE PARAMETER {} IS MISTYPED. CAN ONLY BE `fixed` or `variable`, not {} ***'.format(name, ParameterFrame['name'][index]))

    theModel.parameters[name].set_min(ParameterFrame.Min[index])
    theModel.parameters[name].set_max(ParameterFrame.Max[index])

    theModel.parameters[name].reset()

theModel.boot()

# '''
# this is the fitting step that can be completed using data from the dataBcCdc package.
# I'll make a test for emptiness here and skip this code until the dataBcCdc gets patched up
# '''
# realData = datasheet(myScenario, "epi_DataSummary")

# if not realData.empty:

#     myOptimiser = Optimizer(
#         theModel,
#         'daily reported',
#         realData.Value,
#         [int(runParams.StartFit[0]), int(runParams.EndFit[0])],
#         bool(runParams.CumulReset[0]),
#         str(runParams.SkipDatesText[0])
#     )
#     popt, pcov = myOptimiser.fit()

#     for parName in myOptimiser.variable_names:
#         print('\t'+parName, '= {0:0.3f}'.format(theModel.parameters[parName].get_value()))

#     for index in range(len(popt)):
#         name = myOptimiser.variable_names[index]
#         value = popt[index]
#         theModel.parameters[name].set_value(value)
#         theModel.parameters[name].new_initial()

'''
finally, the iteration step for generating the data
'''
simDict = dict()
simSummaryDict = dict()

for iter in range(runParams.Iterations.at[0]):

    tempTable = pandas.DataFrame()

    theModel.reset()
    theModel.generate_data(simLength)

    for pop in theModel.populations.keys():
        
        if pop in originalPopNames:
            
            currentCol = theModel.populations[pop].history
            
            if movementThreshold(currentCol, 0.3):
                
                tempTable[ standardName(pop) ] = theModel.populations[pop].history

    tempTable['Iteration'] = str(iter+1)
    tempTable['Timestep'] = [(startDate+datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(tempTable.shape[0])]
    
    theDailiesAdded = ['infected', 'deaths', 'recovered', 'smptomatic', 'infected_v', 'reported_v', 'removed', 'removed_v']
    
    for metric in theDailiesAdded:
        if 'daily {}' .format(metric) in originalPopNames:
            displayName = getFancyName(metric)
            tempTable['{} - Daily'.format( displayName )] = delta(theModel.populations[metric].history)

    meltedTable = pandas.melt(tempTable, id_vars=["Timestep", "Iteration"])
    simSummaryDict[str(iter)] = meltedTable

summaryData = pandas.concat(simSummaryDict.values(), ignore_index=True)

epiDatasummary = datasheet(myScenario, "epi_DataSummary", empty=True)
epiDatasummary.Iteration = summaryData.Iteration
epiDatasummary.Timestep = summaryData.Timestep
epiDatasummary.Variable = summaryData.variable
epiDatasummary.Value = summaryData.value
epiDatasummary.Jurisdiction = modelFileInfo.Region.at[0]
epiDatasummary.TransformerID = 'modelKarlenPypm_runIterations'
saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
