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

def getModelInformation(theInfo:tuple):

    modelURL = theInfo[0]
    landName = theInfo[1]

    theModel = downloadModel(modelURL)
    filename = theModel.name + '.pypm'

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
        return None

    somePredictions = theModel.populations['infected'].history
    if not movementThreshold(somePredictions, 0.5):
        return None

    modelInfo = {
        'Code' : regionInfo(landName, filename)['code'],
        'Country' : landName,
        'Region' : regionInfo(landName, filename)['name'],
        'AgeRange': ageRange(filename),
        'Date' : modelDate(filename),
        'Name': filename,
        'URL' : modelURL
    }

    populationInfo = {}; counter = 0

    for pop in theModel.populations.values():

        if 'frac' in pop.name.lower():
            continue

        populationInfo[counter] = {
            'StockName' : pop.name,
            'StandardName' : standardPopName(pop),
            'Description' : pop.description.capitalize()
        }; counter += 1

    return (modelInfo, populationInfo)


def main():

    env = ssimEnvironment()
    myScenario = scenario()

    jurisDictionary = {}

    foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
    countryFolders = foldersResponse.json()
    countryList = list(countryFolders.keys())

    allURLs = []

    for country in countryList:

        folder = countryFolders[country]
        countryName = folder.split('/')[-1]

        modelsResponse = requests.get('http://data.ipypm.ca/list_models/{}'.format(folder))

        modelFilenames = modelsResponse.json()
        modelList = list(modelFilenames.keys())

        for modelName in modelList:

            modelFn = modelFilenames[modelName]

            allURLs.append( ('http://data.ipypm.ca/get_pypm/{}'.format(modelFn), countryName) )


    poolSize = 1

    processingInfo = datasheet(myScenario, 'core_Multiprocessing')

    if not processingInfo.empty:

        if processingInfo.EnableMultiprocessing[0] == 'Yes':

            poolSize = max(1, processingInfo.MaximumJobs[0])

            if poolSize >= os.cpu_count():

                poolSize = os.cpu_count() - 1


    modelsAvailable = []

    renamingMap = {}
    counter = 0


    with ThreadPoolExecutor(max_workers = poolSize) as executor:

        resultGenerator = {executor.submit(getModelInformation, theInfo) : theInfo for theInfo in allURLs}

        for future in as_completed(resultGenerator):

            data = future.result()

            if data == None: continue

            modelsAvailable.append(data[0])

            for (index, popData) in data[1].items():

                renamingMap[counter] = popData
                counter += 1


    renamingTable = pandas.DataFrame.from_dict(renamingMap, orient='index')
    renamingTable = renamingTable.drop_duplicates(subset=['StockName'], keep='first').reset_index(drop=True).sort_values('StockName')
    renamingTable = renamingTable[['StockName', 'StandardName', 'Description']]
    addedOnes = pandas.DataFrame([
        ['daily infected', 'Daily - Infected', 'number of new infections per day'],
        ['daily deaths', 'Daily - Deaths', 'number of new deaths per day'],
        ['daily recovered', 'Daily - Recovered', 'number of recoveries per day'],
        ['daily symptomatic', 'Daily - Symptomatic', 'number of people who have shown symptoms per day'],
        ['daily infected_v', 'Daily - Infected (Variants)', 'daily number of people infected with variant'],
        ['daily reported_v', 'Daily - Reported (Variants)', 'variant cases reported per day'],
        ['daily removed', 'Daily - Removed', 'people removed from the contagious population per day'],
        ['daily removed_v', 'Daily - Removed (Variants)', 'people removed from the variant contagious population per day'],
        ], columns=['StockName', 'StandardName', 'Description']
    )
    renamingTable = pandas.concat([renamingTable, addedOnes]).dropna().drop_duplicates(subset=['StockName'], keep='first')
    renamingTable = renamingTable.sort_values('StockName').reset_index(drop=True)

    conventionFilename = '{}\\StockToStandard.csv'.format(env.TempDirectory)
    renamingTable.to_csv(conventionFilename, index=False)

    conventionFileInfo = datasheet(myScenario, 'modelKarlenPypm_ConventionFileOut', empty=True)
    conventionFileInfo = conventionFileInfo.drop(columns=['ConventionFileOutID'])
    conventionFileInfo.File = [conventionFilename]
    conventionFileInfo.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
    saveDatasheet(myScenario, conventionFileInfo, 'modelKarlenPypm_ConventionFileOut')

    modelsAvail = pandas.DataFrame(modelsAvailable)
    modelsAvail = modelsAvail.loc[(modelsAvail.AgeRange=='') & (modelsAvail.Country != 'reference')]
    # make sure this line runs only once
    modelsAvail.Date = [x.strftime('%d/%m/%Y') if isinstance(x, datetime.date) else '' for x in modelsAvail.Date]

    saveDatasheet(myScenario, modelsAvail, "modelKarlenPypm_ModelsAvailable")

    regionsOccurringOnce = [x for (x,y) in collections.Counter(list(modelsAvail.Code)).items() if y==1]
    selectedModels = modelsAvail[modelsAvail.Code.isin(regionsOccurringOnce)]

    differentDates = modelsAvail[modelsAvail.duplicated(['Code'], keep=False)]
    selectedModels2 = modelsAvail[modelsAvail.duplicated(['Code'], keep=False)].groupby(by='Code').max('Region')
    selectedModels2.reset_index(level=0, inplace=True)

    filteredModels = pandas.concat([selectedModels, selectedModels2])

    theJurisdictions = datasheet(myScenario, 'epi_Jurisdiction')

    ourContribution = pandas.DataFrame({'Name':[], 'Description':[]})

    for reg in filteredModels.Region:
        theThing = '({}) {}'.format(list(filteredModels[filteredModels.Region==reg].Code)[0], reg)
        if theThing not in list(theJurisdictions.Name):
            ourContribution = ourContribution.append({
                'Name' : theThing,
                'Description' : list(filteredModels[filteredModels.Region==reg].URL)[0]
            }, ignore_index=True)

    ourContribution = ourContribution.drop_duplicates()

    if not ourContribution.empty:
        saveDatasheet(myScenario, ourContribution.drop_duplicates(), "epi_Jurisdiction")

if __name__ == '__main__':

    main()
