#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))
        
import requests

from syncro import *
from headerFile import *

env = ssimEnvironment()
myScenario = scenario()

jurisDictionary = {}

foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
countryFolders = foldersResponse.json()
countryList = list(countryFolders.keys())

modelsAvailable = []
theVariables = {}

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

        theModel = downloadModel(modelURL)

        '''
            run the model for a few time steps to make sure it's good
            check the output to kmake sure that the infection is moving
            if it gives Attribute Error as is, dump it
            if the infection isn't moving, dump it
        '''
        theModel.reset()

        try:
            theModel.generate_data(10)
        except AttributeError:
            continue

        somePredictions = theModel.populations['infected'].history
        if len(somePredictions) != len(set(somePredictions)):
            continue

        populationDescrips = {camelify(x.name) : x.description for x in theModel.populations.values()}
        theVariables = {**theVariables, **populationDescrips}

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
    modelsAvail.iloc[index]['Region'] = regionName + newDate

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

'''
    appending to the variable name table
    Names must be unique, with no NAs
    so get what's in there first, and then concatenate, drop NAs and duplicates
    delete the populations with empty descriptions
'''
beforeVars = datasheet(myScenario, "epi_Variable").drop(columns=['VariableID'])
currentVars = pandas.DataFrame({'Name':theVariables.keys(), 'Description':theVariables.values()})
currentVars = currentVars[currentVars.Description != '']
currentVars = currentVars.append({'Name':'DailyInfected', 'Description':'number of new infections per day'}, ignore_index=True)
newVars = pandas.concat([beforeVars, currentVars]).dropna().drop_duplicates()
saveDatasheet(myScenario, newVars, "epi_Variable")
