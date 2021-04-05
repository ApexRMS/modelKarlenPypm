#!/usr/bin/python

# def main():
    
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
        'Country' : 'Canada' if landName == 'BC' else landName,  
        'Region' : regionInfo(landName, filename)['name'],
        'AgeRange': ageRange(filename),
        'Date' : modelDate(filename),
        'Name': filename,
        'URL' : modelURL
    }
    
    # print(modelInfo)

    populationInfo = {}; counter = 0

    for pop in theModel.populations.values():

        if 'frac' in pop.name.lower():
            continue

        populationInfo[counter] = {
            'Stock' : pop.name,
            'Standard' : standardPopName(pop),
            'Description' : pop.description.capitalize()
        }; counter += 1

    return (modelInfo, populationInfo)

    
env = ssimEnvironment()
myScenario = scenario()

jurisDictionary = {}

standard = ('http://data.ipypm.ca/get_pypm/models/covid19/Canada/bcc_2_6_1224.pypm','Canada')

result = getModelInformation(standard)

first = result[0]
second = result[1]

foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
countryFolders = foldersResponse.json()
# countryList = list(countryFolders.keys())
countryList = ['Canada', 'BC']

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

conventionFilename = '{}\\StockToStandard.csv'.format(env.TempDirectory)
renamingTable.to_csv(conventionFilename, index=False)

conventionFileInfo = datasheet(myScenario, 'modelKarlenPypm_ConventionFileOut', empty=True)
conventionFileInfo = conventionFileInfo.drop(columns=['ConventionFileOutID'])
conventionFileInfo.File = [conventionFilename]
conventionFileInfo.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
saveDatasheet(myScenario, conventionFileInfo, 'modelKarlenPypm_ConventionFileOut')


modelsAvail = pandas.DataFrame(modelsAvailable)
modelsAvail = modelsAvail.loc[(modelsAvail.AgeRange=='') & (modelsAvail.Country != 'reference')]
modelsAvail = modelsAvail.drop(modelsAvail[modelsAvail.Name.str.contains('bcc')].index)
modelsAvail = modelsAvail.sort_values('Date').drop_duplicates('Region', keep='last')
modelsAvail.Date = [x.strftime('%d/%m/%Y') if isinstance(x, datetime.date) else '' for x in modelsAvail.Date]
modelsAvail['LUT'] = modelsAvail[['Country', 'Region']].agg(' - '.join, axis=1)
saveDatasheet(myScenario, modelsAvail, "modelKarlenPypm_ModelsAvailable")

juris = datasheet(myScenario, "modelKarlenPypm_PypmcaJuris").drop(columns=['PypmcaJurisID'])
temp = datasheet(myScenario, "modelKarlenPypm_PypmcaJuris", empty=True).drop(columns=['PypmcaJurisID'])
for name in modelsAvail.LUT:
    if name not in list(juris.Name):
        temp = temp.append({
            'Name' : name,
            'URL' : list(modelsAvail[modelsAvail.LUT == name].URL)[0]
        }, ignore_index=True)
temp = temp.dropna(subset=['Name'])
if not temp.empty:
    saveDatasheet(myScenario, temp.dropna(subset=['Name']), "modelKarlenPypm_PypmcaJuris")


# if __name__ == '__main__':

#     main()
