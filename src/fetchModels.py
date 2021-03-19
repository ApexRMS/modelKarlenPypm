#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import requests
import pickle
import pycountry
import pandas

from syncro import *

def unaccumulate(a):
    return [a[0]] + [t - s for s, t in zip(a, a[1:])]

def camelify(x):
	return ''.join(i.capitalize() for i in x.replace('_', ' ').replace(',', ' ').split(' '))

def openModel(my_pickle):
    model = pickle.loads(my_pickle)
    time_step = model.get_time_step()
    if time_step > 1.001 or time_step < 0.999:
        print('Filename: ' + filename)
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
        return ' over {}'.format(getSubinteger(firstBit))

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

    return 8*' '

def regionInfo(countryName:str, modelName:str):

    theSplit = modelName.replace(" ", "").split('_')
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
        finalName = '{} ({})'.format(countryName.title(), ' '.join(theDigits))

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
            finalName = lut[ theSplit[0] ].title()

    return '({:5}) {:26}'.format(iso3166Code, finalName)


env = ssimEnvironment()
myScenario = scenario()

jurisDictionary = {}

foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
countryFolders = foldersResponse.json()
countryList = list(countryFolders.keys())

modelsAvailable = []

for country in countryList:

    folder = countryFolders[country]
    countryName = folder.split('/')[-1]

    modelsResponse = requests.get('http://data.ipypm.ca/list_models/{}'.format(folder))

    modelFilenames = modelsResponse.json()
    modelList = list(modelFilenames.keys())

    for modelName in modelList:

        modelFn = modelFilenames[modelName]
        filename = modelFn.split('/')[-1]

        modelURL = 'http://data.ipypm.ca/get_pypm/{}'.format(modelFn)

        modelsAvailable.append({
            'Region': '{} {}'.format(regionInfo(countryName, filename), ageRange(filename)),
            'Name': filename,
            'URL' : modelURL
        })

modelsAvail = pandas.DataFrame(modelsAvailable)

duplicateRegions = list(set(modelsAvail.Region[modelsAvail.Region.duplicated()]))
repeatedIndices = modelsAvail.index[modelsAvail['Region'].isin(duplicateRegions)]

for index in repeatedIndices:
    modelName = modelsAvail.Name[index]
    date = modelName.split('_')[-1].replace('.pypm', '')
    newDate = '({}/{})'.format(date[:2], date[2:])
    regionName = modelsAvail.Region[index]
    modelsAvail.iloc[index]['Region'] = regionName[:-7] + newDate

theJurisdictions = datasheet(myScenario, 'epi_Jurisdiction', empty=True)
theJurisdictions = theJurisdictions.drop(columns=['JurisdictionID'])

theJurisdictions.Name = modelsAvail.Region
theJurisdictions.Description = modelsAvail.URL

saveDatasheet(myScenario, theJurisdictions, "epi_Jurisdiction")

theModels = datasheet(myScenario, "modelKarlenPypm_ModelsAvailable", empty=True)
theModels = theModels.drop(columns=['ModelsAvailableID'])

theModels.Region = modelsAvail.Region
theModels.Name = modelsAvail.Name
theModels.URL = modelsAvail.URL

saveDatasheet(myScenario, theModels, "modelKarlenPypm_ModelsAvailable")
