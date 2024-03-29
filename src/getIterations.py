#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

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
    tempTable['Timestep'] = [startDate + datetime.timedelta(days=x) for x in range(tempTable.shape[0])]

    meltedTable = pandas.melt(tempTable, id_vars=["Timestep", "Iteration"])
    simSummaryDict[str(iter)] = meltedTable

epiDatasummary = pandas.concat(simSummaryDict.values(), ignore_index=True).dropna()
epiDatasummary.columns = map(camelify, epiDatasummary.columns)
epiDatasummary['Jurisdiction'] = LUTRow.Jurisdiction
epiDatasummary['TransformerID'] = 'modelKarlenPypm_C_getIterations'

epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction")
if LUTRow.Jurisdiction not in epiJurisdiction.Name:
    saveDatasheet(
        myScenario,
        pandas.DataFrame({'Name':[LUTRow.Jurisdiction], 'Description':['']}),
        "epi_Jurisdiction"
    )


# Save the model choices datasheet back to the result scenario
saveDatasheet(
    myScenario,
    datasheet(myScenario, "modelKarlenPypm_ModelChoices").iloc[0].to_frame(0).T,
    "modelKarlenPypm_ModelChoices")

# Append to input data
epiDatasummary = datasheet(myScenario, "epi_DataSummary").drop(columns=['DataSummaryID']).append(epiDatasummary)
epiDatasummary.AgeMin = epiDatasummary.AgeMin.astype(pandas.Int64Dtype())
epiDatasummary.AgeMax = epiDatasummary.AgeMax.astype(pandas.Int64Dtype())
epiDatasummary.Iteration = numpy.floor(pandas.to_numeric(epiDatasummary.Iteration)).astype('Int64')

saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
