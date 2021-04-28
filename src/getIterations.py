#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import re
import pandas
import numpy
import datetime
import pypmca

import headerFile
from syncro import *

'''
     this transformer takes the chosen populations and fitted .pypm object from the getExpectations transformer and reuses them. here, the
     user can also choose new populations, but cannot refit or reparametrise the model object. user input is taken for the length of the
     simulation (ie., length of the projection) and the generate_data function is used to carry out the simulations

     Tables:

     1) RunControl - user given simulation length and number of iterations

     2) FittedModelFile - name and location of the fitted model output by the previous getExpectations transformer

     3) PypmcaModels - list of all the models available in the repository

     4) PopulationSelectionTable - list of the populations/model variables that the user wants to see here

     5) PypmcaCrosswalk - project-level crosswalk sheet mapping between Ssim and Karlen variable names
'''

env = ssimEnvironment()
myScenario = scenario()

# simulation length and number of iterations
runControl = datasheet(myScenario, "modelKarlenPypm_RunControl").iloc[0]

# name and location of the fitted model file from the previous transformer
modelInfo = datasheet(myScenario, "modelKarlenPypm_FittedModelFile").iloc[0]
theModel = pypmca.Model.open_file(modelInfo.File)

# the name of this model
THIS_MODEL = modelInfo.ModelDescrip

# a list of the all the models - used as a lut
pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels")
LUTRow = pypmcaModels[pypmcaModels.LUT == THIS_MODEL].iloc[0]

# default start and end dates of the simulations (start of the model and 28 days future, respectively)
startDate = theModel.t0
endDate = datetime.datetime.now().date() + datetime.timedelta(days=28)

# if the user gave an end date, use that instead
if not runControl.isnull().EndDate:
    endDate = datetime.datetime.strptime(runControl.EndDate, "%Y-%m-%d").date()

# calculating the length of the simulation
simLength = (endDate-startDate).days

# a list of the populations/model variables that the user wants to see
populationTable = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
showThesePops = list(populationTable.ShowThese.drop_duplicates())

# if a crosswalk file is supplied, use that, else use the scenario-level datasheet
if modelInfo.isnull().Crosswalk:
    pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
else:
    crosssWalk = pandas.read_csv(modelInfo.CrosswalkFile)

# lookup function for the Ssim standard name
def standardName(pop):
    if pop in list(pypmcaCrosswalk.Stock):
        return pypmcaCrosswalk[pypmcaCrosswalk.Stock == pop].Standard.iloc[0]
    else:
        return None

# inverse lookup for the Karlen population name
def stockName(pop):
    if pop in list(pypmcaCrosswalk.Standard):
        return pypmcaCrosswalk[pypmcaCrosswalk.Standard == pop].Stock.iloc[0]
    else:
        return None

# dictionary to hold the time series
simSummaryDict = dict()

# standard error to be printed if a variable name can't be lookmed up
def standardError(variable):
    return '*** ERROR: requested population {} has no equivalent \
        in the Pypmca model object. Please verify either the \
        crosswalk file used or the standardising funtion \
        "getFancyName" in <headerFile.py> ***'.format(variable)

# each iteration
for iter in range(int(runControl.Iterations)):

    # print progress
    print('\t*** interation {} ***'.format(iter))

    # hold the results of this iteration
    tempTable = pandas.DataFrame()

    # reset the model and generate results
    theModel.reset()
    theModel.generate_data(simLength)

    # for each population that the user wanted to see
    for standardName in showThesePops:

        # temp list for the time series
        timeSeries = []

        # get Karlen's name for the population
        karlenName = stockName(standardName)

        # if the name exists, get the time series
        if karlenName in theModel.populations.keys():
            timeSeries = theModel.populations[karlenName].history

        else:
            # if the current name is one that we've manually added to the crosswalk file

            # it it's a daily variable get the name of its cumulative version
            if 'daily' in karlenName:
                karlenStub = karlenName.replace('daily', '').strip()

                # if the cumulative series can't be found, there may be a problem with the
                if karlenStub not in theModel.populations.keys():
                    print(standardError(karlenName))
                    continue

                # else, get the cumulative data and run it through a diff function
                timeSeries = headerFile.delta(theModel.populations[karlenStub].history)

            # if the missing variable is cumulative, get the name of the corresponding daily variable
            elif 'cumulative' in karlenName:
                karlenStub = karlenName.replace('daily', '').strip()

                # if the daily version can't be found, then there may be a problem with the crosswalk file
                if karlenStub not in theModel.populations.keys():
                    print(standardError(karlenName))
                    continue

                # else, get the cumsum
                timeSeries = numpy.cumsum(theModel.populations[karlenStub].history)

        # if at least 10% of the values in the dataset are unique, accept the series
        if headerFile.movementThreshold(timeSeries, 0.1):
            tempTable[ standardName ] = timeSeries

    # add the number of the iteration to the set, and add a series for the date of each step
    tempTable['Iteration'] = str(iter+1)
    tempTable['Timestep'] = [startDate+datetime.timedelta(days=x) for x in range(tempTable.shape[0])]

    # melt the table to get unique population/variable rows and add the data to the dictionary
    meltedTable = pandas.melt(tempTable, id_vars=["Timestep", "Iteration"])
    simSummaryDict[str(iter)] = meltedTable

# concatenate all the data, rename the columns and fill the missing infoemation
epiDatasummary = pandas.concat(simSummaryDict.values(), ignore_index=True).dropna()
epiDatasummary.columns = map(headerFile.camelify, epiDatasummary.columns)
epiDatasummary['Jurisdiction'] = '{} - {}'.format(LUTRow.Country, LUTRow.Region)
epiDatasummary['TransformerID'] = 'modelKarlenPypm_C_getIterations'

# save the data
saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
