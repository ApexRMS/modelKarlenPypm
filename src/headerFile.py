import os
import pickle

'''
    When I recompile modelKarlenPypm, it deletes the epi.ssim.temp folder, so I'm using the SSIM_TEMP_DIRECTORY
'''
OUTPUT_FOLDER = os.getenv('SSIM_TEMP_DIRECTORY')

# no extension
DOWNLOADED_MODEL_NAME = 'downloadedScenario'

# no extension
PARAMETER_FILE_NAME = 'modelPrameters'

# no extension
FINAL_SCENARIO_NAME = 'finalScenario'

# no extension
EMPIRICAL_DATA_FILE = 'summary_output'

REGION_NAME = 'Canada - British Columbia'

# no extension
SIM_FILE_NAME = 'SSIM_APPEND-modelKarlenPypm_OutputDatasheet'

# epi package run control?

DAYS_TO_FIT = [37, 350] # range of days in the data to fit

CUMUL_RESET = True; # whether to start the cumulative at zero

SKIP_DATES_TEXT = '25,45:47'

NUM_ITERATIONS = 200

def openModel(filename, myPickle):
    model = pickle.loads(myPickle)
    time_step = model.get_time_step()
    if time_step > 1.001 or time_step < 0.999:
        print('Filename: ' + filename)
        print('*** Model NOT loaded ***')
        print('Only supporting models with time_step = 1 day.')
    return model

def delta(cumul):
    # get the daily data from the cumulative data
    diff = []
    for i in range(1, len(cumul)):
        diff.append(cumul[i] - cumul[i - 1])
    return diff

def camelify(x):
	return ''.join(i.capitalize() for i in x.replace('_', ' ').replace(',', ' ').split(' '))

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
    noiseParameters = pop.get_report_noise()
    buff = []

    for npName in noiseParameters:
        if npName == 'report_noise':
            buff.append('enabled =' + str(noiseParameters[npName]))
        else:
            try:
                buff.append(str(noiseParameters[npName])+'='+str(noiseParameters[npName].get_value()))
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
    for i, parName in enumerate(optimiser.variable_names):
        truth = model.parameters[parName].get_value()
        mean = np.mean(transposed[i])
        std = np.std(transposed[i])
        err_mean = std/np.sqrt(n_rep)
        print(' \t'+parName, ': truth = {0:0.4f} mean = {1:0.4f}, std = {2:0.4f}, err_mean = {3:0.4f}'.format(truth, mean, std, err_mean))
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
    for parName in model.parameters:
        par = model.parameters[parName]
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

# file1 = open("{}\\myfile.txt".format(os.getenv('SSIM_TEMP_DIRECTORY')),"w")
# file1.write("Hello \n")
# # file1.write( "{}".format(os.getenv('SSIM_TRANSFER_DIRECTORY')) )
# for k, v in os.environ.items():
#     file1.write(f'{k}={v}\n')
# file1.close() #to change file access modes
