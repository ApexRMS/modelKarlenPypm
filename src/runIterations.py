#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import re
import pandas
import numpy
import datetime

from fetchModels import downloadModel, camelify, delta
from syncro import *

from pypmca.analysis.Optimizer import Optimizer

env = ssimEnvironment()
myScenario = scenario()

runControl = datasheet(myScenario, "epi_RunControl")
fileInfo = datasheet(myScenario, "modelKarlenPypm_ModelFile")
legalColumns = list(set(datasheet(myScenario, "epi_Variable").Name))

numIterations = runControl.MaximumIteration[0]
endDate = runControl.MaximumTimestep[0]
endDate = datetime.datetime.strptime(endDate, '%Y-%m-%d')

modelURL = str(fileInfo.URL[0])

'''
this is a stopgap - figure out how to find the length of the prediction from the data set we get from dataBcCdc
'''
simLength = 500

theModel = downloadModel(modelURL)

ParameterFrame = datasheet(myScenario, "modelKarlenPypm_ParameterValues").drop(columns=['ParameterValuesID'])

for index in range(0, ParameterFrame.shape[0]):

    name = ParameterFrame.Name.loc[index] # list(theModel.parameters.keys())[index]

    theModel.parameters[name].Type = ParameterFrame.Type[index]
    if ParameterFrame.Type[index] == 'int':
        theModel.parameters[name].set_value(int(ParameterFrame.Initial[index]))
    elif ParameterFrame.Type[index] == 'float':
        theModel.parameters[name].set_value(float(ParameterFrame.Initial[index]))
    else:
        print('*** PARAMETER TYPE FOR {} IS MISTYPED. CAN ONLY BE `int` or `float`, not {} ***'.format(name, ParameterFrame['name'][index]))
        continue

    theModel.parameters[name].description = ParameterFrame.Description[index]

    if ParameterFrame.Status[index] == 'fixed':
        theModel.parameters[name].set_fixed()
    elif ParameterFrame.Status[index] == 'variable':
        prior_func = ParameterFrame.PriorDist[index]
        # prior_params = dict()
        # Initial = 0
        if ParameterFrame.MCMCStep[index] == None:
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
            prior_func = None
            prior_params = None

        theModel.parameters[name].set_variable(prior_function=prior_func, prior_parameters=prior_params)

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

    myOptimiser = Optimizer(theModel, 'daily reported', realData.Value, DAYS_TO_FIT, CUMUL_RESET, SKIP_DATES_TEXT)
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

startDate0 = "2020-01-29"
startDate = datetime.datetime.strptime(startDate0, "%Y-%m-%d")

for iter in range(numIterations):

    tempTable = pandas.DataFrame()

    theModel.reset()
    theModel.generate_data(simLength)

    for pop in theModel.populations.keys():
        if camelify(pop) in legalColumns:
            tempTable[camelify(pop)] = theModel.populations[pop].history

    tempTable['Iteration'] = str(iter+1)
    tempTable['Timestep'] = [(startDate+datetime.timedelta(days=x)).strftime('%Y-%m-%d') for x in range(tempTable.shape[0])]
    # this name will camelify into "DailyInfected" as in the XML
    tempTable['DailyInfected'] = delta(tempTable.Infected)
    simDict[str(iter)] = tempTable

    meltedTable = pandas.melt(tempTable, id_vars=["Timestep", "Iteration"])
    simSummaryDict[str(iter)] = meltedTable


allData = pandas.concat(simDict.values(), ignore_index=False)
summaryData = pandas.concat(simSummaryDict.values(), ignore_index=True)

epiDatasummary = datasheet(myScenario, "epi_DataSummary", empty=True)
epiDatasummary.Iteration = summaryData.Iteration
epiDatasummary.Timestep = summaryData.Timestep
epiDatasummary.Variable = summaryData.variable
epiDatasummary.Value = summaryData.value
epiDatasummary.Jurisdiction = fileInfo.Region[0] # re.sub(' +', ' ', )
saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")

completeData = datasheet(myScenario, "modelKarlenPypm_CompleteData", empty=True)
allData.columns = [camelify(x) for x in allData.columns]
for varName in list(allData.columns.intersection(completeData.columns))+['DailyInfected']:
    completeData[varName] = allData[varName]
saveDatasheet(myScenario, completeData, "modelKarlenPypm_CompleteData")

# '''
# generate XML table columns quickly
# print('\n'.join(['<column name="{}" dataType="Double" displayName="{}"/>'.format(camelify(x), theModel.populations[x].description) for x in theModel.populations.keys()]))
# '''
