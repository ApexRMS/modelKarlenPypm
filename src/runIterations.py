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

runControl = datasheet(myScenario, "epi_RunControl")
modelFileInfo = datasheet(myScenario, "modelKarlenPypm_ModelFile")
fittingParams = datasheet(myScenario, "modelKarlenPypm_FittingParams")

showThesePops = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
showThesePops = showThesePops[showThesePops.Show=='Yes'].drop(columns=['PopulationSelectionTableID', 'Show', 'Description'])

def standardName(string):
    if pop in list(showThesePops.StockName):
        return list(showThesePops[showThesePops.StockName == pop].StandardName)[0]
    else:
        return None

numIterations = 2 # 50

startDate = datetime.date(2020, 1, 29)
endDate = datetime.date.today() + datetime.timedelta(days=15)

simLength = (endDate-startDate).days

if(runControl.shape[0] != 0):
    numIterations = runControl.MaximumIteration[0]
    endDate = runControl.MaximumTimestep[0]
    endDate = datetime.datetime.strptime(endDate, '%Y-%m-%d')

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

'''
this is the fitting step that can be completed using data from the dataBcCdc package.
I'll make a test for emptiness here and skip this code until the dataBcCdc gets patched up
'''
realData = datasheet(myScenario, "epi_DataSummary")

if not realData.empty:

    myOptimiser = Optimizer(
        theModel,
        'daily reported',
        realData.Value,
        [int(fittingParams.StartFit[0]), int(fittingParams.EndFit[0])],
        bool(fittingParams.CumulReset[0]),
        str(fittingParams.SkipDatesText[0])
    )
    popt, pcov = myOptimiser.fit()

    for parName in myOptimiser.variable_names:
        print('\t'+parName, '= {0:0.3f}'.format(theModel.parameters[parName].get_value()))

    for index in range(len(popt)):
        name = myOptimiser.variable_names[index]
        value = popt[index]
        theModel.parameters[name].set_value(value)
        theModel.parameters[name].new_initial()

'''
finally, the iteration step for generating the data
'''
simDict = dict()
simSummaryDict = dict()

legalColumns = list(showThesePops.StockName) 
legalColumns += [getFancyName(x) for x in legalColumns]

for iter in range(numIterations):

    tempTable = pandas.DataFrame()

    theModel.reset()
    theModel.generate_data(simLength)

    for pop in theModel.populations.keys():
        
        if pop in legalColumns:
            
            currentCol = theModel.populations[pop].history
            
            if movementThreshold(currentCol, 0.3):
                
                tempTable[ standardName(pop) ] = theModel.populations[pop].history

    tempTable['Iteration'] = str(iter+1)
    tempTable['Timestep'] = [(startDate+datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(tempTable.shape[0])]
    
    theDailiesAdded = ['infected', 'deaths', 'recovered', 'smptomatic', 'infected_v', 'reported_v', 'removed', 'removed_v']
    
    for metric in theDailiesAdded:
        if 'daily {}' .format(metric) in legalColumns:
            displayName = getFancyName(metric)
            tempTable['Daily - {}'.format( displayName )] = delta(theModel.populations[metric].history)

    meltedTable = pandas.melt(tempTable, id_vars=["Timestep", "Iteration"])
    simSummaryDict[str(iter)] = meltedTable

summaryData = pandas.concat(simSummaryDict.values(), ignore_index=True)

epiDatasummary = datasheet(myScenario, "epi_DataSummary", empty=True)
epiDatasummary.Iteration = summaryData.Iteration
epiDatasummary.Timestep = summaryData.Timestep
epiDatasummary.Variable = summaryData.variable
epiDatasummary.Value = summaryData.value
epiDatasummary.Jurisdiction = modelFileInfo.Region[0]
saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")

# completeData = datasheet(myScenario, "modelKarlenPypm_CompleteData", empty=True)
# allData.columns = [camelify(x) for x in allData.columns]
# for varName in list(allData.columns.intersection(completeData.columns))+['DailyInfected']:
#     completeData[varName] = allData[varName]
# saveDatasheet(myScenario, completeData, "modelKarlenPypm_CompleteData")

# dataFilename = '{}\\totalData_{}.csv'.format(env.TempDirectory, modelFileInfo.Name[0])

# # completeData.to_csv(dataFilename)

# # '''
# # generate XML table columns quickly
# print()
# # print('\n'.join(['<column name="{}" dataType="Double" displayName="{}" isOptional="True"/>'.format(camelify(x), theModel.populations[x].description.title()) for x in theModel.populations.keys()]))
# # '''
