'''
    There's an error in the Karlen MCMC code (as of 19 Feb 2020), so this file will be completed later.
'''


# print('\ncalculating auto covariance')
# my_optimiser.calc_auto_covariance(300)
#
# print('\ncalculating simulation goodness of fit')
# my_optimiser.calc_sim_gof(10)
#
# ParameterFrame = pd.read_csv('model_parameters.csv', sep=',')
# # get the mcmc_step parameters fromt the file
# for name in  [x for x in ParameterFrame.name if pmodel.parameters[x].get_status() == 'variable']:
#
# 	mcmc_step = ParameterFrame[ParameterFrame.name == 'cont_0'].mcmc_step.item()
#
# 	# if no mcmc step size defined, default to half the standard deviation
# 	if np.isnan(mcmc_step):
# 		print('\t*** mcmc_step not given for variable parameter {}. Defaulting to 1/2 of one standard deviation. ***'.format(name))
# 		if pmodel.parameters[name].prior_function == 'uniform':
# 			# var=(b-a)/12, hw=(b-a)/2, so that sd=hw/sqrt(6)
# 			pmodel.parameters[name].mcmc_step = 0.5*pmodel.parameters[name].prior_parameters['half_width'] /np.sqrt(6)
# 		elif pmodel.parameters[name].prior_function == 'normal':
# 			# mcmc default step hald the standard deviation
# 			pmodel.parameters[name].mcmc_step = 0.5*pmodel.parameters[name].prior_parameters['mean']
# 	# if there is a user-specified mcmc_step ni the parameters file, pull them in here
# 	else:
# 		pmodel.parameters[name].mcmc_step = mcmc_step
#
# print('calculating MCMC')
#
# # n_dof, chi2n, n_mcmc
# # my_optimiser.mcmc(60, 500, 500)
#
# '''
#     do you want some sort of iterative procedure where the MCMC step is repeated until the accepted fraction is above 0.3
# '''
# chains = do_mcmc(pmodel, my_optimiser, 60, my_optimiser.chi2n, 5000)
#
#
#
# '''
#     It seems that there is a way to make Ensembles of scenarios with infection cycles disseminated through contact matrix, but there are a few caveats related to growth rates etc that karlen cautions against
# '''
