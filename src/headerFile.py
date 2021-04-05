import requests
import pickle
import pycountry
import pandas
import datetime
import pypmca

from syncro import *

''' functions to turn the integers from the XML into strings and vice verse (due to the validation) '''

def standardPopName(pop:pypmca.Population):
    
    varName = getFancyName(pop.name)
    
    if 'daily' in varName.lower():
        return '{} - Daily'.format( varName.replace('daily', '').strip().title() )
    
    if 'cumulative' in varName.lower():
        return '{} - Cumulative'.format( varName.replace('cumulative', '').strip().title() )

    standardName = '{} - {}'.format(
        varName,
        'Cumulative' if pandas.Series(pop.history).is_monotonic_increasing else 'Daily'
    )

    return standardName

def getFancyName(varName:str):

    varName = varName.replace('_', ' ').lower()
    varName = varName.replace('non ', 'Non ')
    varName = varName.replace(' rel', ' Released')
    varName = varName.replace('vacc ', 'Vaccination ')
    varName = varName.replace(' cand', ' Candidates')
    varName = varName.replace('sus ', 'Susceptible ')
    varName = varName.replace('rec ', 'Recovered ')
    varName = varName.replace('daily ', 'Daily - ')
    varName = varName.replace('cumulative ', 'Cumulative - ')
    varName = varName.replace('deaths', 'mortality')
    varName = varName.replace('infected', 'cases')

    if varName[-2:] == ' v':
        varName = varName.replace(' v', ' (Variants)')

    varName = varName.title().replace('Icu', 'ICU')

    return varName

def movementThreshold(series, desiredProportion):
    if (desiredProportion < 0) or (desiredProportion > 1):
        print('*** ERROR: the proportion must be between 0 and 1 ***')
        return None
    # ratio of unique values to total number of values
    theRatio = len(set(series))/len(series)
    if theRatio < desiredProportion:
        return False
    else:
        return True

def tablePriorDist(input):
    if input == None:
        return 3
    if isinstance(input, int) or isinstance(input, float):
        return 'uniform' if int(input)==1 else 'norm' if int(input)==2 else 3
    if isinstance(input, str):
        return 1 if input=='uniform' else 2 if input=='norm' else 3
    return None

def tableStatus(input):
    if isinstance(input, int) or isinstance(input, float):
        return 'fixed' if input == 1 else 'variable'
    elif isinstance(input, str):
        return 1 if input == 'fixed' else 2
    return None

def tableType(input):
    if isinstance(input, int) or isinstance(input, float):
        return 'int' if input == 1 else 'float'
    elif isinstance(input, str):
        return 1 if input == 'int' else 2
    return None

def capitaliseFirst(string):
    return string[0].upper() + string[1:]

def delta(cumul):
    diff = []
    for i in range(1, len(cumul)):
        diff.append(cumul[i] - cumul[i - 1])
    # first daily value is repeated since val(t0-1) is unknown
    diff.insert(0,diff[0])
    return diff

def camelify(x):
	return ''.join(capitaliseFirst(i) for i in x.replace('_', ' ').replace(',', ' ').split(' '))

def openModel(my_pickle):
    try:
        model = pickle.loads(my_pickle)
    except UnpicklingError as error:
        print('*** Model NOT loaded ***')
        print(error)

    time_step = model.get_time_step()

    if time_step > 1.001 or time_step < 0.999:
        print('*** Model NOT loaded ***')
        print('Currently, ipypm only supports models with time_step = 1 day.')
    return model

def downloadModel(theURL):

    try:
        modelResponse = requests.get(theURL);
    except requests.exceptions.RequestException as error:
        print('Error retrieving model folder list over network:')
        print()
        print(error)
        return None
    myPickle = modelResponse.content
    return openModel(myPickle)

def getSubinteger(string:str):
    numString = ''.join([s for s in list(string) if s.isdigit()])
    return int(numString)

def ageRange(modelName:str):

    firstBit = modelName.split('_')[0]

    if any([substring in firstBit for substring in ['under', 'less']]):
        return 'under {}'.format(getSubinteger(firstBit))

    elif any([substring in firstBit for substring in ['over', 'plus']]):
        # extra space to make sure that all strings are the same length
        return 'over {}'.format(getSubinteger(firstBit))

    elif 'to' in firstBit:
        subStrs = firstBit.split('to')
        fromAge = getSubinteger(subStrs[0])
        toAge = getSubinteger(subStrs[1])
        return '{} -> {}'.format(fromAge, toAge)

    # 'bc60_2_3_0911', etc
    elif bool(re.search(r'\d', firstBit)):
        fromAge = getSubinteger(firstBit)
        toAge = fromAge + 9
        return '{} -> {}'.format(fromAge, toAge)

    return ''

def modelDate(modelName):

   firstPass = modelName.split('_')[-1].replace('.pypm', '')

   if firstPass == '':
       return None

   if len(firstPass) != 4:
       return firstPass

   month = int(firstPass[:2])
   day = int(firstPass[2:])
   # return '{}/{}'.format( )
   return datetime.date(2021 if month < 5 else 2020, month, day)

def regionInfo(countryName:str, modelName:str):

    theSplit = modelName.replace(' ', '').split('_')
    twoLetter = theSplit[0][:2].upper()

    iso3166Code = ''
    finalName = ''

    # regionInfo('USA', 'oh_2_8_0316')
    if countryName == 'USA':
        countryName = 'United States'
    # regionInfo('California', 'ca65plus_2_5_1005.pypm'))
    elif countryName == 'California':
        countryName = 'United States'

    # if it's actually a country we were given:
    if countryName in [x.name for x in pycountry.countries]:
        # regionInfo('Canada', ' qc_2_8_0311.pypm')
        countryCode = pycountry.countries.get(name=countryName).alpha_2
        iso3166Code = '{}-{}'.format(countryCode, twoLetter)
        finalName = pycountry.subdivisions.get(code=iso3166Code).name

    elif countryName == 'EU':
        # regionInfo('EU', 'it_2_8_0224.pypm')
        localeInfo = pycountry.countries.get(alpha_2=twoLetter)
        iso3166Code = '{}-{}'.format(countryName, twoLetter)
        finalName = localeInfo.name

    elif countryName == 'reference':
        # regionInfo('reference', 'ref_model_2.pypm')
        # get the numbers from the string
        theDigits = [x for x in modelName.replace('.pypm', '').split('_') if x.isdigit()]
        # print the digits at the end
        # finalName = '{} ({})'.format(countryName.title(), ' '.join(theDigits))
        finalName = countryName.title()

    if countryName == 'BC':

        lut = { # health authorities
            'coastal' : 'Vancouver Coastal', # North Shore/East Garibaldi, Richmond, Vancouver, Unknown
            'northern' : 'Northern', # Northeast, Northern Interior, Northwest, Unknown
            'island' : 'Vancouver Island', # Central, North, South
            'interior' : 'Interior',  #  East Kootenay, Okanagan, Kootenay Boundary, Thompson Cariboo Shuswap
            'fraser' : 'Fraser' # Frase East, North, South, Unknown
        }

        iso3166Code = 'CA-BC'

        if twoLetter == 'BC':
            # regionInfo('BC', 'bc60_2_3_0911.pypm')
            finalName = 'British Columbia'
        else:
            # regionInfo('BC', 'interior_2_8_0309.pypm')
            finalName = 'British Columbia - {}'.format( lut[ theSplit[0] ].title() )

    return {'code' : iso3166Code, 'name' : finalName}

# def fit_sims(model, n_rep, optimiser):
#     # Estimate the properties of the estimators, by making many several simulated samples to find the bias and covariance
#     # This presumes that the variability of the data is well represented: show the autocorrelation and chi^2
#
#     optimiser.calc_chi2f = True
#     optimiser.calc_chi2s = False
#     optimiser.calc_sim_gof(n_rep)
#
#     results = []
#     for i_rep in range(n_rep):
#         results.append(optimiser.opt_lists['opt'][i_rep])
#     transposed = np.array(results).T
#     corr = None
#     if len(optimiser.variable_names) > 1:
#         corr = np.corrcoef(transposed)
#
#     print('Reporting noise parameters:')
#     pop_name = optimiser.region_name
#     pop = optimiser.model.populations[pop_name]
#     noiseParameters = pop.get_report_noise()
#     buff = []
#
#     for npName in noiseParameters:
#         if npName == 'report_noise':
#             buff.append('enabled =' + str(noiseParameters[npName]))
#         else:
#             try:
#                 buff.append(str(noiseParameters[npName])+'='+str(noiseParameters[npName].get_value()))
#             except:
#                 pass
#     print('  ',', '.join(buff))
#     for conn_name in optimiser.model.connectors:
#         conn = optimiser.model.connectors[conn_name]
#         try:
#             dist, nbp = conn.get_distribution()
#             if dist == 'nbinom':
#                 print('   '+conn_name+' neg binom parameter='+str(nbp.get_value()))
#         except:
#             pass
#
#     print('\nFit results from: ' + str(n_rep) + ' simulations')
#     for i, parName in enumerate(optimiser.variable_names):
#         truth = model.parameters[parName].get_value()
#         mean = np.mean(transposed[i])
#         std = np.std(transposed[i])
#         err_mean = std/np.sqrt(n_rep)
#         print(' \t'+parName, ': truth = {0:0.4f} mean = {1:0.4f}, std = {2:0.4f}, err_mean = {3:0.4f}'.format(truth, mean, std, err_mean))
#     if corr is not None:
#         print('Correlation coefficients:')
#         for row in corr:
#             buff = '   '
#             for value in row:
#                 buff += ' {0: .3f}'.format(value)
#             print(buff)
#
#     values = {}
#     for fit_stat in optimiser.fit_stat_list:
#         for stat in ['chi2_c', 'chi2', 'cov', 'acor']:
#             if stat not in values:
#                 values[stat] = []
#             values[stat].append(fit_stat[stat])
#
#     print('Fit statistics: Data | simulations')
#     print('  chi2_c = {0:0.1f} | mean = {1:0.1f} std = {2:0.1f}, err_mean = {3:0.1f}'.format(
#         optimiser.fit_statistics['chi2_c'],
#         np.mean(values['chi2_c']),
#         np.std(values['chi2_c']),
#         np.std(values['chi2_c'])/np.sqrt(n_rep)
#     ))
#
#     print('  ndof = {0:d} | {1:d}'.format(optimiser.fit_statistics['ndof'], optimiser.fit_stat_list[0]['ndof']))
#
#     fs = {'chi2':1, 'cov':2, 'acor':4}
#     for stat in ['chi2', 'cov', 'acor']:
#         data_val = optimiser.fit_statistics[stat]
#         mean = np.mean(values[stat])
#         std = np.std(values[stat])
#         err_mean = std / np.sqrt(n_rep)
#         print('  '+stat+' = {0:0.{i}f} | mean = {1:0.{i}f} std = {2:0.{i}f}, err_mean = {3:0.{i}f}'.format(
#             data_val, mean, std, err_mean, i=fs[stat]
#         ))
#
# def do_mcmc(model, optimizer, n_dof, chi2n, n_mcmc):
#     status = True
#     # check that autocovariance matrix is calculated
#     if optimizer.auto_cov is None:
#         status = False
#         print('Auto covariance is needed before starting MCMC')
#     # check that mcmc steps are defined. Check there are no integer variables
#     for parName in model.parameters:
#         par = model.parameters[parName]
#         if par.get_status() == 'variable':
#             if par.parameter_type != 'float':
#                 status = False
#                 print('Only float parameters allowed in MCMC treatment')
#                 print('Remove: '+par.name)
#             elif par.mcmc_step is None:
#                 status = False
#                 print('MCMC step size missing for: '+par.name)
#     if status:
#         chain = optimizer.mcmc(n_dof, chi2n, n_mcmc)
#         print('MCMC chain produced.')
#         print('fraction accepted =',self.optimizer.accept_fraction)
#         return chain
#     else:
#         return None
#
# file1 = open("{}\\myfile.txt".format(os.getenv('SSIM_TEMP_DIRECTORY')),"w")
# file1.write("Hello \n")
# # file1.write( "{}".format(os.getenv('SSIM_TRANSFER_DIRECTORY')) )
# for k, v in os.environ.items():
#     file1.write(f'{k}={v}\n')
# file1.close() #to change file access modes
