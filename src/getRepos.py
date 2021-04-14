#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import requests
import collections
import datetime

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

from syncro import *
from headerFile import *

env = ssimEnvironment()
myScenario = scenario()

jurisDictionary = {}

foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
countryFolders = foldersResponse.json()
countryList = list(countryFolders.keys())

modelsAvailable = []

renamingMap = {}; counter = 0

for country in  countryList:

    folder = countryFolders[country]
    countryName = folder.split('/')[-1]

    modelsResponse = requests.get('http://data.ipypm.ca/list_models/{}'.format(folder))

    modelFilenames = modelsResponse.json()
    modelList = list(modelFilenames.keys())

    for modelName in modelList:

        modelFn = modelFilenames[modelName]
        filename = modelFn.split('/')[-1]

        modelURL = 'http://data.ipypm.ca/get_pypm/{}'.format(modelFn)

        theModel = downloadModel(modelURL)

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
        if not movementThreshold(somePredictions, 0.5):
            continue

        modelsAvailable.append({
            'Code' : regionInfo(countryName, filename)['code'],
            'Country' : countryName,
            'Region' : regionInfo(countryName, filename)['name'],
            'Version' : modelVersion(filename),
            'AgeRange': ageRange(filename),
            'Date' : modelDate(filename),
            'Name': filename,
            'URL' : modelURL
        })

        for pop in theModel.populations.values():

            if 'frac' in pop.name.lower():
                continue

            renamingMap[counter] = {
                'Stock' : pop.name,
                'Standard' : standardPopName(pop),
                'Description' : pop.description.capitalize()
            }; counter += 1


renamingTable = pandas.DataFrame.from_dict(renamingMap, orient='index')
renamingTable = renamingTable.drop_duplicates(subset=['Stock'], keep='first').reset_index(drop=True).sort_values('Stock')
renamingTable = renamingTable[['Stock', 'Standard', 'Description']]
addedOnes = pandas.DataFrame([
    ['daily infected', 'Cases - Daily', 'number of new infections per day'],
    ['daily deaths', 'Mortality - Daily', 'number of new deaths per day'],
    ['daily recovered', 'Recovered - Daily', 'number of recoveries per day'],
    ['daily symptomatic', 'Symptomatic - Daily', 'number of people who have shown symptoms per day'],
    ['daily infected_v', 'Cases (Variants) - Daily', 'daily number of people infected with variant'],
    ['daily reported_v', 'Reported (Variants) - Daily', 'variant cases reported per day'],
    ['daily removed', 'Removed - Daily', 'people removed from the contagious population per day'],
    ['daily removed_v', 'Removed (Variants) - Daily', 'people removed from the variant contagious population per day'],
    ], columns=['Stock', 'Standard', 'Description']
)
renamingTable = pandas.concat([renamingTable, addedOnes]).dropna().drop_duplicates(subset=['Stock'], keep='first')
renamingTable = renamingTable.sort_values('Stock').reset_index(drop=True)

crosswalkFilename = '{}\\StockToStandard.csv'.format(env.TempDirectory)
renamingTable.to_csv(crosswalkFilename, index=False)

crosswalkFile = datasheet(myScenario, 'modelKarlenPypm_CrosswalkFile', empty=True)
crosswalkFile = crosswalkFile.drop(columns=['InputID'])
crosswalkFile.File = [crosswalkFilename]
crosswalkFile.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
saveDatasheet(myScenario, crosswalkFile, 'modelKarlenPypm_CrosswalkFile')

modelsAvail = pandas.DataFrame(modelsAvailable)
modelsAvail = modelsAvail.sort_values('Date').drop_duplicates('Region', keep='last')
modelsAvail.Date = [x.strftime('%d/%m/%Y') if isinstance(x, datetime.date) else '' for x in modelsAvail.Date]
modelsAvail['LUT'] = modelsAvail[['Country', 'Region']].agg(' - '.join, axis=1)
saveDatasheet(myScenario, modelsAvail, "modelKarlenPypm_ModelsAvailable")

# filtering all the models
modelsAvail = modelsAvail.loc[(modelsAvail.AgeRange=='') & (modelsAvail.Country != 'reference')]

juris = datasheet(myScenario, "modelKarlenPypm_PypmcaJuris").drop(columns=['InputID'])
temp = datasheet(myScenario, "modelKarlenPypm_PypmcaJuris", empty=True).drop(columns=['InputID'])
for name in modelsAvail.LUT:

    # only looking at Canada for now, but we can have all the regions later
    if 'Canada' not in name:
        continue

    if name not in list(juris.Name):
        temp = temp.append({
            'Name' : name,
            'URL' : list(modelsAvail[modelsAvail.LUT == name].URL)[0]
        }, ignore_index=True)
temp = temp.dropna(subset=['Name'])
if not temp.empty:
    saveDatasheet(myScenario, temp.dropna(subset=['Name']), "modelKarlenPypm_PypmcaJuris")

allSources = datasheet(myScenario, "modelKarlenPypm_DataAvailable", empty=True).drop(columns=['InputID'])

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

allSources = allSources.dropna()
saveDatasheet(myScenario, allSources, "modelKarlenPypm_DataAvailable")

pypmcaData = datasheet(myScenario, "modelKarlenPypm_PypmcaData").drop(columns=['InputID'])
addThese = datasheet(myScenario, "modelKarlenPypm_PypmcaData", empty=True).drop(columns=['InputID'])

for index, row in allSources.iterrows():

    theCountry = row.Country
    theRegion = row.Region

    if theCountry not in ["BC", "Canada"]:
        continue

    theCountry = 'Canada - British Columbia' if theCountry == 'BC' else theCountry

    if theRegion == 'BC':
        theRegion = 'British Columbia'
    elif theRegion == "NWT":
        theRegion = "Northwest Territories"
    elif theRegion == "PEI":
        theRegion = "Prince Edward Island"

    fullName = '{} - {}'.format(theCountry, theRegion)

    if fullName not in list(pypmcaData.Name):

        addThese = addThese.append({
            'Name' : fullName,
            'Country' : row.Country, # theCountry,
            'Region' : row.Region,
            'URL' : row.URL
        }, ignore_index=True)

if not addThese.empty:
    saveDatasheet(myScenario, addThese, "modelKarlenPypm_PypmcaData")
