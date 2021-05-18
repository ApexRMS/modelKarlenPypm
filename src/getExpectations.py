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

    3) get the expected values of the populations (model variables) chosen by the user; simulation data will be gathered in
        the getIterations transformer. this is done by calculating the number of time steps between the start of the time of
        the model and the projection end date specified by the user. the function .evolve_expectations is used
'''

import re
import pandas
import numpy
import datetime
import copy
import warnings

import headerFile
from syncro import *

# the model fit (least squares) is done with this 'Optimizer' object
from pypmca.analysis.Optimizer import Optimizer

env = ssimEnvironment()
myScenario = scenario()

# user input (model name, fitting parameter, etc)
model_choices = datasheet(myScenario, "modelKarlenPypm_ModelChoices").iloc[0]

# the name/handle of this model
THIS_MODEL = model_choices.ModelName

#sheet giving the list of models - will be used as a lut
pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels")
# get the corresponding (single) row in the lut
LUTRow = pypmcaModels[pypmcaModels.LUT == THIS_MODEL].iloc[0]
# get the URL of the model and download the .pypm object
model_url = LUTRow.URL
the_model = headerFile.downloadModel(model_url)

'''
    in the options (in line with Karlen's online ipypm interface), the user is allowed to change the default
    (pre-supplied by Karlen) parameter values. after the values have been changed, then all the new parameters
    (whether changed or not, that would be hard to keep track of, KISS) are re-added to the model and then the
    object is rebooted (recalibrated to find initial population values; this  is described by Karlen in the
    pypmca package files) and written to a file
'''

# get the user-supplied parameter values from the datasheet
parameter_frame = datasheet(myScenario, "modelKarlenPypm_ParameterValues")

if not parameter_frame.empty:

    # since the values for all models are specified in the same sheet, be sure only to pull the ones for the specific model
    parameter_frame = parameter_frame[parameter_frame.Model == THIS_MODEL].reset_index()

    # for each parameter
    for index in range(0, parameter_frame.shape[0]):

        # set the parameter name,m description, and other class attributes
        name = parameter_frame.Name.loc[index]

        try:
            the_model.parameters[name].description = parameter_frame.Description[index]
    
            the_model.parameters[name].set_min(parameter_frame.ParameterMin[index])
            the_model.parameters[name].set_max(parameter_frame.ParameterMax[index])
    
            if the_model.parameters[name].parameter_type == 'int':
                the_model.parameters[name].set_value(int( parameter_frame.InitialValue[index] ))
            elif the_model.parameters[name].parameter_type == 'float':
                the_model.parameters[name].set_value( parameter_frame.InitialValue[index] )
    
            the_model.parameters[name].new_initial_value()
    
            # fixed variables are held constant during the fitting step
            if parameter_frame.Status[index] == 'fixed':
                the_model.parameters[name].set_fixed()
    
    
            # variable values are fit during the fitting step by the Optimizer object.
            elif parameter_frame.Status[index] == 'variable':
    
                # the prior distribution of each parameter is either normal or uniform
                prior_func = parameter_frame.PriorFunction[index]
    
                # we're not allowing a parameter to be set as variable without a specified prior function
                if prior_func == '':
                    print('\t parameter {} set to variable but prior function not set (currently {}). \
                          no changes made, please adjust and rerun ***'.format(name, prior_func))
                    continue
    
                # setting the parameters of the prior distributions
                prior_params = dict()
    
                if parameter_frame.PriorFunction[index] == 'uniform':
    
                    prior_params = {
                        'mean': parameter_frame.PriorMean[index],
                        'half_width' : parameter_frame.PriorSecond[index]
                    }
    
                elif parameter_frame.PriorFunction[index] == 'normal':
    
                    prior_params = {
                        'mean' : parameter_frame.PriorMean[index],
                        'sigma' : parameter_frame.PriorSecond[index]
                    }
    
                the_model.parameters[name].set_variable(prior_function=prior_func, prior_parameters=prior_params)
    
            else:
                print('*** STATUS FOR THE PARAMETER {} IS MISTYPED. CAN ONLY BE `fixed` or `variable`, \
                      not {} ***'.format(name, parameter_frame['name'][index]))
    
            # call the reset class method to complete the process of setting this parameter
            the_model.parameters[name].reset()
            
        except KeyError:
            warnings.warn('Parameter defined in parameter list not found in model!')
        except Exception as e:
            print(e)
                

    the_model.boot()

'''
    get the start date assigned to the model; this is important for figuring out the start of the
    time series to fit to and any data we want to overlay in a chart for comparison
'''



print('data filtering step')

data_for_fitting = datasheet(myScenario, "epi_DataSummary").drop(columns=['DataSummaryID', 'TransformerID'])
if data_for_fitting.empty:
    print('\t*** WARNING: no fitting data given ***')

'''
    some of the data sets have different age ranges and sexes. since the Optimizer object only takes a list of values, this structure
    is lost, and all the function sees will be a time series 5000 timesteps deep. to avoid this, we run the data through a filtering
    function that will

    1) select the data for the same jurisdiction as the model

    2) select the currect age ranges and sexes. in cases where totals aren't given, the appropriate rows are summed for each timestep.
        for example, Karlen's BC data breaks the population down completely into age groups and sexes, but gives no aggregates, so a
        cumulative time series is created by either adding the data from each sex (total = male + female) or summing over the ages
        given (total = 0->14 + 15->34 + 35->59 + ... + over 85, say).

    3) choose the iteration giving the longest time series, should there be multiple iterations present in the data set
'''
filtered_data = headerFile.filter_the_data(
    data_for_fitting,
    THIS_MODEL,
    model_choices.FitVariable,
    LUTRow.Jurisdiction,
    LUTRow.AgeRange
)

# set the default fit start, projection start date and end dates to the mode t0 and a 28-day future projection as default values
# Fit start date
try:
    start_date = datetime.datetime.strptime(model_choices.StartFit, '%Y-%m-%d').date()
except:
    start_date = the_model.t0

model_choices.StartFit = start_date.strftime("%Y-%m-%d")    

# Projection start date
try:
    projection_start_date = datetime.datetime.strptime(model_choices.EndFit, '%Y-%m-%d').date()
except:
    projection_start_date = datetime.datetime.now().date() if filtered_data.empty else datetime.datetime.strptime(filtered_data.Timestep.iloc[-1], '%Y-%m-%d').date()

model_choices.EndFit = projection_start_date.strftime("%Y-%m-%d")

# Projection end date
try:
    end_date = projection_start_date + datetime.timedelta(days=model_choices.EndDate.item())
except:
    end_date = projection_start_date + datetime.timedelta(days=model_choices.EndDate.item())

model_choices.EndDate = int((end_date - projection_start_date).days)

# the length of the simulation (in time steps)
simulation_length = (end_date-start_date).days

# we proceed with the filtered data
if not filtered_data.empty:

    print("fitting step\n")

    filtered_data.Timestep = filtered_data.Timestep.apply(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date())
    filtered_data = filtered_data[filtered_data.Timestep >= start_date]

    '''
        the only two time series that can be fit are 'reported' cases and 'infected' cases, either on a daily
        or cumulative basis. this chunk of code takes the four drop-down options given to the user and creates
        one of these four combinations
    '''
    fitting_string = ''

    if 'cumulative' in model_choices.FitVariable.lower():
        fitting_string += 'total '
    elif 'daily' in model_choices.FitVariable.lower():
        fitting_string += 'daily '

    if 'cases' in model_choices.FitVariable.lower():
        fitting_string += 'reported'
    elif 'infected' in model_choices.FitVariable.lower():
        fitting_string += 'infected'

    cumulative_reset_from_zero = True if model_choices.CumulReset == True else False

    # days in the time series on which to start and end data fitting
    start_fitting_day = 1 # since the data is already filtered by start_date
    end_fitting_day = min(filtered_data.shape[0], (projection_start_date - start_date).days + 1)

    # fitting using least squares (detailed by Karlen in the pypmca code)
    myOptimiser = Optimizer(
        the_model,
        fitting_string,
        filtered_data.Value.values,
        [start_fitting_day, end_fitting_day],
        cumulative_reset_from_zero,
        str(model_choices.SkipDatesText[0])
    )
    popt, pcov = myOptimiser.fit()

    # fetch the names and values of the posteriors, reparameterise the model and write them to datasheet
    fitted_variables = datasheet(myScenario, "modelKarlenPypm_FitVariables", empty=True)
    for index in range(len(popt)):
        name = myOptimiser.variable_names[index]
        value = popt[index]
        fitted_variables = fitted_variables.append({'Variable':name, 'Value':value}, ignore_index=True)
        the_model.parameters[name].set_value(value)

    saveDatasheet(myScenario, fitted_variables, "modelKarlenPypm_FitVariables")

# save the reparameterise model object in the Temp Directory
model_file_name = '{}\\{}_fitted.pypm'.format(env.TempDirectory, the_model.name)
the_model.save_file(model_file_name)

# fill in information table for the fitted model
fitted_model_file = datasheet(myScenario, "modelKarlenPypm_FittedModelFile")
fitted_model_file.File = [model_file_name]
fitted_model_file.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
fitted_model_file.ModelDescrip = [THIS_MODEL]
fitted_model_file.Crosswalk = [model_choices.CrosswalkFile]
saveDatasheet(myScenario, fitted_model_file, "modelKarlenPypm_FittedModelFile")

print("getting the expectations")

'''
    here we read the names of the populations/variables chosen by the user and get the time series available,
    if they are included in this model
'''

# this is the list of populations requested by the user
population_table = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
show_these_pops = list(population_table.ShowThese.drop_duplicates())

# if a corrected crosswalk fine has been supplied by the user, use that. else, default to the project datasheet
if model_choices.isnull().CrosswalkFile:
    pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
else:
    crosssWalk = pandas.read_csv(model_choices.CrosswalkFile)

# lookup function : Karlen model name -> Ssim standard variable name
def standard_Ssim_name(pop):
    if pop in list(pypmcaCrosswalk.Stock):
        return pypmcaCrosswalk[pypmcaCrosswalk.Stock == pop].Standard.iloc[0]
    else:
        return None

# inverse lookup function : Ssim standard variable name -> Karlen model name
def stockName(pop):
    if pop in list(pypmcaCrosswalk.Standard):
        return pypmcaCrosswalk[pypmcaCrosswalk.Standard == pop].Stock.iloc[0]
    else:
        return None

# standard message to be printed if a variable lookup finds so Ssim standard name for a Karlen variable
def standardError(variable):
    return '*** ERROR: requested population {} has no equivalent \
        in the Pypmca model object. Please verify either the \
        crosswalk file used or the standardising function \
        "getFancyName" in <headerFile.py> ***'.format(variable)

# reset the model to initial values (set previously) and get the expectations for the required time
the_model.reset()
the_model.evolve_expectations(simulation_length)

# data frame to hold all the time series for the variables requested
expectations_table = pandas.DataFrame()

# for each variable
for standard_Ssim_name in show_these_pops:

    # get the Karlen model equivalent of the name
    karlen_population_name = stockName(standard_Ssim_name)

    # if there's a time series corresponding to the Karlen name, fetch it
    if karlen_population_name in the_model.populations.keys():
        time_series = the_model.populations[karlen_population_name].history

    else:

        '''
            some of Karlen's models will not have both daily and cumulative pairs, so here we fetch one if the
            other is not available. this will happen with the variable names manually added to the crosswalk file
            in the renamingMap of the getRepos transformer
        '''

        # if there's no daily variable but a corresponding cumulative variable
        if 'daily' in karlen_population_name:

            # get the base name of the cumulative variable
            karlen_stub = karlen_population_name.replace('daily', '').strip()

            # if there's no population of that name, then there may be a problem with the crosswalk file
            if karlen_stub not in the_model.populations.keys():
                print(standardError(karlen_population_name))
                continue

            # if the cumulative equivalent is found, make a daily version with a diff function
            time_series = headerFile.delta(the_model.populations[karlen_stub].history)

        # else, if the daily version exists and we want the cumulative
        elif 'cumulative' in karlen_population_name:

            # get the name of the corresponding daily variable
            karlen_stub = karlen_population_name.replace('daily', '').strip()

            # if this isn't found, there may be a problem with the crosswalk file
            if karlen_stub not in the_model.populations.keys():
                print(standardError(karlen_population_name))
                continue

            # create the cumulative series by the cumsum function
            time_series = numpy.cumsum(the_model.populations[karlen_stub].history)

    # if at least 10% of the values in the time series are unique, add the time series to the table
    if headerFile.movementThreshold(time_series, 0.1):
        expectations_table[ standard_Ssim_name ] = time_series

print("expectations done")

# add a time column to the time series table
expectations_table['Timestep'] = [start_date+datetime.timedelta(days=x) for x in range(expectations_table.shape[0])]

# melt the table to get unique Timestep|Variable rows
epiDatasummary = pandas.melt(expectations_table, id_vars=["Timestep"])
# fix the column headers to title case
epiDatasummary.columns = map(headerFile.camelify, epiDatasummary.columns)
# add the jurisdiction and transformer ID
epiDatasummary['Jurisdiction'] = '{} - {}'.format(LUTRow.Country, LUTRow.Region.replace('_', '-'))
epiDatasummary['TransformerID'] = 'modelKarlenPypm_B_getExpectations'
epiDatasummary['Iteration'] = 1

# write only the missing variable names to epi_Variable, adding the corresponding descriptions from the Crosswalk lut
epiVariable = datasheet(myScenario, "epi_Variable")
variable_list = epiDatasummary.Variable.drop_duplicates()
descriptions_list = map(
    lambda x: pypmcaCrosswalk[pypmcaCrosswalk.Standard == x].Description.iloc[0],
    variable_list
)
variablesHere = pandas.DataFrame({'Name' : variable_list, 'Description' : descriptions_list})
saveDatasheet(myScenario, variablesHere[~variablesHere.Name.isin(epiVariable.Name)], "epi_Variable")

# add the current model jurisdiction only if it's not already included (the case if the transformer is run without data and fitting, possible)
epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction")
if LUTRow.Jurisdiction not in list(epiJurisdiction.Name):
    saveDatasheet(
        myScenario,
        pandas.DataFrame({'Name':['{} - {}'.format(LUTRow.Country, LUTRow.Region)], 'Description':['']}),
        "epi_Jurisdiction"
    )

# Save parsed model settings
saveDatasheet(
    myScenario,
    model_choices.to_frame(0).T,
    "modelKarlenPypm_ModelChoices"
)

# Append to input data
epiDatasummary = datasheet(myScenario, "epi_DataSummary").drop(columns=['DataSummaryID']).append(epiDatasummary)
epiDatasummary.AgeMin = epiDatasummary.AgeMin.astype(pandas.Int64Dtype())
epiDatasummary.AgeMax = epiDatasummary.AgeMax.astype(pandas.Int64Dtype())
epiDatasummary.Iteration = epiDatasummary.Iteration.astype(pandas.Int64Dtype())

# save the expectations data
saveDatasheet(myScenario, epiDatasummary, "epi_DataSummary")
