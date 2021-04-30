#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))


'''
    this transformer takes user input and

    1) gets the requested .pypm model object (specified by region, version, sex and age range)

    2) fits the downloaded model to the data supplied. If no data is dragged in as a dependency, the fitting steps
        are skipped. fitting is done within the range of time steps specified by the user, to a user-chosen variable.
        for instance, we can fit the model to 'Cases - Cumulative' from day 37 until the end of the series, skipping the
        days 20 and 30-41 because of weird reporting anomalies in that region. the parameters that are fit are the ones
        specified as status 'variable' in the *_ParameterValues sheet. the posterior values are then assigned to the model
        and output to a file in the TransferDirectory.

    3) get the expected values of the populations (model variables) choden by the user; simulation data will be gathered in
        the getIterations transformer. this is done by calculating the number of time steps between the start of the time of
        the model and the projection end date specified by the user. the function .evolve_expectations is used
'''

import re
import pandas
import numpy
import datetime

import headerFile
from syncro import *

# the model fit (leasst squares) is done with this 'Optimiser' object
from pypmca.analysis.Optimizer import Optimizer

env = ssimEnvironment()
myScenario = scenario()

# user input (model name, fitting parameter, etc)
modelChoices = datasheet(myScenario, "modelKarlenPypm_ModelChoices").iloc[0]

# the name/handle of this model
THIS_MODEL = modelChoices.ModelName

#sheet giving the list of models - will be used as a lut
pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels")
# get the corresponding (single) row in the lut
LUTRow = pypmcaModels[pypmcaModels.LUT == THIS_MODEL].iloc[0]
# get the URL of the model and download the .pypm object
modelURL = LUTRow.URL
theModel = headerFile.downloadModel(modelURL)

'''
    in the options (in line with Karlen's online ipypm interface), the user is allowed to change the default
    (pre-supplied by Karlen) parameter values. after the values have been changed, then all the new parameters
    (whether changed or not, that would be hard to keep track of, KISS) are re-added to the model and then the
    object is rebooted (recalibrated to find initial population values; this  is described by Karlen in the
    pypmca package files) and written to a file
'''

# get the user-supplied parameter values from the datasheet
parameterFrame = datasheet(myScenario, "modelKarlenPypm_ParameterValues")
# since the values for all models are specified in the same sheet, be sure only to pull the ones for the specifiec model
parameterFrame = parameterFrame[parameterFrame.Model == THIS_MODEL].reset_index()

# for each parameter
for index in range(0, parameterFrame.shape[0]):

    # set the parameter name,m description, and other class attributes
    name = parameterFrame.Name.loc[index]

    theModel.parameters[name].description = parameterFrame.Description[index]

    theModel.parameters[name].set_min(parameterFrame.ParameterMin[index])
    theModel.parameters[name].set_max(parameterFrame.ParameterMax[index])

    if theModel.parameters[name].parameter_type == 'int':
        theModel.parameters[name].set_value(int( parameterFrame.InitialValue[index] ))
    elif theModel.parameters[name].parameter_type == 'float':
        theModel.parameters[name].set_value( parameterFrame.InitialValue[index] )

    theModel.parameters[name].new_initial_value()

    # fixed variables are held constant during the fitting step
    if parameterFrame.Status[index] == 'fixed':
        theModel.parameters[name].set_fixed()


    # variable values are fit during the fitting step by the Optimizer object.
    elif parameterFrame.Status[index] == 'variable':

        # the prior distribution of each parameter is either normal or uniform
        priorFunc = parameterFrame.PriorFunction[index]

        # we're not allowing a parameter to be set as variable without a specified prior function
        if priorFunc == '':
            print('\t parameter {} set to variable but prior function not set (currently {}). \
                  no changes made, please adjust and rerun ***'.format(name, priorFunc))
            continue

        # setting the parameters of the prior distributions
        priorParams = dict()

        if parameterFrame.PriorFunction[index] == 'uniform':

            priorParams = {
                'mean': parameterFrame.PriorMean[index],
                'half_width' : parameterFrame.PriorSecond[index]
            }

        elif parameterFrame.PriorFunction[index] == 'normal':

            priorParams = {
                'mean' : parameterFrame.PriorMean[index],
                'sigma' : parameterFrame.PriorSecond[index]
            }

        theModel.parameters[name].set_variable(prior_function=priorFunc, prior_parameters=priorParams)

    else:
        print('*** STATUS FOR THE PARAMETER {} IS MISTYPED. CAN ONLY BE `fixed` or `variable`, \
              not {} ***'.format(name, parameterFrame['name'][index]))

    # call the reset class method to complete the process of setting this parameter
    theModel.parameters[name].reset()

theModel.boot()

'''
    get the start date assigned to the model; this is important for figuring out the start of the
    time seties to fit to and any data we want to overlay in a chart for comparison
'''

# set the default start and end dates to the mode t0 and a 28-day future projection as default values
startDate = theModel.t0
endDate = datetime.datetime.now().date() + datetime.timedelta(days=28)

# the length of the simulation (in time steps)
simLength = (endDate-startDate).days

print("fitting step")

# try to read case data brought in as a dependency
realData = datasheet(myScenario, "epi_DataSummary")

# if there's case data available for fitting
if not realData.empty:

    # change the timesteps frim string to datetime objects
    realData.Timestep = realData.Timestep.apply(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date())
    realData = realData[realData.Timestep >= startDate]

    # this is the variable we want to fit the model to
    fittingVar = modelChoices.FitVariable

    # if data for the fitting variable chosen is available in the case data given, then proceed
    if fittingVar in set(realData.Variable):
        realData = realData[realData.Variable == fittingVar]
    # if not, default to fitting the cumulative cases
    else:
        realData = realData[realData.Variable == 'Cases - Cumulative']
        fittingVar = 'Cases - Cumulative'

    '''
        the only two time series that can be fit are 'reported' cases and 'infected' cases, either on a daily
        or cumulative basis. this chunk of code takes the four drop-down options given to the user and creates
        one of these four combinations
    '''
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

    # days in the time series on which to start and end data fitting
    startFitDay = 1 if numpy.isnan(modelChoices.StartFit) else int(modelChoices.StartFit)
    endFitDay = realData.shape[0] if numpy.isnan(modelChoices.EndFit) else int(modelChoices.EndFit)

    # fitting using least squares (detailed by Karlen in the pypmca code)
    myOptimiser = Optimizer(
        theModel,
        fittingString,
        realData.Value.values,
        [startFitDay, endFitDay],
        cumulReset,
        str(modelChoices.SkipDatesText[0])
    )
    popt, pcov = myOptimiser.fit()

    # fetch the names and values of the posteriors, reparametrise the model and write them to datasheet
    fitVars = datasheet(myScenario, "modelKarlenPypm_FitVariables", empty=True)
    for index in range(len(popt)):
        name = myOptimiser.variable_names[index]
        value = popt[index]
        fitVars = fitVars.append({'Variable':name, 'Value':value}, ignore_index=True)
        theModel.parameters[name].set_value(value)

    saveDatasheet(myScenario, fitVars, "modelKarlenPypm_FitVariables")

# save the reparametrised model object in the Temp Directory
modelFileName = '{}\\{}_fitted.pypm'.format(env.TempDirectory, theModel.name)
theModel.save_file(modelFileName)

# fill ain information table for the fitted model
fittedModelFile = datasheet(myScenario, "modelKarlenPypm_FittedModelFile")
fittedModelFile.File = [modelFileName]
fittedModelFile.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
fittedModelFile.ModelDescrip = [THIS_MODEL]
fittedModelFile.Crosswalk = [modelChoices.CrosswalkFile]
saveDatasheet(myScenario, fittedModelFile, "modelKarlenPypm_FittedModelFile")

print("getting the expectations")

'''
    here we read the names of the populations/variables chosen by the user and get the time series available,
    if they are included in this model
'''

# this is the list of populations requested by the user
populationTable = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
showThesePops = list(populationTable.ShowThese.drop_duplicates())

# if a corrected crosswalk fine has been supoplied by the user, use that. else, default to the project datasheet
if modelChoices.isnull().CrosswalkFile:
    pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
else:
    crosssWalk = pandas.read_csv(modelChoices.CrosswalkFile)

# lookup function : Karlen model name -> sism standard variable name
def standardName(pop):
    if pop in list(pypmcaCrosswalk.Stock):
        return pypmcaCrosswalk[pypmcaCrosswalk.Stock == pop].Standard.iloc[0]
    else:
        return None

# inverse lookup function : ssim standard variable name -> Karlen model name
def stockName(pop):
    if pop in list(pypmcaCrosswalk.Standard):
        return pypmcaCrosswalk[pypmcaCrosswalk.Standard == pop].Stock.iloc[0]
    else:
        return None

# standard message to be printed if a variable lookup finds so Ssim standard name for a Karlen variable
def standardError(variable):
    return '*** ERROR: requested population {} has no equivalent \
        in the Pypmca model object. Please verify either the \
        crosswalk file used or the standardising funtion \
        "getFancyName" in <headerFile.py> ***'.format(variable)

# reset the model to initial values (set previously) and get the expectations for the reguired time
theModel.reset()
theModel.evolve_expectations(simLength)

# data frame to hold all the time series for the variables requested
expectationsTable = pandas.DataFrame()

# for each variable
for standardName in showThesePops:

    # get the Karlen model equivalent of the name
    karlenName = stockName(standardName)

    # if there's a time series corresponding to the Karlen name, fetch it
    if karlenName in theModel.populations.keys():
        timeSeries = theModel.populations[karlenName].history

    else:

        '''
            some of Karlen's models will not have both daily and cumulative pairs, so here we fetch one if the
            other is not available. this will happen with the variable names manually added to the crosswalk file
            in the renamingMap of the getRepos transformer
        '''

        # if there's no daily variable but a corresponding cumulative variable
        if 'daily' in karlenName:

            # get the base name of the cumulative variable
            karlenStub = karlenName.replace('daily', '').strip()

            # if there's no population of that name, then there may be a problem with the crosswalk file
            if karlenStub not in theModel.populations.keys():
                print(standardError(karlenName))
                continue

            # if the cumulative equivalent is found, make a daily version with a diff function
            timeSeries = headerFile.delta(theModel.populations[karlenStub].history)

        # else, if the daily version exists and we want the cumulative
        elif 'cumulative' in karlenName:

            # get the name of the corresponding daily variable
            karlenStub = karlenName.replace('daily', '').strip()

            # if this isn't dounf, there may be a problem with teh crosswalk file
            if karlenStub not in theModel.populations.keys():
                print(standardError(karlenName))
                continue

            # create the cumulative series by the cumsum function
            timeSeries = numpy.cumsum(theModel.populations[karlenStub].history)

    # if at least 10% of the values in the time series are unique, add the time series to the table
    if headerFile.movementThreshold(timeSeries, 0.1):
        expectationsTable[ standardName ] = timeSeries

print("expectations done")

# add a time column to the time series table
expectationsTable['Timestep'] = [startDate+datetime.timedelta(days=x) for x in range(expectationsTable.shape[0])]

# melt the table to get unique Timestep|Variable rows
epiDatasummary = pandas.melt(expectationsTable, id_vars=["Timestep"])
# fix the column headers to title case
epiDatasummary.columns = map(headerFile.camelify, epiDatasummary.columns)
# add the jurisdiction and trandformer ID
epiDatasummary['Jurisdiction'] = '{} - {}'.format(LUTRow.Country, LUTRow.Region)
epiDatasummary['TransformerID'] = 'modelKarlenPypm_B_getExpectations'

# write only the missing variable names to epi_Variable, adding the corresponding descriptions from the Crosswalk lut
epiVariable = datasheet(myScenario, "epi_Variable")
varList = epiDatasummary.Variable.drop_duplicates()
descripList = map(
    lambda x: pypmcaCrosswalk[pypmcaCrosswalk.Standard == x].Description.iloc[0],
    varList
)
variablesHere = pandas.DataFrame({'Name' : varList, 'Description' : descripList})
saveDatasheet(myScenario, variablesHere[~variablesHere.Name.isin(epiVariable.Name)], "epi_Variable")

# add the current model jurisdiction only if it's not already included (the case if the transformer is run without data and fitting, possible)
epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction")
if LUTRow.Jurisdiction not in list(epiJurisdiction.Name):
    saveDatasheet(
        myScenario,
        pandas.DataFrame({'Name':['{} - {}'.format(LUTRow.Country, LUTRow.Region)], 'Description':['']}),
        "epi_Jurisdiction"
    )

# save the expectations data
saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
