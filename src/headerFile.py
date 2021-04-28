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
def getFancyName(varName:str):

	# total -> Total
    if varName.lower() == 'total':
        return 'Total'

	# take out underscores and convert to lower case for parsing. so, infected_v -> infected v
    varName = varName.replace('_', ' ').lower()

	# whether the variable is daily or cumulative
    interval = ''

    '''
		if the keyword 'daily' is found, mark the interval as daily and strip it from the string.
		for ex., 'daily infected' -> 'infected'

		else, if any of the cumulative keywords are found ('total', 'sum', 'cumulative'), mark and strip.
		for ex. 'total reported' -> 'reported'
	'''
    if re.findall(r'daily', varName) != []:
        interval = 'daily'
        varName = re.sub('daily|-', '', varName).strip()
    elif re.findall(r'total|cumulative|sum', varName) != []:
        interval = 'cumulative'
        varName = re.sub('total|cumulative|sum|-', '', varName).strip()

	# ex. 'non icu hospitalized' -> 'Non icu hospltalized'
    varName = varName.replace('non ', 'Non ')
	# ex. 'non icu rel' -> 'Non icu Released'
    varName = varName.replace(' rel', ' Released')
	# ex. 'vacc cand' -> 'Vaccination Candidates'
    varName = varName.replace('vacc ', 'Vaccination ')
    varName = varName.replace(' cand', ' Candidates')
	# ex. 'sus vacc cand' -> 'Susceptible Vaccination Candidates'
    varName = varName.replace('sus ', 'Susceptible ')
	# what Karlen calls 'reported', we call 'cases'
    varName = varName.replace('reported', 'cases')
	# ex.
    varName = varName.replace('rec ', 'Recovered ')
    varName = varName.replace('mortality', 'deaths')

	# ex. 'infected v' -> 'infected (Variants)'
    if varName[-2:] == ' v':
        varName = varName.replace(' v', ' (Variants)')
	# ex.'Non Icu hospitalized' -> 'Non ICU hospitalized'
    varName = varName.title().replace('Icu', 'ICU')

	# whether daily or cumulative is tacked onto the end of the variable name if determined through input
    if interval != '':
        varName = '{} - {}'.format(varName, interval.title())

    return varName


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
	teste the time series for monotonicity and returns daily if not monotonic
'''
def standardPopName(pop:pypmca.Population):

    varName = getFancyName(pop.name)

    if re.findall('total|daily|cumulative', varName.lower()):
        return varName

    standardName = '{} - {}'.format(
        varName,
        'Cumulative' if monotonic(pop.history) else 'Daily'
    )
    return standardName


'''
	in the data repositories, Karlen gives German states by their English names, while the pycountry lookup
	package that we use to get the regions of the models gives the names in German, so to prevent there being
	two jurisdictions in the chart referring to the same region, we'll go with the native state names and
	translate the english names to German for consistency.

	this is to prevent having a model of Bayern but data from Bavaria (same place, but will be different in
	the charting display)
'''
def germanStateName(stateName:str):

    # hella slow
    # return translate.Translator(from_lang="en", to_lang="de").translate(stateName).replace('-', '_')

	# lut for the German state names
    germanStateLUT = {
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

	# if the state name isn;t the same in ENglish as it is in German
    if stateName in germanStateLUT:
        return germanStateLUT[stateName].replace('-', '_')

	# the other of the 16 states
    otherStates = ['Schleswig-Holstein', 'Hamburg', 'Bremen', 'Brandenburg', 'Berlin', 'Saarland']

	# if it's one of the German states that doesn't needd to be translated, return the input
    if stateName in otherStates:
        return stateName.replace('-', '_')
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

'''
	translates integer values from the validated PriorFunction column in the ParameterTable
	scenario-level table and turns it into either 'norm' (normal) or 'uniform' (uniform)

	used in the getRepos (model deconstruction) and getExpectations (model rebuilding) transformers
'''
def tablePriorDist(input):
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
def tableStatus(input):
    if isinstance(input, int) or isinstance(input, float):
        return 'fixed' if input == 1 else 'variable'
    elif isinstance(input, str):
        return 1 if input == 'fixed' else 2
    return None

# was used in the getRepos and getExpectations transformers to translate integer values to number types
def tableType(input):
    if isinstance(input, int) or isinstance(input, float):
        return 'int' if input == 1 else 'float'
    elif isinstance(input, str):
        return 1 if input == 'int' else 2
    return None

# capitalises the first character in a string while not altering the other (as does .title())
def capitaliseFirst(string):
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

# converts a strint to camel case
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

# downloads a model given a URL. deprecated in favuor of pypmca.Model.open...
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

# retrieves an integer from an input string
def getSubinteger(string:str):
    numString = ''.join([s for s in list(string) if s.isdigit()])
    if not numString:
        return None
    return int(numString)

'''
	parses a string (usually a model region) and retrieves the date range.
	sample inputs are '<10', '20-59', '89+', '10to50', 'bw_a2', 'Germany_age', 'BC'
	returns a dictionary indexed by 'lower' and 'upper'
'''
def ageRangeString(theString:str):

	# if the input string is a legit country or province/state/city name, no information
    if theString in [x.name for x in pycountry.countries]:
        return {}
    if theString in [x.name for x in pycountry.subdivisions]:
        return {}

	# no information if there are no numbers in the string
    if not re.search('\d', theString):
        return {}

	# convert to lower case for less cases during parsing
    theString = theString.lower()

    '''
		for the data set Germany_age, the regions tale the form:
			<ISO 3166-2 code>_a<digit>
		the first twe characters before the underscore give the region of the dataset, the 'a' is for 'age' (presumably)
		and the number refers to the relevant age band of the Robert-Koch Institut (RKI) data sets and descriptions.
		the RKI age bands with indices are (0) <4, (1) 5-14, (2) 15-34, (3) 35-59, (4) 60-79 and (5) 80+.

		below we set up a lut for the min and max ages, and parse the region name to return the correct age range.
	'''
	# if the inut string matches the format
    if re.compile('[a-zA-Z]{2}_a[0-5]*').match(theString):

		# luts for the RKI age bands
        DE_lower_ages = {0:0, 1: 5, 2:15, 3:35, 4:60, 5:80}
        DE_upper_ages = {0:4, 1:14, 2:34, 3:59, 4:79, 5:None}

		# the age band index is the only number in the string, fetch it
        rkiIndex = getSubinteger(theString)
        fromAge = DE_lower_ages[rkiIndex]
        toAge = DE_upper_ages[rkiIndex]

        return {'lower': fromAge, 'upper': toAge}

	# search for the key words 'under', 'less', '<'. zB. '<10', 'under 20', etc
    if re.findall('under|less|<', theString):
        return {'lower': None, 'upper': getSubinteger(theString)}

	# search for the key words 'over', 'plus', '+'. zB. 'over 80', '89+', etc
    if re.findall('over|plus|\+|>', theString):
        return {'lower': getSubinteger(theString), 'upper': None}

	# some data sets have age unknown
    if 'unknown' in theString:
        return {'lower': None, 'upper': None}

    if re.findall(' to |\dto\d|_|-', theString):

        '''
    		searching for the keywords 'to' (with or without surrounding spaces), hyphen and underscore.
    		zB. '18 to 45', '8to18', '25_39', '40-50', '0-17'

    		split the string by the keyword, and assuming that there are no extraneous integers in the string,
    		extract the integers from the two pieces and return them. the age '0' returns None
    	'''

        subStrs = re.split('to|_|-', theString)
        fromAge = getSubinteger(subStrs[0])
        toAge = getSubinteger(subStrs[1])
        if fromAge == 0:
            return {'lower': None, 'upper': toAge}
        else:
            return {'lower': fromAge, 'upper': toAge}

    elif re.findall('\ds', theString):

        '''
    		some data sets have their age stratification in 10-year bands, for which the age range is denoted only
    		by the start of the band. zB. 'BC 10s', 'fraser_40s'

    		assuming that there are no extraneous integers in the string, extract the integer fron the input string
    		and find the upper limit of the band by adding 9.
    		zB. '40s' -> '40 to 49'
    	'''

		# split by a sensible separator (if there is one)
        subStrs = re.split(' |_|-', theString)
		# filter the substrings by possession of an integer
        subStr = [string for index, string in enumerate(subStrs) if re.findall('\ds', string)]
		# retrieve the integer from the first string piece with an integer and mark that as the starting age
        fromAge = getSubinteger( subStr[0] )
		# add 9 to get the upper age of the band
        toAge = fromAge + 9
        return {'lower': fromAge, 'upper': toAge}

	# if all the check fail, give up
    return {'lower': None, 'upper': None}


'''
	this retrieves the age range from a model name
    ex. 'ca65plus_2_5_1005.pypm'

    we assume that the age information is contained in the first fragment before the underscore,
    so split the string at the underscore and run the ageRangeString in trhe fragment

    returns pretty print for the jurisdiction column of PypmcaModels

'''
def ageRangeModel(modelName:str):

    firstBit = modelName.split('_')[0]

    ageDict = ageRangeString(firstBit)

    if ageDict == {}:
        return ''

    if set(ageDict.values()) == {None}:
        return ''

    if ageDict['lower'] == None:
        return 'under {}'.format(ageDict['upper'])

    if ageDict['upper'] == None:
        return 'over {}'.format(ageDict['lower'])

    return '{} -> {}'.format(ageDict['lower'], ageDict['upper'])

'''
    reads the version number of the model
    ex. 'ca65plus_2_5_1005.pypm'


    the version number are the second and third string segments when split by underscore. extract the
    integers from those pieces and paste them together in a format string
'''
def modelVersion(modelName):

    if 'ref' in modelName:
        theDigits = [x for x in modelName.replace('.pypm', '').split('_') if x.isdigit()]
        if len(theDigits) == 1:
            return '{}.0'.format(theDigits[0])
        else:
            return '.'.join(theDigits)

    modelName = modelName.replace('.pypm', '').replace('_d', '')
    first, sec = modelName.split('_')[1:3]
    return '{}.{}'.format(first, sec)

'''
    reads the publishing date of the model
    ex. 'ca65plus_2_5_1005.pypm'

    the date of the model is given by the last 4 digits of the model name before the extension:
    the first two digits are the month, and the last two digits are the day. since the year is not
    given (and based of the date at which these models each became available), we assume that every
    month before the current one happened in the previous year (2020)
'''
def modelDate(modelName):

    # we're not treating reference models on this package
    if 'reference' in modelName:
        return None

    # cut the extension (some model names have an extra fragment '_d', so we cut that too)
    modelName = modelName.replace('.pypm', '').replace('_d', '')
    # the date stub is now the final fragment
    theStub = modelName.split('_')[-1]

    # if there's no date, return None
    if theStub == '':
        return None
    # after taking off trailing '_d', if the date fragment doesn't follow the four character convention, ignore it
    if len(theStub) != 4:
        return None

    # the month is given by the first two characters, the day by the last two
    month = int(theStub[:2])
    day = int(theStub[2:])
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
def regionInfo(countryName:str, modelName:str):

    '''
        as with the model name 'ca65plus_2_5_1005', the ISO 3166-2 code is given by the first two characters
        of the filename string when split by underscores. retrieve this fragment.
    '''
    theSplit = modelName.replace(' ', '').split('_')
    twoLetter = theSplit[0][:2].upper()

    iso3166Code = ''
    finalName = ''

    '''
        sourt out the true country names. example function calls are given for each case
    '''

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

    # if the country is 'EU' then the first two characters will be the ISO 3166 country code
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

        lut = { # health authorities lut
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
