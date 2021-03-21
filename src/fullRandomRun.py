# #!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import pandas
import requests
import random
import collections

from syncro import *
from headerFile import *

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

##################################################################################################

theJurisdictions = datasheet(myScenario, 'epi_Jurisdiction')

emptyCols = []

simLength = 450

numIterations = 50

for iteration in range(numIterations):
    
    modelsToTrial = random.sample(range(theJurisdictions.shape[0]), 94)

    for modelNumber in modelsToTrial:
    
        randNumber = random.sample(range(theJurisdictions.shape[0]), 1)[0]
        modelURL = theJurisdictions.Description[randNumber]
        
        theModel = downloadModel(modelURL)

        theModel.reset()
        theModel.evolve_expectations(simLength)
        
        for population in theModel.populations.values():
            
            theVector = population.history
            if len(set(theVector)) < simLength/10:
                emptyCols.append(population.name)
    
repetitions = collections.Counter(emptyCols)
repetitions = {x:y/numIterations/len(modelsToTrial) for (x,y) in repetitions.items()}
commentThese = {x:round(y,2) for (x,y) in dict(repetitions).items() if y>0.7}

















