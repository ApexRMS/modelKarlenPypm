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

runControl = datasheet(myScenario, "modelKarlenPypm_RunControl").iloc[0]

modelInfo = datasheet(myScenario, "modelKarlenPypm_FittedModelFile").iloc[0]
theModel = pypmca.Model.open_file(modelInfo.File)

THIS_MODEL = modelInfo.ModelDescrip

pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels")
LUTRow = pypmcaModels[pypmcaModels.LUT == THIS_MODEL].iloc[0]

startDate = theModel.t0
endDate = datetime.datetime.now().date() + datetime.timedelta(days=28)

if not numpy.isnan(runControl.EndDate):
    endDate = datetime.datetime.strptime(runControl.EndDate, "%Y-%m-%d").date()

simLength = (endDate-startDate).days

populationTable = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
showThesePops = list(populationTable.ShowThese.drop_duplicates())

if numpy.isnan(modelInfo.Crosswalk):
    pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
else:
    crosssWalk = pandas.read_csv(modelInfo.CrosswalkFile)

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


for iter in range(int(runControl.Iterations)):

    tempTable = pandas.DataFrame()

    theModel.reset()
    theModel.generate_data(simLength)

    timeSeries = []

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


    tempTable['Iteration'] = str(iter+1)
    tempTable['Timestep'] = [startDate+datetime.timedelta(days=x) for x in range(tempTable.shape[0])]

    meltedTable = pandas.melt(tempTable, id_vars=["Timestep", "Iteration"])
    simSummaryDict[str(iter)] = meltedTable

epiDatasummary = pandas.concat(simSummaryDict.values(), ignore_index=True).dropna()
epiDatasummary.columns = map(camelify, epiDatasummary.columns)
epiDatasummary['Jurisdiction'] = LUTRow.Jurisdiction
epiDatasummary['TransformerID'] = 'modelKarlenPypm_C_runIterations'

# epiVariable = datasheet(myScenario, "epi_Variable")
# varList = epiDatasummary.Variable.drop_duplicates()
# descripList = map(
#     lambda x: pypmcaCrosswalk[pypmcaCrosswalk.Standard == x].Description.iloc[0],
#     varList
# )
# variablesHere = pandas.DataFrame({'Name' : varList, 'Description' : descripList})
# saveDatasheet(myScenario, dataFrameDifference(epiVariable, variablesHere, 'Name'), "epi_Variable")

epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction")
if LUTRow.Jurisdiction not in epiJurisdiction.Name:
    saveDatasheet(
        myScenario,
        pandas.DataFrame({'Name':[LUTRow.Jurisdiction], 'Description':['']}),
        "epi_Jurisdiction"
    )

saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
