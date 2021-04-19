#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import requests
import collections
import datetime

from syncro import *
from headerFile import *

env = ssimEnvironment()
myScenario = scenario()

foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
countryFolders = foldersResponse.json()
countryList = list(countryFolders.keys())

modelsAvailable = []

renamingMap = {}; renamingCounter = 0

PARAMETER_ATTIBUTES = ['name', 'description', 'initial_value', 'parameter_min', 'parameter_max']
defaultParameters = pandas.DataFrame()

for country in countryList: # ['Canada', 'Germany', 'Brazil', 'USA', 'EU', 'BC', 'California']:

    if 'ref' in country.lower():
        continue

    folder = countryFolders[country]
    countryName = folder.split('/')[-1]

    modelsResponse = requests.get('http://data.ipypm.ca/list_models/{}'.format(folder))

    modelFilenames = modelsResponse.json()
    modelList = list(modelFilenames.keys())

    for modelName in modelList:

        modelFn = modelFilenames[modelName]
        filename = modelFn.split('/')[-1]

        completeDescrip = regionInfo(country, filename)

        modelRegion = completeDescrip['name']
        modelCode = completeDescrip['code']
        modelAgeRange = ageRange(filename)
        modelVersionNum = modelVersion(filename)

        if modelAgeRange != '':
            continue

        print(modelName)

        modelURL = 'http://data.ipypm.ca/get_pypm/{}'.format(modelFn)

        try:
            theModel = downloadModel(modelURL)
        except UnpicklingError:
            continue

        '''
            run the model for a few time steps to make sure it's good
            check the output to kmake sure that the infection is moving
            if it gives Attribute Error as is, dump it
            if the infection isn't moving, dump it
        '''
        theModel.reset()

        try:
            theModel.generate_data(300)
        except AttributeError:
            continue

        somePredictions = theModel.populations['infected'].history
        if not movementThreshold(somePredictions, 0.2):
            continue

        if countryName == 'BC':
            countryName = 'Canada'
        elif country == 'EU':
            countryName = completeDescrip['name']
        elif countryName == 'California':
            countryName = 'USA'

        fullJurisdiction = '{} - {}'.format(countryName, modelRegion)

        fullModelDisplayName = (
            '{} ({}, ver. {})'.format(fullJurisdiction, modelAgeRange, modelVersionNum)
            if modelAgeRange != ''
            else '{} (ver. {})'.format(fullJurisdiction, modelVersionNum)
        )

        modelsAvailable.append({
            'LUT' : fullModelDisplayName,
            'Code' : modelCode,
            'Country' : countryName,
            'Region' : modelRegion,
            'Version' : modelVersionNum,
            'AgeRange': modelAgeRange,
            'Date' : modelDate(filename),
            'FileName': filename,
            'URL' : modelURL,
            'Jurisdiction' : fullJurisdiction
        })

        for pop in theModel.populations.values():

            if 'frac' in pop.name.lower():
                continue

            renamingMap[renamingCounter] = {
                'Stock' : pop.name,
                'Standard' : standardPopName(pop),
                'Description' : pop.description.capitalize()
            }; renamingCounter += 1


        paramDict = dict()

        for key in PARAMETER_ATTIBUTES:
            paramDict[key] = []

        paramDict['prior_function'] = []
        paramDict['prior_mean'] = []
        paramDict['prior_second'] = []
        paramDict['status'] = []

        for param in theModel.parameters.values():

            paramDict['model'] = fullModelDisplayName
            for attrName in PARAMETER_ATTIBUTES:
                paramDict[attrName].append( getattr(param, attrName) )

            paramDict['prior_function'].append( tablePriorDist(param.prior_function) )

            if param.prior_function == None:
                paramDict['prior_mean'].append('')
                paramDict['prior_second'].append('')
            else:
                paramDict['prior_mean'].append(param.prior_parameters['mean'])
                paramDict['prior_second'].append(list(param.prior_parameters.values())[1])

            paramDict['status'].append( tableStatus(param.get_status()) )

        defaultParameters = pandas.concat([
            defaultParameters,
            pandas.DataFrame(paramDict)
        ])

modelsAvail = pandas.DataFrame(modelsAvailable).drop_duplicates()
modelsAvail = modelsAvail.loc[(modelsAvail.AgeRange=='') & (modelsAvail.Country != 'reference')]
modelsAvail['LUT'] = [
    '{} - {} ({}, ver. {})'.format(row.Country, row.Region, row.AgeRange, row.Version)
    if row.AgeRange != ''
    else '{} - {} (ver. {})'.format(row.Country, row.Region, row.Version)
    for index, row in modelsAvail.iterrows()
]

pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels")
addThese = datasheet(myScenario, "modelKarlenPypm_PypmcaModels", empty="True")
for index, row in modelsAvail.iterrows():
    if row.LUT in list(pypmcaModels.LUT):
        continue
    addThese = addThese.append(row)
addThese = addThese.sort_values('Date').drop_duplicates('LUT', keep='last')
# this keeps the model bcc*.pypm
saveDatasheet(myScenario, addThese, "modelKarlenPypm_PypmcaModels")


defaultParameters.columns = list(map(camelify, defaultParameters.columns))
saveDatasheet(myScenario, defaultParameters, "modelKarlenPypm_ParameterValues")

renamingTable = pandas.DataFrame.from_dict(renamingMap, orient='index')
renamingTable = renamingTable.drop_duplicates(subset=['Stock'], keep='first').reset_index(drop=True).sort_values('Stock')
renamingTable = renamingTable[['Stock', 'Standard', 'Description']]
addedOnes = pandas.DataFrame([
    ['daily infected', getFancyName('daily infected'), 'number of new infections per day'],
    ['daily deaths', getFancyName('daily deaths'), 'number of new deaths per day'],
    ['daily recovered', getFancyName('daily recovered'), 'number of recoveries per day'],
    ['daily symptomatic', getFancyName('daily synmtomatic'), 'number of people who have shown symptoms per day'],
    ['daily infected_v', getFancyName('daily infected_v'), 'daily number of people infected with variant'],
    ['daily reported', getFancyName('daily reported'), 'cases reported per day'],
    ['daily reported_v', getFancyName('daily reported_v'), 'variant cases reported per day'],
    ['daily removed', getFancyName('daily removed'), 'people removed from the contagious population per day'],
    ['daily removed_v', getFancyName('daily removed_v'), 'people removed from the variant contagious population per day'],
    ], columns=['Stock', 'Standard', 'Description']
)
renamingTable = pandas.concat([renamingTable, addedOnes]).dropna().drop_duplicates(subset=['Stock'], keep='first')
renamingTable = renamingTable.sort_values('Stock').reset_index(drop=True)

pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
dataFrameDifference(renamingTable, pypmcaCrosswalk, 'Stock')
saveDatasheet(
    myScenario,
    dataFrameDifference(renamingTable, pypmcaCrosswalk, 'Stock'),
    "modelKarlenPypm_PypmcaCrosswalk"
)

renamingTable['PackageName'] = 'modelKarlenPypm'
renamingTable = renamingTable[['PackageName', 'Stock', 'Standard', 'Description']]

crosswalkFilename = '{}\\StockToStandard.csv'.format(env.TransferDirectory)
renamingTable.to_csv(crosswalkFilename, index=False)

crosswalkFile = datasheet(myScenario, 'modelKarlenPypm_CrosswalkFile', empty=True)
crosswalkFile.File = [crosswalkFilename]
crosswalkFile.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
saveDatasheet(myScenario, crosswalkFile, 'modelKarlenPypm_CrosswalkFile')


allSources = datasheet(myScenario, 'modelKarlenPypm_PypmcaData', empty=True)

karlenSources = requests.get('http://data.ipypm.ca/list_data_folders/covid19').json()

for country in karlenSources.keys():

    data_folder = karlenSources[country]
    success = True

    try:
        data_url = 'http://data.ipypm.ca/get_data_desc/{}'.format(data_folder)
        data_desc_resp = requests.get(data_url)
    except requests.exceptions.RequestException as error:
        print(error)
        success = False

    if not success:
        continue

    dataDescription = data_desc_resp.json()

    theCountry = 'Canada - British Columbia' if country == 'BC' else country

    for region in dataDescription['regional_data'].keys():

        ageStructure = 'No'
        if 'age' in dataDescription['regional_data'][region]['reported']['total']['filename']:
            ageStructure = 'Yes'
        elif len( ''.join(re.findall('\d+', region)) ) >= 2:
            ageStructure = 'Yes'

        allSources = allSources.append({
                'Country' : country,
                'Region' : region,
                'AgeStructure': ageStructure,
                'URL' : data_url
            }, ignore_index=True)


pypmcaData = datasheet(myScenario, 'modelKarlenPypm_PypmcaData')
addThese = datasheet(myScenario, 'modelKarlenPypm_PypmcaData', empty=True)

for index, row in allSources.iterrows():

    theCountry = row.Country
    theRegion = row.Region

    theCountry = 'Canada - British Columbia' if theCountry == 'BC' else theCountry

    if theRegion == 'BC':
        theRegion = 'British Columbia'
    elif theRegion == 'NWT':
        theRegion = 'Northwest Territories'
    elif theRegion == 'PEI':
        theRegion = 'Prince Edward Island'

    fullName = '{} - {}'.format(theCountry, theRegion)

    if fullName not in list(pypmcaData.Name):

        addThese = addThese.append({
            'Name' : fullName,
            'Country' : row.Country,
            'Region' : row.Region,
            'URL' : row.URL
        }, ignore_index=True)

if not addThese.empty:
    saveDatasheet(myScenario, addThese, 'modelKarlenPypm_PypmcaData')
