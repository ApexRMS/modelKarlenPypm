#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import sys
import requests
import collections
import datetime
import numpy

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

from syncro import *
import headerFile

env = ssimEnvironment()
myScenario = scenario()

'''
    this transformer fetches the data set requested in the input datasheet by looking up the country and region in the PypmcaData lut.

    Tables:

    1) DataChoices - user choices of the Jurisdiction and stratification desired
    2) PypmcaData - matches user input with Karlen's country and region names for the data sets

'''

# user jurisdiction choice
dataChoices = datasheet(myScenario, "modelKarlenPypm_DataChoices").drop(columns=['InputID']).iloc[0]

# if a crosswalk file is supplied, use that. else, use the project-level sheet
if not dataChoices.isnull().CrosswalkFile:
    crossWalk = pandas.read_csv(dataChoices.CrosswalkFile)
else:
    crossWalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")

# function to look up the Ssim standard names for Karlen's population names
def standardName(varName):
    if varName in crossWalk.Stock:
        return crossWalk[crossWalk.Stock == varName].Standard.iloc[0]
    else:
        return headerFile.getFancyName(varName)

# gives the country and region names used *by Karlen* to store and organise the data
dataLUT = datasheet(myScenario, "modelKarlenPypm_PypmcaData")
dataLUT = dataLUT[dataLUT.LUT == dataChoices.DataSet].set_index('PypmcaDataID')

# get the object
karlenSources = requests.get('http://data.ipypm.ca/list_data_folders/covid19').json()

# holds all the data
totalData = pandas.DataFrame()
# stores a list of data sets (for the programmer) that may be duplicate
duplicates = pandas.DataFrame()

'''
    since the getRepos transformer combined stratified data sets into one single description, a user choice will potentially map to
    many different data sets ("<10", "10-20", etc), we iterate over all the data sets described by the lookup
'''
for index, row in dataLUT.iterrows():

    # Karlen's country and region names
    countryChosen = row.Country.split(' ')[0]
    regionChosen = row.Region.split(' ')[0]

    # data folder
    dataFolder = karlenSources[countryChosen]

    success = True

    # the data description gives information on the jurisdiction, data file names and headers for the data
    try:
        data_desc_resp = requests.get('http://data.ipypm.ca/get_data_desc/' + dataFolder)
    except requests.exceptions.RequestException as error:
        print(error)
        success = False

    if not success:
        continue

    data_description = data_desc_resp.json()
    data_description['folder'] = dataFolder

    # a structured dictionary of the variables, file names necessary
    regionData = data_description['regional_data'][regionChosen]

    pd_dict = {}

    # the data is split across different files
    for filename in data_description['files']:

        path = dataFolder + '/' + filename
        success = True

        # pd_dict stores the time series for all data sets
        try:
            csv_resp = requests.get('http://data.ipypm.ca/get_csv/' + path, stream=True)
        except requests.exceptions.RequestException as error:
            print(error)
            success = False
        if success:
            pd_dict[filename] = pandas.read_csv(csv_resp.raw)

        # for every population (infected, removed, deaths, etc)
        for pop_name in regionData:

            # data is either daily or cumulative
            for metric in ['total', 'daily']:

                # the data set may contain only one of 'daily' or 'total', not both
                if metric not in regionData[pop_name]:
                    continue

                # progress
                print('pop_name: {}, metric: {}'.format(pop_name, metric))

                # name of the file the data is in (a key in the dictionary pd_dict)
                filename = regionData[pop_name][metric]['filename']

                # sometimes a given filename isn't actually provided
                if filename not in pd_dict.keys():
                    print('\t*** Filename not found ***\n')
                    continue

                # gives the column header of the time series. usually coded, such as "BC-xt"
                header = regionData[pop_name][metric]['header']

                # possible that the header's not there
                if header not in pd_dict[filename]:
                    print('\t*** requested header not in data table ***\n')
                    continue

                # get the age range of the data. this is usually contained in the region name or the header
                ageDict = headerFile.ageRangeString(regionChosen)
                print(ageDict)

                # fetch the time series
                theData = pd_dict[filename][header].values

                # sometimes the time series is all NaN values
                if all(numpy.isnan(theData)):
                    print('\t*** all NA data ***\n')
                    continue

                # the description also gives the start date of the time series
                startDate = datetime.datetime(*data_description['files'][filename]['date start'])
                # using the starting date and the length of the time series, generate a list of dates
                # (assuming that dates haven't been skipped in the data
                allDates = [startDate + datetime.timedelta(days=x) for x in range(len(theData))]

                 # I reckon that some of the data is mislabelled (the in_icu data, for example), as to 'daily' vs 'total'
                # if it's not monotone, then it must be daily
                dailyOrTotal = metric
                if not headerFile.monotonic(theData):
                    dailyOrTotal = 'daily'

                fancyName = standardName( '{} {}'.format(dailyOrTotal, pop_name) )

                # or we can trust Karlen to get the daily and total labels right
                # fancyName = '{} - {}'.format(standardName(pop_name), 'Daily' if metric == 'daily' else 'Cumulative')

                print('\t{}'.format(fancyName))

                # store the data temporarily
                dataDict = {
                    'Timestep' : allDates,
                    'Variable' : fancyName,
                    'Value' : theData,
                    'Jurisdiction' : row.LUT,
                    'TransformerID' : 'modelKarlenPypm_D_getData'
                }

                # print progress
                print('\tADDED')

                # fill the age information of the data set
                if ageDict != {}:

                    if ageDict['lower'] not in [0, None]:
                        dataDict['AgeMin'] = ageDict['lower']
                        print('\tlower: {}'.format(dataDict['AgeMin']))
                    if ageDict['upper'] != None:
                        dataDict['AgeMax'] = ageDict['upper']
                        print('\tupper: {}'.format(dataDict['AgeMax']))

                # filling the sex columns of the datasheet
                if row.Region.lower() == 'male':
                    dataDict['Sex'] = 0
                    print('\tSex: Male')
                elif row.Region.lower() == 'female':
                    dataDict['Sex'] = 1
                    print('\tSex: Female')

                # pull together the data from this source
                dataHere = pandas.DataFrame.from_dict(dataDict)

                '''
                    since we're pulling together multiple data sets, it's possible for some data sets to be duplicated. for example, BC CDC data may
                    appear multiple times, or be combined with UofT API data. this chunk recognises when duplicate data is about to be added and
                    skips the writing step.

                    we create a signature row (a one line table with all the constant values - age, sex, jurisdiction, etc) and check to see whether
                    there is some such row already in totalData by merging the two and seeing if the row is common to both

                    dropping duplicates gets rid of the same data set added multiple time, whereas this chunk prevents including conflicting data sets,
                    preference given to the first one in
                '''
                # only make a comparison of the data set isn't empty
                if not totalData.empty:
                    # a short signature of the data set can be created by having only the static columns (so we take out the dynamic ones)
                    tempDataDescrip = dataHere.drop(columns=['Value', 'Timestep']).drop_duplicates()
                    # print the signature
                    print(tempDataDescrip)

                    # a list of the columns
                    cols = list(tempDataDescrip.columns)

                    # if the data from this loop has columns that totalData doesn't have as yet (age, gender, etc) then there's no need to check
                    if set(cols).issubset(totalData.columns):
                        # merge the signature of the current data with all the signatures in totalData, with an indicator
                        merged = pandas.merge(totalData[cols].drop_duplicates(), tempDataDescrip, on=cols, how='outer', indicator=True)
                        # if it's unique,then _merge should only say "left_join". else, the signature is not unique
                        if not merged[merged._merge=="both"].empty:
                            print('\t*** data set duplicated ***\n')

                            # collect a list of duplicated data sets for review
                            tempDataDescrip['country'] = row.Country
                            tempDataDescrip['region'] = row.Region
                            duplicates = pandas.concat([duplicates, tempDataDescrip])
                            continue

                # incorporate the data
                totalData = pandas.concat([ totalData, dataHere ])

                print()

# the "Value"  column of epi_DataSummary can't have NaNs
totalData = totalData[totalData.Value.notnull()] # .drop_duplicates()

# if there's age information, AgeMax and AgeMin need to be integer values
if ('AgeMin' in totalData.columns) or ('AgeMax' in totalData.columns):

    # convert to integers
    totalData.AgeMin = totalData.AgeMin.astype('Int32')
    totalData.AgeMax = totalData.AgeMax.astype('Int32')

    # should the user choose not to have age stratified data, we exclude those rows
    if (not dataChoices.isnull().Age) and (dataChoices.Age == 'No'):
        totalData = totalData[numpy.isnan(totalData.AgeMax) & numpy.isnan(totalData.AgeMin)].drop(columns=['AgeMin', 'AgeMax'])

# it there's sex information, Sex needs to be integer values
if 'Sex' in totalData.columns:

    # convert to integers
    totalData.Sex = totalData.Sex.astype('Int32')

    # should the user choose not to have sex stratified data, we exclude those rows
    if (not dataChoices.isnull().Sex) and (dataChoices.Sex != 'Yes'):
        totalData = totalData[numpy.isnan(totalData.Sex)].drop(columns=['Sex'])

# write only new jurisdictions to epi_Jurisdiction
epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction")
tempJuris = datasheet(myScenario, "epi_Jurisdiction", empty=True).drop(columns='JurisdictionID')
for dataJuris in set(totalData.Jurisdiction):
    if dataJuris not in set(epiJurisdiction.Name):
        tempJuris = tempJuris.append({'Name' : dataJuris, 'Description' : ''}, ignore_index=True)

if not tempJuris.empty:
    saveDatasheet(myScenario, tempJuris, "epi_Jurisdiction")

# write only new variable names to epi_Variable
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
