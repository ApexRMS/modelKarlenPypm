import requests
import os
import sys
import pickle
import pypmca

import subprocess
import pandas
from syncro import *

########################### FOR THE R RETICULATE WRAPPER ###########################

def openModel(my_pickle):
    model = pickle.loads(my_pickle)
    time_step = model.get_time_step()
    if time_step > 1.001 or time_step < 0.999:
        print('Filename: ' + filename)
        print('*** Model NOT loaded ***')
        print('Currently, ipypm only supports models with time_step = 1 day.')
    return model

# def saveModel(theURL:str, fileName):
#     pypmResponse = requests.get(theURL, stream=True)
#     myPickle = pypmResponse.content
#     model = openModel(myPickle)
#     model.save_file(fileName)

# def getModelNameDescription(fileName:str):
#     model = pypmca.Model.open_file(fileName)
#     return {'name':model.name, 'description':model.description}

####################################################################################

env = ssimEnvironment()
myScenario = scenario()

jurisDictionary = {}

foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
regionModelFolders = foldersResponse.json()
regionList = list(regionModelFolders.keys())

modelsAvailable = []

for region in regionList:

    folder = regionModelFolders[region]
    regionPrintName = folder.split('/')[-1]
    modelsResponse = requests.get('http://data.ipypm.ca/list_models/' + folder)

    modelFilenames = modelsResponse.json()
    modelList = list(modelFilenames.keys())

    for model in modelList:

        modelFn = modelFilenames[model]
        filename = modelFn.split('/')[-1]

        modelPrintName = modelFn.split('/')[-1].replace('.pypm', '')
        fullModelName = '{}: {}'.format(regionPrintName, modelPrintName)

        pypmResponse = requests.get('http://data.ipypm.ca/get_pypm/' + modelFn, stream=True)

        myPickle = pypmResponse.content
        model = openModel(myPickle)

        model.save_file('{}.temp\\{}'.format(env.LibraryFilePath, filename))
        modelDescrip = model.description.replace('\"', '').replace('\'', '')

        jurisDictionary[fullModelName] = modelDescrip

        modelsAvailable.append({
            'Region':regionPrintName,
            'Name':filename,
            'Description':modelDescrip
        })

    break

theJurisdictions = datasheet(myScenario, 'epi_Jurisdiction', empty=True)
theJurisdictions = theJurisdictions.drop(columns=['JurisdictionID'])

theJurisdictions.Name = pandas.Series(jurisDictionary.keys())
theJurisdictions.Description = pandas.Series(jurisDictionary.values())

datasheet(myScenario, 'epi_Jurisdiction', empty=True)

# theModels = datasheet(myScenario, "modelKarlenPypm_ModelsAvailable", empty=True)
# theModels = theModels.drop(columns=['ModelsAvailableID'])

modelAvailDT = pandas.DataFrame(modelsAvailable)

saveDatasheet(myScenario, modelAvailDT, "modelKarlenPypm_ModelsAvailable")



# exportFilename = "C:\\Users\\User\\Documents\\haha7.csv"

# theJurisdictions.to_csv(exportFilename, index=False)
# cmdLine = '"{}" --lib={} --sid={} --pid={} --sheet={} --file={} --import'.format(theConsole, libraryPath, myScenario, hereProj, "epi_Jurisdiction", exportFilename)
# print(cmdLine)
# subprocess.call(cmdLine)

# theModels = ss.getDatasheet(myScenario, "modelKarlenPypm_ModelsAvailable", empty=True)
# theModels = theModels.drop(columns=['ModelsAvailableID'])

# exportFilename = "C:\\Users\\User\\Documents\\haha8.csv"

# pandas.DataFrame(modelsAvailable).to_csv(exportFilename, index=False)
# cmdLine = '"{}" --lib={} --sid={} --pid={} --sheet={} --file={} --import'.format(theConsole, libraryPath, myScenario, hereProj, "modelKarlenPypm_ModelsAvailable", exportFilename)
# print(cmdLine)
# subprocess.call(cmdLine)
