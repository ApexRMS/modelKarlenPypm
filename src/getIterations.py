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
     user can also choose new populations, but cannot refit or reparameterise the model object. user input is taken for the length of the
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
the_model = pypmca.Model.open_file(modelInfo.File)

# the name of this model
THIS_MODEL = modelInfo.ModelDescrip

# a list of the all the models - used as a lut
pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels")
LUTRow = pypmcaModels[pypmcaModels.LUT == THIS_MODEL].iloc[0]

# default start and end dates of the simulations (start of the model and 28 days future, respectively)
start_date = the_model.t0
end_date = datetime.datetime.now().date() + datetime.timedelta(days=28)

# if the user gave an end date, use that instead
if not runControl.isnull().EndDate:
    end_date = datetime.datetime.strptime(runControl.EndDate, "%Y-%m-%d").date()

# calculating the length of the simulation
simulation_length = (end_date-start_date).days

# a list of the populations/model variables that the user wants to see
populationTable = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
show_these_populations = list(populationTable.ShowThese.drop_duplicates())

# if a crosswalk file is supplied, use that, else use the scenario-level datasheet
if modelInfo.isnull().Crosswalk:
    pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
else:
    crosssWalk = pandas.read_csv(modelInfo.CrosswalkFile)

# lookup function for the Ssim standard name
def standard_Ssim_name(pop):
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
simulation_output_dict = dict()

# standard error to be printed if a variable name can't be looked up
def standardError(variable):
    return '*** ERROR: requested population {} has no equivalent \
        in the Pypmca model object. Please verify either the \
        crosswalk file used or the standardising function \
        "getFancyName" in <headerFile.py> ***'.format(variable)

# each iteration
for iter in range(int(runControl.Iterations)):

    # print progress
    print('\t*** iteration {} ***'.format(iter))

    # hold the results of this iteration
    temp_results_table = pandas.DataFrame()

    # reset the model and generate results
    the_model.reset()
    the_model.generate_data(simulation_length)

    # for each population that the user wanted to see
    for standard_Ssim_name in show_these_populations:

        # temp list for the time series
        times_series = []

        # get Karlen's name for the population
        karlen_population_name = stockName(standard_Ssim_name)

        # if the name exists, get the time series
        if karlen_population_name in the_model.populations.keys():
            times_series = the_model.populations[karlen_population_name].history

        else:
            # if the current name is one that we've manually added to the crosswalk file

            # it it's a daily variable get the name of its cumulative version
            if 'daily' in karlen_population_name:
                karlen_stub = karlen_population_name.replace('daily', '').strip()

                # if the cumulative series can't be found, there may be a problem with the
                if karlen_stub not in the_model.populations.keys():
                    print(standardError(karlen_population_name))
                    continue

                # else, get the cumulative data and run it through a diff function
                times_series = headerFile.delta(the_model.populations[karlen_stub].history)

            # if the missing variable is cumulative, get the name of the corresponding daily variable
            elif 'cumulative' in karlen_population_name:
                karlen_stub = karlen_population_name.replace('daily', '').strip()

                # if the daily version can't be found, then there may be a problem with the crosswalk file
                if karlen_stub not in the_model.populations.keys():
                    print(standardError(karlen_population_name))
                    continue

                # else, get the cumsum
                times_series = numpy.cumsum(the_model.populations[karlen_stub].history)

        # if at least 10% of the values in the data set are unique, accept the series
        if headerFile.movementThreshold(times_series, 0.1):
            temp_results_table[ standard_Ssim_name ] = times_series

    # add the number of the iteration to the set, and add a series for the date of each step
    temp_results_table['Iteration'] = str(iter+1)
    temp_results_table['Timestep'] = [start_date+datetime.timedelta(days=x) for x in range(temp_results_table.shape[0])]

    # melt the table to get unique population/variable rows and add the data to the dictionary
    melted_table = pandas.melt(temp_results_table, id_vars=["Timestep", "Iteration"])
    simulation_output_dict[str(iter)] = melted_table

# concatenate all the data, rename the columns and fill the missing information
epiDatasummary = pandas.concat(simulation_output_dict.values(), ignore_index=True).dropna()
epiDatasummary.columns = map(headerFile.camelify, epiDatasummary.columns)
epiDatasummary['Jurisdiction'] = '{} - {}'.format(LUTRow.Country, LUTRow.Region)
epiDatasummary['TransformerID'] = 'modelKarlenPypm_C_getIterations'

# save the data
saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
