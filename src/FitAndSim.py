#!/usr/bin/python

import os
import pickle
import time
import copy
import sys
import numpy as np

import pandas as pd
from pypmca import Model

def fit_sims(model, n_rep, optimiser):
    # Estimate the properties of the estimators, by making many several simulated samples to find the bias and covariance
    # This presumes that the variability of the data is well represented: show the autocorrelation and chi^2

    optimiser.calc_chi2f = True
    optimiser.calc_chi2s = False
    optimiser.calc_sim_gof(n_rep)

    results = []
    for i_rep in range(n_rep):
        results.append(optimiser.opt_lists['opt'][i_rep])
    transposed = np.array(results).T
    corr = None
    if len(optimiser.variable_names) > 1:
        corr = np.corrcoef(transposed)

    print('Reporting noise parameters:')
    pop_name = optimiser.region_name
    pop = optimiser.model.populations[pop_name]
    noise_pars = pop.get_report_noise()
    buff = []

    for noise_par_name in noise_pars:
        if noise_par_name == 'report_noise':
            buff.append('enabled =' + str(noise_pars[noise_par_name]))
        else:
            try:
                buff.append(str(noise_pars[noise_par_name])+'='+str(noise_pars[noise_par_name].get_value()))
            except:
                pass
    print('  ',', '.join(buff))
    for conn_name in optimiser.model.connectors:
        conn = optimiser.model.connectors[conn_name]
        try:
            dist, nbp = conn.get_distribution()
            if dist == 'nbinom':
                print('   '+conn_name+' neg binom parameter='+str(nbp.get_value()))
        except:
            pass

    print('\nFit results from: ' + str(n_rep) + ' simulations')
    for i, par_name in enumerate(optimiser.variable_names):
        truth = model.parameters[par_name].get_value()
        mean = np.mean(transposed[i])
        std = np.std(transposed[i])
        err_mean = std/np.sqrt(n_rep)
        print(' \t'+par_name, ': truth = {0:0.4f} mean = {1:0.4f}, std = {2:0.4f}, err_mean = {3:0.4f}'.format(truth, mean, std, err_mean))
    if corr is not None:
        print('Correlation coefficients:')
        for row in corr:
            buff = '   '
            for value in row:
                buff += ' {0: .3f}'.format(value)
            print(buff)

    values = {}
    for fit_stat in optimiser.fit_stat_list:
        for stat in ['chi2_c', 'chi2', 'cov', 'acor']:
            if stat not in values:
                values[stat] = []
            values[stat].append(fit_stat[stat])

    print('Fit statistics: Data | simulations')
    print('  chi2_c = {0:0.1f} | mean = {1:0.1f} std = {2:0.1f}, err_mean = {3:0.1f}'.format(
        optimiser.fit_statistics['chi2_c'],
        np.mean(values['chi2_c']),
        np.std(values['chi2_c']),
        np.std(values['chi2_c'])/np.sqrt(n_rep)
    ))

    print('  ndof = {0:d} | {1:d}'.format(optimiser.fit_statistics['ndof'], optimiser.fit_stat_list[0]['ndof']))

    fs = {'chi2':1, 'cov':2, 'acor':4}
    for stat in ['chi2', 'cov', 'acor']:
        data_val = optimiser.fit_statistics[stat]
        mean = np.mean(values[stat])
        std = np.std(values[stat])
        err_mean = std / np.sqrt(n_rep)
        print('  '+stat+' = {0:0.{i}f} | mean = {1:0.{i}f} std = {2:0.{i}f}, err_mean = {3:0.{i}f}'.format(
            data_val, mean, std, err_mean, i=fs[stat]
        ))

def do_mcmc(model, optimizer, n_dof, chi2n, n_mcmc):
    status = True
    # check that autocovariance matrix is calculated
    if optimizer.auto_cov is None:
        status = False
        print('Auto covariance is needed before starting MCMC')
    # check that mcmc steps are defined. Check there are no integer variables
    for par_name in model.parameters:
        par = model.parameters[par_name]
        if par.get_status() == 'variable':
            if par.parameter_type != 'float':
                status = False
                print('Only float parameters allowed in MCMC treatment')
                print('Remove: '+par.name)
            elif par.mcmc_step is None:
                status = False
                print('MCMC step size missing for: '+par.name)
    if status:
        chain = optimizer.mcmc(n_dof, chi2n, n_mcmc)
        print('MCMC chain produced.')
        print('fraction accepted =',self.optimizer.accept_fraction)
        return chain
    else:
        return None

def delta(cumul):
    # get the daily data from the cumulative data
    diff = []
    for i in range(1, len(cumul)):
        diff.append(cumul[i] - cumul[i - 1])
    return diff

def camelify(x):
	return ''.join(i.capitalize() for i in x.replace('_', ' ').replace(',', ' ').split(' '))

def fitandsim(output_folder, empirical_data_file, region_name, final_scenario_name, sim_file_name, days_to_fit, cumul_reset, skip_dates, num_iterations):

    from pypmca.analysis.Optimizer import Optimizer

    '''
    file name in the next line is just a shortcut. will figure this out later
    '''
    DT = pd.read_csv('{}\\{}.csv'.format('C:\\Users\\User\\Documents\\GitHub\\modelKarlenPypm\\src', empirical_data_file))

    real_data = np.array(DT[DT.Jurisdiction == region_name][DT.Iteration == 1].Value)
    pmodel = Model.open_file('{}\\{}.pypm'.format(output_folder, final_scenario_name))
    pmodel.reset()

    my_optimiser = Optimizer(pmodel, 'daily reported', real_data, days_to_fit, cumul_reset, skip_dates)
    popt, pcov = my_optimiser.fit()

    for par_name in my_optimiser.variable_names:
        print('\t'+par_name, '= {0:0.3f}'.format(pmodel.parameters[par_name].get_value()))

    for index in range(len(popt)):
        name = my_optimiser.variable_names[index]
        value = popt[index]
        pmodel.parameters[name].set_value(value)
        pmodel.parameters[name].new_initial_value()

    # chi2_c
    # chi2_m - naive goodness of fit
    # chi2_n - goodness of fit (normalization only): one egree of freedom - the last data value
    # chi2_f naive goodness of fit (shape only) calculated with respect to a reference model fitted to the data (calculated if self.calc_chi2_f is True)
    # chi2_s - goodness of fit (shape only, with autocorrelation) calculated with respect to the rederence model.
    #   means and standard deviations of the dof distributions are saved in in self.chi2m, self.chi2m_sd etc.

    print('Fit statistics:')
    print('\tchi2_c = {0:0.1f}'.format(my_optimiser.fit_statistics['chi2_c']))
    print('\tndof = {0:d}'.format(my_optimiser.fit_statistics['ndof']))
    print('\tchi2 = {0:0.1f}'.format(my_optimiser.fit_statistics['chi2']))
    print('\tcov = {0:0.2f}'.format(my_optimiser.fit_statistics['cov']))
    print('\tacor = {0:0.4f}'.format(my_optimiser.fit_statistics['acor']))

    # print('\nFitting simulations:')
    # fit_sims(pmodel, 10, my_optimiser)

    Sim_Dict = dict()

    # the Date column seems to screw with the XML, so we leave that out for now

    temp_table = pd.DataFrame()
    pmodel.reset()
    pmodel.evolve_expectations(len(real_data))
    for pop in pmodel.populations.keys():
        if pop != 'frac':
            temp_table[pop] = pmodel.populations[pop].history
    temp_table['Iteration'] = np.nan
    # temp_table['date'] = DT.Date
    daily_row = delta(temp_table['infected'])
    temp_table = temp_table[0:len(real_data)]
    temp_table['daily_infected'] = daily_row
    temp_table['true_reported'] = real_data
    temp_table['time_step'] = list(range(1, temp_table.shape[0]+1))

    Sim_Dict['expectations'] = temp_table

    for iter in range(num_iterations):
        temp_table = pd.DataFrame()
        pmodel.reset()
        pmodel.generate_data(len(real_data))
        for pop in pmodel.populations.keys():
            if pop != 'frac':
                temp_table[pop] = pmodel.populations[pop].history
        temp_table['Iteration'] = str(iter)
        # temp_table['date'] = DT.Date
        temp_table = temp_table[0:len(real_data)]
        temp_table['daily_infected'] = daily_row
        temp_table['true_reported'] = real_data
        temp_table['time_step'] = list(range(1, temp_table.shape[0]+1))

        Sim_Dict[str(iter)] = temp_table

    All_Data = pd.concat(Sim_Dict.values(), ignore_index=False)
    All_Data.columns = [camelify(x) for x in All_Data.columns]

    these_first = ['Iteration', 'TimeStep', 'TrueReported', 'DailyInfected', 'Infected', 'Total']
    all_the_rest = sorted([x for x in All_Data.columns if x not in these_first])

    All_Data = All_Data[these_first + all_the_rest]

    All_Data.to_csv('{}\\{}.csv'.format(output_folder, sim_file_name), index=False)

    return True
