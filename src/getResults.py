#!/usr/bin/python

import pypmca
import numpy
import pandas

from pypmca.analysis.Optimizer import Optimizer

from headerFile import *

theModel = pypmca.Model.open_file('{}\\{}.pypm'.format(OUTPUT_FOLDER, DOWNLOADED_MODEL_NAME))

ParameterFrame = pandas.read_csv('{}\\{}.csv'.format(OUTPUT_FOLDER, PARAMETER_FILE_NAME), sep=',')

for index in range(0, ParameterFrame.shape[0]):

	name = list(theModel.parameters.keys())[index]

	theModel.parameters[name].parameter_type = ParameterFrame['parameter_type'][index]
	if ParameterFrame['parameter_type'][index] == 'int':
		theModel.parameters[name].set_value(int(ParameterFrame['initial_value'][index]))
	elif ParameterFrame['parameter_type'][index] == 'float':
		theModel.parameters[name].set_value(float(ParameterFrame['initial_value'][index]))
	else:
		print('*** PARAMETER TYPE FOR {} IS MISTYPED. CAN ONLY BE `int` or `float`, not {} ***'.format(name, ParameterFrame['name'][index], ))
		continue

	theModel.parameters[name].description = ParameterFrame['description'][index]

	if ParameterFrame['status'][index] == 'fixed':
		theModel.parameters[name].set_fixed()
	elif ParameterFrame['status'][index] == 'variable':
		prior_func = ParameterFrame['prior_function'][index]; prior_params = dict(); initial_value = 0;
		if ParameterFrame['mcmc_step'][index] == None:
			print('\t*** mcmc_step not given for variable parameter {}. Defaulting to 1/2 of one standard deviation. ***'.format(name))
		if ParameterFrame['prior_function'][index] == 'uniform':
			prior_params = {'mean': ParameterFrame['prior_mean'][index], 'half_width' : ParameterFrame['prior_second'][index]}
			# var=(b-a)/12, hw=(b-a)/2, so that sd=hw/sqrt(6)
			theModel.parameters[name].mcmc_step = 0.5*ParameterFrame['prior_second'][index]/numpy.sqrt(6)
		elif ParameterFrame['prior_function'][index] == 'normal':
			prior_params = {'mean' : ParameterFrame['prior_mean'][index], 'sigma' : ParameterFrame['prior_second'][index]}
			# mcmc default step half the standard deviation
			theModel.parameters[name].mcmc_step = 0.5*ParameterFrame['prior_second'][index]
		else:
			print('\t*** variable parameter {} has no prior function or parameters supplied. ***'.format(name))
			prior_func = None
			prior_params = None
		theModel.parameters[name].set_variable(prior_function=prior_func, prior_parameters=prior_params)
	else:
		print('*** STATUS FOR THE PARAMETER {} IS MISTYPED. CAN ONLY BE `fixed` or `variable`, not {} ***'.format(name, ParameterFrame['name'][index]))

	theModel.parameters[name].set_min(ParameterFrame['parameter_min'][index])
	theModel.parameters[name].set_max(ParameterFrame['parameter_max'][index])

	theModel.parameters[name].reset()

theModel.boot()
# theModel.save_file('{}\\final_model.pypm'.format(File_Folder))
theModel.save_file('{}\\{}.pypm'.format(OUTPUT_FOLDER, FINAL_SCENARIO_NAME))

'''
file name in the next line is just a shortcut. will figure this out later
'''
DT = pandas.read_csv('{}\\{}.csv'.format('C:\\Users\\User\\Documents\\GitHub\\modelKarlenPypm\\src', EMPIRICAL_DATA_FILE))

real_data = numpy.array(DT[DT.Jurisdiction == REGION_NAME][DT.Iteration == 1].Value)
pmodel = pypmca.Model.open_file('{}\\{}.pypm'.format(OUTPUT_FOLDER, FINAL_SCENARIO_NAME))
pmodel.reset()

myOptimiser = Optimizer(pmodel, 'daily reported', real_data, DAYS_TO_FIT, CUMUL_RESET, SKIP_DATES_TEXT)
popt, pcov = myOptimiser.fit()

for parName in myOptimiser.variable_names:
    print('\t'+parName, '= {0:0.3f}'.format(pmodel.parameters[parName].get_value()))

for index in range(len(popt)):
    name = myOptimiser.variable_names[index]
    value = popt[index]
    pmodel.parameters[name].set_value(value)
    pmodel.parameters[name].new_initial_value()

# chi2_c
# chi2_m - naive goodness of fit
# chi2_n - goodness of fit (normalization only): one egree of freedom - the last data value
# chi2_f naive goodness of fit (shape only) calculated with respect to a reference model fitted to the data (calculated if self.calc_chi2_f is True)
# chi2_s - goodness of fit (shape only, with autocorrelation) calculated with respect to the rederence model.
#   means and standard deviations of the dof distributions are saved in in self.chi2m, self.chi2m_sd etc.

# print('Fit statistics:')
# print('\tchi2_c = {0:0.1f}'.format(myOptimiser.fit_statistics['chi2_c']))
# print('\tndof = {0:d}'.format(myOptimiser.fit_statistics['ndof']))
# print('\tchi2 = {0:0.1f}'.format(myOptimiser.fit_statistics['chi2']))
# print('\tcov = {0:0.2f}'.format(myOptimiser.fit_statistics['cov']))
# print('\tacor = {0:0.4f}'.format(myOptimiser.fit_statistics['acor']))

# print('\nFitting simulations:')
# fit_sims(pmodel, 10, myOptimiser)

simDict = dict()

# the Date column seems to screw with the XML, so we leave that out for now

tempTable = pandas.DataFrame()
pmodel.reset()
pmodel.evolve_expectations(len(real_data))
for pop in pmodel.populations.keys():
    if pop != 'frac':
        tempTable[pop] = pmodel.populations[pop].history
tempTable['Iteration'] = numpy.nan
# tempTable['date'] = DT.Date
daily_row = delta(tempTable['infected'])
tempTable = tempTable[0:len(real_data)]
tempTable['daily_infected'] = daily_row
tempTable['true_reported'] = real_data
tempTable['time_step'] = list(range(1, tempTable.shape[0]+1))

simDict['expectations'] = tempTable

for iter in range(NUM_ITERATIONS):
    tempTable = pandas.DataFrame()
    pmodel.reset()
    pmodel.generate_data(len(real_data))
    for pop in pmodel.populations.keys():
        if pop != 'frac':
            tempTable[pop] = pmodel.populations[pop].history
    tempTable['Iteration'] = str(iter)
    # tempTable['date'] = DT.Date
    tempTable = tempTable[0:len(real_data)]
    tempTable['daily_infected'] = daily_row
    tempTable['true_reported'] = real_data
    tempTable['time_step'] = list(range(1, tempTable.shape[0]+1))

    simDict[str(iter)] = tempTable

All_Data = pandas.concat(simDict.values(), ignore_index=False)
All_Data.columns = [camelify(x) for x in All_Data.columns]

these_first = ['Iteration', 'TimeStep', 'TrueReported', 'DailyInfected', 'Infected', 'Total']
all_the_rest = sorted([x for x in All_Data.columns if x not in these_first])

All_Data = All_Data[these_first + all_the_rest]

All_Data.to_csv('{}\\{}.csv'.format(OUTPUT_FOLDER, SIM_FILE_NAME), index=False)
