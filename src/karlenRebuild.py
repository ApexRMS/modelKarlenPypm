# build a model from output files

import os
import copy
import pypmca
import builtins
import numpy as np
import pandas as pd

the_model = pypmca.Model.open_file('{}\\downloaded_model.pypm'.format('C:\\Users\\User\\Documents\\SyncroSim\\Packages\\modelKarlenPypm'))

############################################################################################################################################

PARAMETER_TYPES = {'int': int, 'float': float, 'bool': bool}
PARAMETER_STATUSES = ['fixed', 'variable']
PRIOR_FUNCTIONS = ['norm', 'uniform']
PRIOR_PARS = {'norm': ['mean', 'sigma'], 'uniform': ['mean', 'half_width']}
ParameterFrame = pd.read_csv('{}\\model_parameters.csv'.format('C:\\Users\\User\\Documents\\SyncroSim\\Packages\\modelKarlenPypm'), sep=',')

'''
	implement a check table function to run over the entire table and make sure that the values are fine before starting with all the loops
		for instance, if a parameter is marked as variable, the parameters for the distribution must be supplied (either that or come up with some default value)

	if an mcmc step hasn't been defined for the 'variable' parameters to be fit, assign 1/2 the standard deviation of the distribution to get started
'''

# importing the parameters
# setting the MCMC parameters here

for index in range(0, ParameterFrame.shape[0]):

	name = list(the_model.parameters.keys())[index]

	the_model.parameters[name].parameter_type = ParameterFrame['parameter_type'][index]
	if ParameterFrame['parameter_type'][index] == 'int':
		the_model.parameters[name].set_value(int(ParameterFrame['initial_value'][index]))
	elif ParameterFrame['parameter_type'][index] == 'float':
		the_model.parameters[name].set_value(float(ParameterFrame['initial_value'][index]))
	else:
		print('*** PARAMETER TYPE FOR {} IS MISTYPED. CAN ONLY BE `int` or `float`, not {} ***'.format(name, ParameterFrame['name'][index], ))
		continue

	the_model.parameters[name].description = ParameterFrame['description'][index]

	if ParameterFrame['status'][index] == 'fixed':
		the_model.parameters[name].set_fixed()
	elif ParameterFrame['status'][index] == 'variable':
		prior_func = ParameterFrame['prior_function'][index]; prior_params = dict(); initial_value = 0;
		if ParameterFrame['mcmc_step'][index] == None:
			print('\t*** mcmc_step not given for variable parameter {}. Defaulting to 1/2 of one standard deviation. ***'.format(name))
		if ParameterFrame['prior_function'][index] == 'uniform':
			prior_params = {'mean': ParameterFrame['prior_mean'][index], 'half_width' : ParameterFrame['prior_second'][index]}
			# var=(b-a)/12, hw=(b-a)/2, so that sd=hw/sqrt(6)
			the_model.parameters[name].mcmc_step = 0.5*ParameterFrame['prior_second'][index]/np.sqrt(6)
		elif ParameterFrame['prior_function'][index] == 'normal':
			prior_params = {'mean' : ParameterFrame['prior_mean'][index], 'sigma' : ParameterFrame['prior_second'][index]}
			# mcmc default step half the standard deviation
			the_model.parameters[name].mcmc_step = 0.5*ParameterFrame['prior_second'][index]
		else:
			print('\t*** variable parameter {} has no prior function or parameters supplied. ***'.format(name))
			prior_func = None
			prior_params = None
		the_model.parameters[name].set_variable(prior_function=prior_func, prior_parameters=prior_params)
	else:
		print('*** STATUS FOR THE PARAMETER {} IS MISTYPED. CAN ONLY BE `fixed` or `variable`, not {} ***'.format(name, ParameterFrame['name'][index]))

	the_model.parameters[name].set_min(ParameterFrame['parameter_min'][index])
	the_model.parameters[name].set_max(ParameterFrame['parameter_max'][index])

	the_model.parameters[name].reset()

###########################################################################################################################################

the_model.boot()
the_model.save_file('{}\\final_model.pypm'.format('C:\\Users\\User\\Documents\\SyncroSim\\Packages\\modelKarlenPypm'))
