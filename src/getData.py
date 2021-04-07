for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))
    
import requests
import collections
import datetime
import matplotlib.pyplot as plt

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

from syncro import *
from headerFile import *

env = ssimEnvironment()
myScenario = scenario()

popSelection = datasheet(myScenario, "modelKarlenPypm_PopulationSelectionTable")
dataChoices = datasheet(myScenario, "modelKarlenPypm_DataChoices")
dataLUT = datasheet(myScenario, "modelKarlenPypm_PypmcaData")

karlenSources = requests.get('http://data.ipypm.ca/list_data_folders/covid19').json()

countryChosen = dataLUT[dataLUT.Name == dataChoices.DataSet.at[0]].Country.values[0]
regionChosen = dataLUT[dataLUT.Name == dataChoices.DataSet.at[0]].Region.values[0]

# legalPopulations = list(popSelection[popSelection.Show == "Yes"].Stock)

dataPairs = [(countryChosen, regionChosen)]

# some of the data sets are equivalent
if (countryChosen == 'Canada') and (regionChosen == 'BC'):
    dataPairs += [('BC', 'All')]
elif (countryChosen == 'BC') and (regionChosen == 'All'):
     dataPairs += [('Canada', 'BC')]
     
totalData = pandas.DataFrame()
    
for theTuple in dataPairs:

    # if the chosen region is Canada - British Columbia, then combine with BC  - All
    
    countryChosen = theTuple[0]
    regionChosen = theTuple[1]
    fancyRegionChosen = dataChoices.DataSet.at[0]
    
    data_folder = karlenSources[countryChosen]
            
    success = True
    
    try:
        data_desc_resp = requests.get('http://data.ipypm.ca/get_data_desc/' + data_folder)
    except requests.exceptions.RequestException as error:
        print(error)
        success = False
        
    if not success:
        continue
    
    data_description = data_desc_resp.json()
    data_description['folder'] = data_folder
    
    regionData = data_description['regional_data'][regionChosen]
        
    pd_dict = {}
    for filename in data_description['files']:
        path = data_folder + '/' + filename
        success = True
        try:
            csv_resp = requests.get('http://data.ipypm.ca/get_csv/' + path, stream=True)
        except requests.exceptions.RequestException as error:
            print(error)
            success = False
        if success:
            pd_dict[filename] = pandas.read_csv(csv_resp.raw)
            
    # for pop_name in legalPopulations:
        # if pop_name in regionData:
            
    for pop_name in regionData:
        
        if pop_name == 'reported' and theTuple[1] == 'BC':
            continue
        
        print(pop_name)
        for metric in ['total', 'daily']:
            
            fancyName = '{} - {}'.format(getFancyName(pop_name), 'Daily' if metric == 'daily' else 'Cumulative')
            
            
            if not totalData.empty and fancyName in list(totalData.Variable):
                continue
            
            if metric in regionData[pop_name]:
                filename = regionData[pop_name][metric]['filename']
                header = regionData[pop_name][metric]['header']
                theData = pd_dict[filename][header].values
                
                startDate = datetime.datetime(*data_description['files'][filename]['date start'])
                
                allDates = [startDate + datetime.timedelta(days=x) for x in range(len(theData))]
                
                totalData = pandas.concat([
                    totalData,
                    pandas.DataFrame.from_dict({
                        'Timestep' : allDates,
                        'Variable' : '{} - {}'.format(getFancyName(pop_name), 'Daily' if metric == 'daily' else 'Cumulative'),
                        'Value' : theData,
                        'Jurisdiction' : fancyRegionChosen,
                        'TransformerID' : 'modelKarlenPypm_C_getData'
                    })
                ], axis=0)


totalData = totalData.reset_index().drop(columns=['index']).drop_duplicates().dropna()

epiVariable = datasheet(myScenario, "epi_Variable").drop(columns=['VariableID'])
weNeedToAdd = {}; counter = 0
for name in set(totalData.Variable.values):
    if name not in list(epiVariable.Name):
        weNeedToAdd[counter] = {'Name' : name, 'Description' : ''}
        counter += 1
addThisDict = pandas.DataFrame.from_dict(weNeedToAdd, orient='index')

if not addThisDict.empty:
    saveDatasheet(myScenario, addThisDict.drop_duplicates(), "epi_Variable")

saveDatasheet(myScenario, totalData, "epi_DataSummary")





# totalData[totalData.Variable.str.contains('BC') & totalData.Variable.str.contains('Daily')].plot(x='Timestep', y='Value', title='Canada - BC')
# totalData[totalData.Variable.str.contains('All') & totalData.Variable.str.contains('Daily')].plot(x='Timestep', y='Value', title='BC - All')