import requests
import pickle
import pycountry
import pandas
import datetime
import pypmca
import sys
import translate

from syncro import *

'''
	a set of all the helper functions used for lookup functions, mutators, etc
'''


# allows for the installation of a library from a file
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

'''
	returns an Ssim-formatted version of a Karlen variable through string parsing and fragment replacement

	for instance, infected_v -> Infected (Variants)
				  reported_v -> Cases (Variants)
'''
def getFancyName(variable_name:str):

	# total -> Total
    if variable_name.lower() == 'total':
        return 'Total'

	# take out underscores and convert to lower case for parsing. so, infected_v -> infected v
    variable_name = variable_name.replace('_', ' ').lower()

	# whether the variable is daily or cumulative
    interval = ''

    '''
		if the keyword 'daily' is found, mark the interval as daily and strip it from the string.
		for ex., 'daily infected' -> 'infected'

		else, if any of the cumulative keywords are found ('total', 'sum', 'cumulative'), mark and strip.
		for ex. 'total reported' -> 'reported'
	'''
    if re.findall('daily', variable_name) != []:
        interval = 'daily'
        variable_name = re.sub('daily|-', '', variable_name).strip()
    elif re.findall('total|cumulative|sum', variable_name) != []:
        interval = 'cumulative'
        variable_name = re.sub('total|cumulative|sum|-', '', variable_name).strip()

	# ex. 'non icu hospitalized' -> 'Non icu hospitalized'
    variable_name = variable_name.replace('non ', 'Non ')
	# ex. 'non icu rel' -> 'Non icu Released'
    variable_name = variable_name.replace(' rel', ' Released')
	# ex. 'vacc cand' -> 'Vaccination Candidates'
    variable_name = variable_name.replace('vacc ', 'Vaccination ')
    variable_name = variable_name.replace(' cand', ' Candidates')
	# ex. 'sus vacc cand' -> 'Susceptible Vaccination Candidates'
    variable_name = variable_name.replace('sus ', 'Susceptible ')
	# what Karlen calls 'reported', we call 'cases'
    variable_name = variable_name.replace('reported', 'cases')
	# ex.
    variable_name = variable_name.replace('rec ', 'Recovered ')
    variable_name = variable_name.replace('mortality', 'deaths')

	# ex. 'infected v' -> 'infected (Variants)'
    if variable_name[-2:] == ' v':
        variable_name = variable_name.replace(' v', ' (Variants)')
	# ex.'Non Icu hospitalized' -> 'Non ICU hospitalized'
    variable_name = variable_name.title().replace('Icu', 'ICU')

	# whether daily or cumulative is tacked onto the end of the variable name if determined through input
    if interval != '':
        variable_name = '{} - {}'.format(variable_name, interval.title())

    return variable_name


'''
	in the getData transformer, if the Karlen sources are misnamed (for example, if a daily variable is misnamed
	as being cumulative), then we test to see if the time series is monotonic; if it's not, it must be daily
'''
# https://stackoverflow.com/questions/4983258/python-how-to-check-list-monotonicity/4983359
# Answer by user: 6502
def non_increasing(L):
    return all(x>=y for x, y in zip(L, L[1:]))
def non_decreasing(L):
    return all(x<=y for x, y in zip(L, L[1:]))
def monotonic(L):
    return non_increasing(L) or non_decreasing(L)

'''
	getFancyName usually returns names without the 'daily' and 'cumulative' qualifiers, so this function
	tests the time series for monotonicity and returns daily if not monotonic
'''
def standardPopName(pop:pypmca.Population):

    variable_name = getFancyName(pop.name)

    if re.findall('total|daily|cumulative', variable_name.lower()):
        return variable_name

    standard_Ssim_name = '{} - {}'.format(
        variable_name,
        'Cumulative' if monotonic(pop.history) else 'Daily'
    )
    return standard_Ssim_name


'''
	in the data repositories, Karlen gives German states by their English names, while the pycountry lookup
	package that we use to get the regions of the models gives the names in German, so to prevent there being
	two jurisdictions in the chart referring to the same region, we'll go with the native state names and
	translate the English names to German for consistency.

	this is to prevent having a model of Bayern but data from Bavaria (same place, but will be different in
	the charting display)
'''
def germanStateName(state_name:str):

    # hella slow
    # return translate.Translator(from_lang="en", to_lang="de").translate(state_name).replace('-', '_')

	# lut for the German state names
    german_state_LUT = {
        'Baden-Wurttemberg' : 'Baden-Württemberg',
        'Bavaria' : 'Bayern',
        'Hesse' : 'Hessen',
        'Lower Saxony' : 'Niedersachsen',
        'Mecklenburg-West Pomerania' : 'Mecklenburg-Vorpommern',
        'North Rhine-Westphalia' : 'Nordrhein-Westfalen',
        'Rhineland-Palatinate' : 'Rheinland-Pfalz',
        'Saxony' : 'Sachsen',
        'Saxony-Anhalt' : 'Sachsen-Anhalt',
        'Thuringia' : 'Thüringen'
    }

	# if the state name isn't the same in English as it is in German
    if state_name in german_state_LUT:
        return german_state_LUT[state_name].replace('-', '_')

	# the other of the 16 states
    otherStates = ['Schleswig-Holstein', 'Hamburg', 'Bremen', 'Brandenburg', 'Berlin', 'Saarland']

	# if it's one of the German states that doesn't need to be translated, return the input
    if state_name in otherStates:
        return state_name.replace('-', '_')
    else:
		# if the input string isn't a German state at all, return None
        return None

'''
	tests the movement of a time series by testing whether some minimum percentage of values
	in the series are unique. for ex, [1,1,2,3,4] has 80% unique values (and so will pass
	depending on the threshold given), whereas [1,1,1,1,1] is only 10% unique.

	this function is used to sort through the Karlen .pypm model objects to see which ones
	have a moving infection and which ones don't. at the time this function was written, not
	all of the models were maintained (or parametrised), so this is used in the getRepos
	transformer to filter good models from bad ones
'''
def movementThreshold(series, desired_proportion):
    if (desired_proportion < 0) or (desired_proportion > 1):
        print('*** ERROR: the proportion must be between 0 and 1 ***')
        return None
    # ratio of unique values to total number of values
    ratio_of_unique_values = len(set(series))/len(series)
    if ratio_of_unique_values < desired_proportion:
        return False
    else:
        return True

'''
	translates integer values from the validated PriorFunction column in the ParameterTable
	scenario-level table and turns it into either 'norm' (normal) or 'uniform' (uniform)

	used in the getRepos (model deconstruction) and getExpectations (model rebuilding) transformers
'''
def tablePriorDist(input:int):
    if input == None:
        return 3
    if isinstance(input, int) or isinstance(input, float):
        return 'uniform' if int(input)==1 else 'norm' if int(input)==2 else 3
    if isinstance(input, str):
        return 1 if input=='uniform' else 2 if input=='norm' else 3
    return None

'''
	translates integer values from the validated Fixed/Variable column in the ParameterTable
	scenario-level table and turns it into either 'variable' (normal) or 'fixed' (uniform)

	used in the getRepos (model deconstruction) and getExpectations (model rebuilding) transformers
'''
def tableStatus(input:int):
    if isinstance(input, int) or isinstance(input, float):
        return 'fixed' if input == 1 else 'variable'
    elif isinstance(input, str):
        return 1 if input == 'fixed' else 2
    return None

# was used in the getRepos and getExpectations transformers to translate integer values to number types
def tableType(input:int):
    if isinstance(input, int) or isinstance(input, float):
        return 'int' if input == 1 else 'float'
    elif isinstance(input, str):
        return 1 if input == 'int' else 2
    return None

# capitalises the first character in a string while not altering the other (as does .title())
def capitaliseFirst(string:str):
    return string[0].upper() + string[1:]

'''
	a diff function used in the getExpectations and getIterations transformers to retrieve daily
	data from cumulative time series, since daily/cumulative pairs aren't always complete in the
	simulation
'''
def delta(cumul):
    diff = []
    for i in range(1, len(cumul)):
        diff.append(cumul[i] - cumul[i - 1])
    # first daily value is repeated since val(t0-1) is unknown
    diff.insert(0,diff[0])
    return diff

# converts a string to camel case
def camelify(x):
	return ''.join(capitaliseFirst(i) for i in x.replace('_', ' ').replace(',', ' ').split(' '))

# opens a stored .pypm model object
def openModel(my_pickle):
    try:
        model = pickle.loads(my_pickle)
    except:
        print('*** Model NOT loaded ***')

    time_step = model.get_time_step()

    if time_step > 1.001 or time_step < 0.999:
        print('*** Model NOT loaded ***')
        print('Currently, ipypm only supports models with time_step = 1 day.')
    return model

# downloads a model given a URL. deprecated in favour of pypmca.Model.open...
def downloadModel(theURL):

    try:
        model_response = requests.get(theURL);
    except requests.exceptions.RequestException as error:
        print('Error retrieving model folder list over network:')
        print()
        print(error)
        return None
    myPickle = model_response.content
    return openModel(myPickle)

# retrieves an integer from an input string
def getSubinteger(string:str):
    string_containing_integer = ''.join([s for s in list(string) if s.isdigit()])
    if not string_containing_integer:
        return None
    return int(string_containing_integer)

'''
	parses a string (usually a model region) and retrieves the date range.
	sample inputs are '<10', '20-59', '89+', '10to50', 'bw_a2', 'Germany_age', 'BC'
	returns a dictionary indexed by 'lower' and 'upper'
'''
def ageRangeString(the_string:str):

	# if the input string is a legit country or province/state/city name, no information
    if the_string in [x.name for x in pycountry.countries]:
        return {}
    if the_string in [x.name for x in pycountry.subdivisions]:
        return {}

	# no information if there are no numbers in the string
    if not re.search('\d', the_string):
        return {}

	# convert to lower case for less cases during parsing
    the_string = the_string.lower()

    '''
		for the data set Germany_age, the regions tale the form:
			<ISO 3166-2 code>_a<digit>
		the first two characters before the underscore give the region of the data set, the 'a' is for 'age' (presumably)
		and the number refers to the relevant age band of the Robert-Koch Institut (RKI) data sets and descriptions.
		the RKI age bands with indices are (0) <4, (1) 5-14, (2) 15-34, (3) 35-59, (4) 60-79 and (5) 80+.

		below we set up a lut for the min and max ages, and parse the region name to return the correct age range.
	'''
	# if the input string matches the format
    if re.compile('[a-zA-Z]{2}_a[0-5]*').match(the_string):

		# luts for the RKI age bands
        DE_lower_ages = {0:0, 1: 5, 2:15, 3:35, 4:60, 5:80}
        DE_upper_ages = {0:4, 1:14, 2:34, 3:59, 4:79, 5:None}

		# the age band index is the only number in the string, fetch it
        rki_age_band_index = getSubinteger(the_string)
        from_age = DE_lower_ages[rki_age_band_index]
        to_age = DE_upper_ages[rki_age_band_index]

        return {'lower': from_age, 'upper': to_age}

	# search for the key words 'under', 'less', '<'. zB. '<10', 'under 20', etc
    if re.findall('under|less|<', the_string):
        return {'lower': None, 'upper': getSubinteger(the_string)}

	# search for the key words 'over', 'plus', '+'. zB. 'over 80', '89+', etc
    if re.findall('over|plus|\+|>', the_string):
        return {'lower': getSubinteger(the_string), 'upper': None}

	# some data sets have age unknown
    if 'unknown' in the_string:
        return {'lower': None, 'upper': None}

    if re.findall(' to |\dto\d|_|-', the_string):

        '''
    		searching for the keywords 'to' (with or without surrounding spaces), hyphen and underscore.
    		zB. '18 to 45', '8to18', '25_39', '40-50', '0-17'

    		split the string by the keyword, and assuming that there are no extraneous integers in the string,
    		extract the integers from the two pieces and return them. the age '0' returns None
    	'''

        string_fragment_list = re.split('to|_|-', the_string)
        from_age = getSubinteger(string_fragment_list[0])
        to_age = getSubinteger(string_fragment_list[1])
        if from_age == 0:
            return {'lower': None, 'upper': to_age}
        else:
            return {'lower': from_age, 'upper': to_age}

    elif re.findall('\ds', the_string):

        '''
    		some data sets have their age stratification in 10-year bands, for which the age range is denoted only
    		by the start of the band. zB. 'BC 10s', 'fraser_40s'

    		assuming that there are no extraneous integers in the string, extract the integer from the input string
    		and find the upper limit of the band by adding 9.
    		zB. '40s' -> '40 to 49'
    	'''

		# split by a sensible separator (if there is one)
        string_fragment_list = re.split(' |_|-', the_string)
		# filter the substrings by possession of an integer
        subStr = [string for index, string in enumerate(string_fragment_list) if re.findall('\ds', string)]
		# retrieve the integer from the first string piece with an integer and mark that as the starting age
        from_age = getSubinteger( subStr[0] )
		# add 9 to get the upper age of the band
        to_age = from_age + 9
        return {'lower': from_age, 'upper': to_age}

	# if all the check fail, give up
    return {'lower': None, 'upper': None}


'''
	this retrieves the age range from a model name
    ex. 'ca65plus_2_5_1005.pypm'

    we assume that the age information is contained in the first fragment before the underscore,
    so split the string at the underscore and run the ageRangeString in the fragment

    returns pretty print for the jurisdiction column of PypmcaModels

'''
def ageRangeModel(model_name:str):

    first_string_fragment = model_name.split('_')[0]

    age_band_dict = ageRangeString(first_string_fragment)

    if age_band_dict == {}:
        return ''

    if set(age_band_dict.values()) == {None}:
        return ''

    if age_band_dict['lower'] == None:
        return 'under {}'.format(age_band_dict['upper'])

    if age_band_dict['upper'] == None:
        return 'over {}'.format(age_band_dict['lower'])

    return '{} -> {}'.format(age_band_dict['lower'], age_band_dict['upper'])

'''
    reads the version number of the model
    ex. 'ca65plus_2_5_1005.pypm'


    the version number are the second and third string segments when split by underscore. extract the
    integers from those pieces and paste them together in a format string
'''
def modelVersion(model_name:str):

    if 'ref' in model_name:
        the_date_in_digits = [x for x in model_name.replace('.pypm', '').split('_') if x.isdigit()]
        if len(the_date_in_digits) == 1:
            return '{}.0'.format(the_date_in_digits[0])
        else:
            return '.'.join(the_date_in_digits)

    model_name = model_name.replace('.pypm', '').replace('_d', '')
    first, sec = model_name.split('_')[1:3]
    return '{}.{}'.format(first, sec)

'''
    reads the publishing date of the model
    ex. 'ca65plus_2_5_1005.pypm'

    the date of the model is given by the last 4 digits of the model name before the extension:
    the first two digits are the month, and the last two digits are the day. since the year is not
    given (and based of the date at which these models each became available), we assume that every
    month before the current one happened in the previous year (2020)
'''
def modelDate(model_name:str):

    # we're not treating reference models on this package
    if 'reference' in model_name:
        return None

    # cut the extension (some model names have an extra fragment '_d', so we cut that too)
    model_name = model_name.replace('.pypm', '').replace('_d', '')
    # the date stub is now the final fragment
    publishing_date_stub = model_name.split('_')[-1]

    # if there's no date, return None
    if publishing_date_stub == '':
        return None
    # after taking off trailing '_d', if the date fragment doesn't follow the four character convention, ignore it
    if len(publishing_date_stub) != 4:
        return None

    # the month is given by the first two characters, the day by the last two
    month = int(publishing_date_stub[:2])
    day = int(publishing_date_stub[2:])
    # calculate the most likely date (based on the number of the current month) and return a date
    return datetime.date(2021 if month < datetime.datetime.now().month else 2020, month, day)

'''
    takes in the country and the filename of the model and returns a a jurisdiction and an ISO 3166-2 code
    for the subdivision.

    some of the 'countries' are actual countries ('Canada', 'Germany', etc), while at other times the 'country'
    is actually a state/province (ex. 'California', 'BC' if stratified models are available), else it could be
    'EU'.

    this function combines these two strings to find a region using pycountry lookups
'''
def regionInfo(country_name:str, model_name:str):

    '''
        as with the model name 'ca65plus_2_5_1005', the ISO 3166-2 code is given by the first two characters
        of the filename string when split by underscores. retrieve this fragment.
    '''
    string_fragment_list = model_name.replace(' ', '').split('_')
    twoLetter = string_fragment_list[0][:2].upper()

    iso_3166_code = ''
    fancy_region_name = ''

    '''
        sort out the true country names. example function calls are given for each case
    '''

    # regionInfo('USA', 'oh_2_8_0316')
    if country_name == 'USA':
        country_name = 'United States'
    # regionInfo('California', 'ca65plus_2_5_1005.pypm'))
    elif country_name == 'California':
        country_name = 'United States'

    # if it's actually a country we were given:
    if country_name in [x.name for x in pycountry.countries]:
        # regionInfo('Canada', ' qc_2_8_0311.pypm')
        country_code = pycountry.countries.get(name=country_name).alpha_2
        iso_3166_code = '{}-{}'.format(country_code, twoLetter)
        fancy_region_name = pycountry.subdivisions.get(code=iso_3166_code).name

    # if the country is 'EU' then the first two characters will be the ISO 3166 country code
    elif country_name == 'EU':
        # regionInfo('EU', 'it_2_8_0224.pypm')
        localeInfo = pycountry.countries.get(alpha_2=twoLetter)
        iso_3166_code = '{}-{}'.format(country_name, twoLetter)
        fancy_region_name = localeInfo.name

    elif country_name == 'reference':
        # regionInfo('reference', 'ref_model_2.pypm')
        # get the numbers from the string
        the_date_in_digits = [x for x in model_name.replace('.pypm', '').split('_') if x.isdigit()]
        # print the digits at the end
        # fancy_region_name = '{} ({})'.format(country_name.title(), ' '.join(the_date_in_digits))
        fancy_region_name = country_name.title()

    if country_name == 'BC':

        lut = { # health authorities lut
            'coastal' : 'Vancouver Coastal', # North Shore/East Garibaldi, Richmond, Vancouver, Unknown
            'northern' : 'Northern', # Northeast, Northern Interior, Northwest, Unknown
            'island' : 'Vancouver Island', # Central, North, South
            'interior' : 'Interior',  #  East Kootenay, Okanagan, Kootenay Boundary, Thompson Cariboo Shuswap
            'fraser' : 'Fraser' # Fraser East, North, South, Unknown
        }

        iso_3166_code = 'CA-BC'

        if twoLetter == 'BC':
            # regionInfo('BC', 'bc60_2_3_0911.pypm')
            fancy_region_name = 'British Columbia'
        else:
            # regionInfo('BC', 'interior_2_8_0309.pypm')
            fancy_region_name = 'British Columbia - {}'.format( lut[ string_fragment_list[0] ].title() )

    return {'code' : iso_3166_code, 'name' : fancy_region_name}
