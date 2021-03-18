for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import requests
import os

import sys
import pickle
import pypmca
import pycountry
import subprocess
import pandas
from syncro import *

def openModel(my_pickle):
    model = pickle.loads(my_pickle)
    time_step = model.get_time_step()
    if time_step > 1.001 or time_step < 0.999:
        print('Filename: ' + filename)
        print('*** Model NOT loaded ***')
        print('Currently, ipypm only supports models with time_step = 1 day.')
    return model

env = ssimEnvironment()
myScenario = scenario()

def getSubinteger(string:str):
    numString = ''.join([s for s in list(string) if s.isdigit()])
    return int(numString)

def ageRange(modelName:str):

    firstBit = modelName.split('_')[0]

    if any([substring in firstBit for substring in ['under', 'less']]):
        return 'under {}'.format(getSubinteger(firstBit))

    if any([substring in firstBit for substring in ['over', 'plus']]):
        # extra space to make sure that all strings are the same length
        return ' over {}'.format(getSubinteger(firstBit))

    if 'to' in firstBit:
        subStrs = firstBit.split('to')
        fromAge = getSubinteger(subStrs[0])
        toAge = getSubinteger(subStrs[1])
        return '{} -> {}'.format(fromAge, toAge)

    return 8*' '

def regionInfo(countryName:str, modelName:str):

    theSplit = modelName.replace(" ", "").split('_')
    twoLetter = theSplit[0][:2].upper()

    iso3166Code = ''
    finalName = ''

    if countryName == 'USA':
        countryName = 'United States'
    elif countryName == 'California':
        countryName = 'United States'
    # elif countryName == moda'

    # if it's actually a country we were given:
    if countryName in [x.name for x in pycountry.countries]:
        countryCode = pycountry.countries.get(name=countryName).alpha_2
        iso3166Code = '{}-{}'.format(countryCode, twoLetter)
        finalName = pycountry.subdivisions.get(code=iso3166Code).name

    elif countryName == 'EU':
        localeInfo = pycountry.countries.get(alpha_2=twoLetter)
        iso3166Code = '{}-{}'.format(countryName, twoLetter)
        finalName = localeInfo.name

    elif countryName == 'reference':
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
            finalName = 'British Columbia'
        else:
            finalName = lut[ theSplit[0] ].title()

    return '({:5}) {}'.format(iso3166Code, finalName)

# print(regionInfo('Canada', ' qc_2_8_0311.pypm'))
# print(regionInfo('EU', 'it_2_8_0224.pypm'))
# print(regionInfo('reference', 'ref_model_2.pypm'))
# print(regionInfo('USA', 'oh_2_8_0316'))
# print(regionInfo('California', 'ca65plus_2_5_1005.pypm'))
# print(regionInfo('Germany', 'st_2_8_0307.pypm'))
# print(regionInfo('Brazil', 'pr_2_3_0624_d.pypm'))
# print(regionInfo('BC', 'bc60_2_3_0911.pypm'))

print(regionInfo('BC', 'interior_2_8_0309.pypm'))

# jurisDictionary = {}

# foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
# countryFolders = foldersResponse.json()
# countryList = list(countryFolders.keys())

# modelsAvailable = []

# for country in ["BC"]: # countryList:

#     folder = countryFolders[country]
#     countryName = folder.split('/')[-1]

#     modelsResponse = requests.get('http://data.ipypm.ca/list_models/{}'.format(folder))

#     modelFilenames = modelsResponse.json()
#     modelList = list(modelFilenames.keys())

#     for modelName in modelList:

#         modelFn = modelFilenames[modelName]
#         filename = modelFn.split('/')[-1]

#         modelURL = 'http://data.ipypm.ca/get_pypm/{}'.format(modelFn)

#         modelsAvailable.append({
#             # 'Region': regionInfo(countryName, filename),
#             'Name': filename,
#             # 'Description': modelDescrip,
#             'URL' : modelURL
#         })

        # break

#         pypmResponse = requests.get(modelURL, stream=True)

#         myPickle = pypmResponse.content
#         model = openModel(myPickle)

#         model.save_file('{}.temp\\{}'.format(env.LibraryFilePath, filename))
#         modelDescrip = model.description.replace('\"', '').replace('\'', '')

#         jurisDictionary[fullModelName] = modelDescrip


#         # break

    # break


# theJurisdictions = datasheet(myScenario, 'epi_Jurisdiction', empty=True)
# theJurisdictions = theJurisdictions.drop(columns=['JurisdictionID'])

# theJurisdictions.Name = pandas.Series(jurisDictionary.keys())
# theJurisdictions.Description = pandas.Series(jurisDictionary.values())

# modelsAvail = pandas.DataFrame(modelsAvailable).drop(columns=['URL'])

# theModels = datasheet(myScenario, "modelKarlenPypm_ModelsAvailable", empty=True)
# theModels = theModels.drop(columns=['ModelsAvailableID'])

# theModels.Region = modelsAvail.Region
# theModels.Name = modelsAvail.Name
# theModels.URL = modelsAvail.URL
# theModels.Description = [re.sub('[\'\"]', '', desc) for desc in modelsAvail.Description]

# saveDatasheet(myScenario, theModels, "modelKarlenPypm_ModelsAvailable")
