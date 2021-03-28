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

jurisDictionary = {}

foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
countryFolders = foldersResponse.json()
countryList = list(countryFolders.keys())

modelsAvailable = []

renamingMap = {}; counter = 0

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
            'AgeRange': ageRange(filename),
            'Date' : modelDate(filename),
            'Name': filename,
            'URL' : modelURL
        })

        for pop in theModel.populations.values():

            if 'frac' in pop.name.lower():
                continue

            renamingMap[counter] = {
                'StockName' : pop.name,
                'StandardName' : standardPopName(pop),
                'Description' : pop.description.capitalize()
            }; counter += 1

        # end loop

    # end loop

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


# '''
#     appending to the variable name table
#     Names must be unique, with no NAs
#     so get what's in there first, and then concatenate, drop NAs and duplicates
#     delete the populations with empty descriptions
# '''
# beforeVars = datasheet(myScenario, "epi_Variable").drop(columns=['VariableID'])
# currentVars = pandas.DataFrame({'Name':theVariables.keys(), 'Description':theVariables.values()})
# currentVars = currentVars[currentVars.Description != '']
# addedOnes = pandas.DataFrame([
#     ['DailyInfected', 'number of new infections per day'],
#     ['DailyDeaths', 'number of new deaths per day'],
#     ['DailyRecovered', 'number of recoveries per day'],
#     ['DailySymptomatic', 'number of people who have shown symptoms per day'],
#     ['DailyInfectedV', 'daily number of people infected with variant'],
#     ['DailyReportedV', 'variant cases reported per day'],
#     ['DailyRemoved', 'people removed from the contagious population per day'],
#     ['DailyRemovedV', 'people removed from the variant contagious population per day'],
#     ], columns=['Name', 'Description']
# )
# newVars = pandas.concat([beforeVars, currentVars, addedOnes]).dropna().drop_duplicates()

# for var in list(newVars.Name):
#     if var not in beforeVars.Name:
#         beforeVars = beforeVars.append({
#             'Name' : list(renamingMap[renamingMap.StockName == var].StandardName)[0],
#             'Description' : list(newVars[newVars.Name==var].Description)[0]
#         }, ignore_index=True)

# saveDatasheet(myScenario, newVars, "epi_Variable")

# renamingMap = pandas.DataFrame()
# renamingMap['StockName'] = newVars.Name
# renamingMap['StandardName'] = ['Cumulative - {}'.format( list(newVars[newVars.Name==x].Name)[0] ) for x in renamingMap.StockName]
# renamingMap['Variable Description'] = [list(newVars[newVars.Name == x].Description)[0] for x in renamingMap.StockName]
# renamingMap.to_csv('C:\\Users\\User\\Documents\\Github\\modelKarlenPypm\\StockToStandard.csv', index=False)

# renamingMap = pandas.read_csv('C:\\Users\\User\\Documents\\Github\\modelKarlenPypm\\StockToStandard_orig.csv')
# theVariables = {}
# theVariables = {**theVariables, **populationDescrips}
