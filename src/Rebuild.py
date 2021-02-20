#!/usr/bin/python

import os
import copy
import pypmca
import numpy as np
import pandas as pd

PARAMETER_TYPES = {'int': int, 'float': float, 'bool': bool}
PARAMETER_STATUSES = ['fixed', 'variable']
PRIOR_FUNCTIONS = ['norm', 'uniform']
PRIOR_PARS = {'norm': ['mean', 'sigma'], 'uniform': ['mean', 'half_width']}

def rebuild(output_folder, downloaded_model_name, parameter_file_name, final_scenario_name):

	the_model = pypmca.Model.open_file('{}\\{}.pypm'.format(output_folder, downloaded_model_name))

	ParameterFrame = pd.read_csv('{}\\{}.csv'.format(output_folder, parameter_file_name), sep=',')


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

	the_model.boot()
	# the_model.save_file('{}\\final_model.pypm'.format(File_Folder))
	the_model.save_file('{}\\{}.pypm'.format(output_folder, final_scenario_name))

	return True
