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


# https://stackoverflow.com/questions/4983258/python-how-to-check-list-monotonicity/4983359
# Answer by user: 6502
def non_increasing(L):
    return all(x>=y for x, y in zip(L, L[1:]))
def non_decreasing(L):
    return all(x<=y for x, y in zip(L, L[1:]))
def monotonic(L):
    return non_increasing(L) or non_decreasing(L)

env = ssimEnvironment()
myScenario = scenario()

dataChoices = datasheet(myScenario, "modelKarlenPypm_DataChoices").drop(columns=['InputID'])

crossWalk = pandas.read_csv(dataChoices.FileName.dropna().iloc[0])

def standardName(varName):
    if varName in crossWalk.Stock:
        return crossWalk[crossWalk.Stock == varName].Standard.iloc[0]
    else:
        return getFancyName(varName)

dataLUT = datasheet(myScenario, "modelKarlenPypm_PypmcaData").drop(columns=['InputID'])

karlenSources = requests.get('http://data.ipypm.ca/list_data_folders/covid19').json()

totalData = pandas.DataFrame()

for jurisdiction in list(dataChoices.DataSet):

    countryChosen = dataLUT[dataLUT.Name == jurisdiction].Country.values[0]
    regionChosen = dataLUT[dataLUT.Name == jurisdiction].Region.values[0]

    dataPairs = [(countryChosen, regionChosen)]

    # some of the data sets are equivalent
    if (countryChosen == 'Canada') and (regionChosen == 'BC'):
        dataPairs += [('BC', 'All')]
    elif (countryChosen == 'BC') and (regionChosen == 'All'):
          dataPairs += [('Canada', 'BC')]

    for theTuple in dataPairs:

        # if the chosen region is Canada - British Columbia, then combine with BC - All

        countryChosen = theTuple[0]
        regionChosen = theTuple[1]
        fancyRegionChosen = jurisdiction

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

            for pop_name in regionData:

                if pop_name == 'reported' and theTuple[1] == 'BC':
                    continue

                for metric in ['total', 'daily']:

                    fancyName = '{} - {}'.format(standardName(pop_name), 'Daily' if metric == 'daily' else 'Cumulative')

                    if not totalData.empty and fancyName in list(totalData.Variable):
                        continue

                    if metric in regionData[pop_name]:

                        filename = regionData[pop_name][metric]['filename']

                        if filename not in pd_dict.keys():
                            continue

                        header = regionData[pop_name][metric]['header']

                        theData = pd_dict[filename][header].values

                        startDate = datetime.datetime(*data_description['files'][filename]['date start'])

                        allDates = [startDate + datetime.timedelta(days=x) for x in range(len(theData))]

                        # I reckon that some of the data is mislabelled (the in_icu data, for example), as to 'daily' vs 'cumulative'
                        # if it's not monotone, then it must be daily
                        dailyOrTotal = metric
                        if not monotonic(theData):
                            dailyOrTotal = 'daily'

                        totalData = pandas.concat([
                            totalData,
                            pandas.DataFrame.from_dict({
                                'Timestep' : allDates,
                                'Variable' : standardName( '{} {}'.format(dailyOrTotal, pop_name) ),
                                # '{} - {}'.format(standardName(pop_name), 'Daily' if dailyOrTotal == 'daily' else 'Cumulative'),
                                'Value' : theData,
                                # if I don't take off the " - All" from the end of the string, we get an "All" subdivision of BC - a bit unsightly, I reckon
                                'Jurisdiction' : fancyRegionChosen.replace('- All', '').strip(),
                                'TransformerID' : 'modelKarlenPypm_C_getData'
                            })
                        ], axis=0)


totalData = totalData.reset_index().drop(columns=['index']).drop_duplicates().dropna()
totalData.Value = totalData.Value.apply(int)

epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction").drop(columns=['JurisdictionID'])
tempJuris = datasheet(myScenario, "epi_Jurisdiction", empty=True).drop(columns=['JurisdictionID'])
for dataJuris in set(totalData.Jurisdiction):
    if dataJuris not in set(epiJurisdiction.Name):
        tempJuris = tempJuris.append({'Name' : dataJuris, 'Description' : ''}, ignore_index=True)

if not tempJuris.empty:
    saveDatasheet(myScenario, tempJuris, "epi_Jurisdiction")

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





# # # totalData[totalData.Variable.str.contains('BC') & totalData.Variable.str.contains('Daily')].plot(x='Timestep', y='Value', title='Canada - BC')
# # # totalData[totalData.Variable.str.contains('All') & totalData.Variable.str.contains('Daily')].plot(x='Timestep', y='Value', title='BC - All')
