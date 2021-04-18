#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

from matplotlib import pyplot as plt

import re
import pandas
import numpy
import datetime

from headerFile import *
from syncro import *

from pypmca.analysis.Optimizer import Optimizer

env = ssimEnvironment()
myScenario = scenario()

modelChoices = datasheet(myScenario, "modelKarlenPypm_ModelChoices").iloc[0]

THIS_MODEL = modelChoices.ModelName

pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels")
LUTRow = pypmcaModels[pypmcaModels.LUT == THIS_MODEL].iloc[0]
modelURL = LUTRow.URL
theModel = downloadModel(modelURL)

parameterFrame = datasheet(myScenario, "modelKarlenPypm_ParameterValues")
parameterFrame = parameterFrame[parameterFrame.Model == THIS_MODEL].reset_index()

for index in range(0, parameterFrame.shape[0]):

    name = parameterFrame.Name.loc[index]

    theModel.parameters[name].description = parameterFrame.Description[index]

    theModel.parameters[name].set_min(parameterFrame.ParameterMin[index])
    theModel.parameters[name].set_max(parameterFrame.ParameterMax[index])

    if theModel.parameters[name].parameter_type == 'int':
        theModel.parameters[name].set_value(int( parameterFrame.InitialValue[index] ))
    elif theModel.parameters[name].parameter_type == 'float':
        theModel.parameters[name].set_value( parameterFrame.InitialValue[index] )

    theModel.parameters[name].new_initial_value()


    if parameterFrame.Status[index] == 'fixed':
        theModel.parameters[name].set_fixed()

    elif parameterFrame.Status[index] == 'variable':

        priorFunc = parameterFrame.PriorFunction[index]

        if priorFunc == '':
            print('\t parameter {} set to variable but prior function not set (currently {}). no changes made, please adjust and rerun ***'.format(name, priorFunc))
            continue

        prior_params = dict()

        if parameterFrame.PriorFunction[index] == 'uniform':
            prior_params = {'mean': parameterFrame.PriorMean[index], 'half_width' : parameterFrame.PriorSecond[index]}

        elif parameterFrame.PriorFunction[index] == 'normal':
            prior_params = {'mean' : parameterFrame.PriorMean[index], 'sigma' : parameterFrame.PriorSecond[index]}

        theModel.parameters[name].set_variable(prior_function=priorFunc, prior_parameters=prior_params)

    else:
        print('*** STATUS FOR THE PARAMETER {} IS MISTYPED. CAN ONLY BE `fixed` or `variable`, not {} ***'.format(name, parameterFrame['name'][index]))

    theModel.parameters[name].reset()

theModel.boot()

startDate = theModel.t0
endDate = datetime.datetime.now().date() + datetime.timedelta(days=28)

simLength = (endDate-startDate).days

print("fitting step")

realData = datasheet(myScenario, "epi_DataSummary")

if not realData.empty:

    startDate = theModel.t0

    realData.Timestep = realData.Timestep.apply(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date())
    realData = realData[realData.Timestep >= startDate]

    simLength = (endDate-startDate).days

    fittingVar = modelChoices.FitVariable

    if fittingVar in set(realData.Variable):
        realData = realData[realData.Variable == fittingVar]
    else:
        realData = realData[realData.Variable == 'Cases - Cumulative']
        fittingVar = 'Cases - Cumulative'

    fittingString = ''

    if 'cumulative' in modelChoices.FitVariable.lower():
        fittingString += 'total '
    elif 'daily' in modelChoices.FitVariable.lower():
        fittingString += 'daily '

    if 'cases' in modelChoices.FitVariable.lower():
        fittingString += 'reported'
    elif 'infected' in modelChoices.FitVariable.lower():
        fittingString += 'infected'

    cumulReset = True if modelChoices.CumulReset == True else False

    startFitDay = 1 if numpy.isnan(modelChoices.StartFit) else int(modelChoices.StartFit)
    endFitDay = realData.shape[0] if numpy.isnan(modelChoices.EndFit) else int(modelChoices.EndFit)

    myOptimiser = Optimizer(
        theModel,
        fittingString,
        realData.Value.values,
        [startFitDay, endFitDay],
        cumulReset,
        str(modelChoices.SkipDatesText[0])
    )
    popt, pcov = myOptimiser.fit()

    fitVars = datasheet(myScenario, "modelKarlenPypm_FitVariables", empty=True)

    for index in range(len(popt)):
        name = myOptimiser.variable_names[index]
        value = popt[index]
        fitVars = fitVars.append({'Variable':name, 'Value':value}, ignore_index=True)
        theModel.parameters[name].set_value(value)

    saveDatasheet(myScenario, fitVars, "modelKarlenPypm_FitVariables")

modelFileName = '{}\\{}_fitted.pypm'.format(env.TempDirectory, theModel.name)
theModel.save_file(modelFileName)

fittedModelFile = datasheet(myScenario, "modelKarlenPypm_FittedModelFile")
fittedModelFile.File = [modelFileName]
fittedModelFile.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
fittedModelFile.ModelDescrip = [THIS_MODEL]
fittedModelFile.Crosswalk = [modelChoices.CrosswalkFile]
saveDatasheet(myScenario, fittedModelFile, "modelKarlenPypm_FittedModelFile")

print("getting the expectations")

populationTable = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
showThesePops = list(populationTable.ShowThese.drop_duplicates())

if numpy.isnan(modelChoices.CrosswalkFile):
    pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
else:
    crosssWalk = pandas.read_csv(modelChoices.CrosswalkFile)

def standardName(pop):
    if pop in list(pypmcaCrosswalk.Stock):
        return pypmcaCrosswalk[pypmcaCrosswalk.Stock == pop].Standard.iloc[0]
    else:
        return None

def stockName(pop):
    if pop in list(pypmcaCrosswalk.Standard):
        return pypmcaCrosswalk[pypmcaCrosswalk.Standard == pop].Stock.iloc[0]
    else:
        return None

simDict = dict()
simSummaryDict = dict()

def standardError(variable):
    return '*** ERROR: requested population {} has no equivalent \
        in the Pypmca model object. Please verify either the \
        crosswalk file used or the standardising funtion \
        "getFancyName" in <headerFile.py> ***'.format(variable)


theModel.reset()
theModel.evolve_expectations(simLength)

tempTable = pandas.DataFrame()

for standardName in showThesePops:

    karlenName = stockName(standardName)

    if karlenName in theModel.populations.keys():
        timeSeries = theModel.populations[karlenName].history

    else:

        if 'daily' in karlenName:
            karlenStub = karlenName.replace('daily', '').strip()

            if karlenStub not in theModel.populations.keys():
                print(standardError(karlenName))
                continue

            timeSeries = delta(theModel.populations[karlenStub].history)

        elif 'cumulative' in karlenName:
            karlenStub = karlenName.replace('daily', '').strip()

            if karlenStub not in theModel.populations.keys():
                print(standardError(karlenName))
                continue

            timeSeries = numpy.cumsum(theModel.populations[karlenStub].history)

    if movementThreshold(timeSeries, 0.1):
        tempTable[ standardName ] = timeSeries

print("expectations done")

tempTable['Iteration'] = 1
tempTable['Timestep'] = [startDate+datetime.timedelta(days=x) for x in range(tempTable.shape[0])]

meltedTable = pandas.melt(tempTable, id_vars=["Timestep", "Iteration"])
simSummaryDict[str(iter)] = meltedTable

epiDatasummary = pandas.concat(simSummaryDict.values(), ignore_index=True).dropna()
epiDatasummary.columns = map(camelify, epiDatasummary.columns)
epiDatasummary['Jurisdiction'] = LUTRow.Jurisdiction
epiDatasummary['TransformerID'] = 'modelKarlenPypm_B_getExpectations'

epiVariable = datasheet(myScenario, "epi_Variable")
varList = epiDatasummary.Variable.drop_duplicates()
descripList = map(
    lambda x: pypmcaCrosswalk[pypmcaCrosswalk.Standard == x].Description.iloc[0],
    varList
)
variablesHere = pandas.DataFrame({'Name' : varList, 'Description' : descripList})
saveDatasheet(myScenario, dataFrameDifference(epiVariable, variablesHere, 'Name'), "epi_Variable")

epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction")
if LUTRow.Jurisdiction not in epiJurisdiction.Name:
    saveDatasheet(
        myScenario,
        pandas.DataFrame({'Name':[LUTRow.Jurisdiction], 'Description':['']}),
        "epi_Jurisdiction"
    )


saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
