#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import sys
import requests
import collections
import datetime
import numpy
import pycountry

from syncro import *
import headerFile

env = ssimEnvironment()
myScenario = scenario()

'''
    this transformer fetches the data set requested in the input datasheet by looking up the country and region in the PypmcaData lut.

    Tables:

    1) data_choices - user choices of the Jurisdiction and stratification desired
    2) PypmcaData - matches user input with Karlen's country and region names for the data sets

'''

# user jurisdiction choice
data_choices = datasheet(myScenario, "modelKarlenPypm_DataChoices").drop(columns=['InputID']).iloc[0]

# if a crosswalk file is supplied, use that. else, use the project-level sheet
if not data_choices.isnull().CrosswalkFile:
    crossWalk = pandas.read_csv(data_choices.CrosswalkFile)
else:
    crossWalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")

# function to look up the Ssim standard names for Karlen's population names
def standardName(var_name):
    if var_name in crossWalk.Stock:
        return crossWalk[crossWalk.Stock == var_name].Standard.iloc[0]
    else:
        return headerFile.getFancyName(var_name)

# gives the country and region names used *by Karlen* to store and organise the data
dataLUT = datasheet(myScenario, "modelKarlenPypm_PypmcaData")
dataLUT = dataLUT[dataLUT.LUT == data_choices.DataSet].set_index('PypmcaDataID')

# get the object
karlen_sources = requests.get('http://data.ipypm.ca/list_data_folders/covid19').json()

# holds all the data
total_data = pandas.DataFrame()
# stores a list of data sets (for the programmer) that may be duplicate
duplicates = pandas.DataFrame()

'''
    since the getRepos transformer combined stratified data sets into one single description, a user choice will potentially map to
    many different data sets ("<10", "10-20", etc), we iterate over all the data sets described by the lookup
'''
for index, row in dataLUT.iterrows():

    # Karlen's country and region names
    country_chosen = row.Country.split(' ')[0]
    if row.Region.split(' ')[0] in ['Germany', 'All', 'Unknown']:
        region_chosen = row.Region.split(' ')[0]
    else:
        region_chosen = row.Region

    # data folder
    data_folder = karlen_sources[country_chosen]

    success = True

    # the data description gives information on the jurisdiction, data file names and headers for the data
    try:
        data_desc_resp = requests.get('http://data.ipypm.ca/get_data_desc/' + data_folder)
    except requests.exceptions.RequestException as error:
        print(error)
        success = False

    if not success:
        continue

    data_description = data_desc_resp.json()
    data_description['folder'] = data_folder

    # a structured dictionary of the variables, file names necessary
    regional_data = data_description['regional_data'][region_chosen]

    pd_dict = {}

    # the data is split across different files
    for filename in data_description['files']:

        path = data_folder + '/' + filename
        success = True

        # pd_dict stores the time series for all data sets
        try:
            csv_response = requests.get('http://data.ipypm.ca/get_csv/' + path, stream=True)
        except requests.exceptions.RequestException as error:
            print(error)
            success = False
        if success:
            pd_dict[filename] = pandas.read_csv(csv_response.raw)

        # for every population (infected, removed, deaths, etc)
        for population_name in regional_data:

            # data is either daily or cumulative
            for metric in ['total', 'daily']:

                # the data set may contain only one of 'daily' or 'total', not both
                if metric not in regional_data[population_name]:
                    continue

                # progress
                print('file: {}\npopulation: {}, metric: {}'.format(filename, population_name, metric))

                # name of the file the data is in (a key in the dictionary pd_dict)
                filename = regional_data[population_name][metric]['filename']

                # sometimes a given filename isn't actually provided
                if filename not in pd_dict.keys():
                    print('\t*** FILENAME NOT FOUND ***\n')
                    continue

                # gives the column header of the time series. usually coded, such as "BC-xt"
                header = regional_data[population_name][metric]['header']

                # possible that the header's not there
                if header not in pd_dict[filename]:
                    print('\t*** REQUESTED HEADER NOT IN DATA TABLE ***\n')
                    continue

                # get the age range of the data. this is usually contained in the region name or the header
                age_dict = headerFile.ageRangeString(region_chosen)
                print(age_dict)

                # fetch the time series
                the_data = pd_dict[filename][header].values

                # sometimes the time series is all NaN values
                if all(numpy.isnan(the_data)):
                    print('\t*** ALL NA DATA ***\n')
                    continue

                # the description also gives the start date of the time series
                start_date = datetime.datetime(*data_description['files'][filename]['date start'])
                # using the starting date and the length of the time series, generate a list of dates
                # (assuming that dates haven't been skipped in the data
                all_dates = [start_date + datetime.timedelta(days=x) for x in range(len(the_data))]

                 # I reckon that some of the data is mislabelled (the in_icu data, for example), as to 'daily' vs 'total'
                # if it's not monotone, then it must be daily
                daily_or_total = metric
                if not headerFile.monotonic(the_data):
                    daily_or_total = 'daily'

                fancy_name = standardName( '{} {}'.format(daily_or_total, population_name) )

                # or we can trust Karlen to get the daily and total labels right
                # fancy_name = '{} - {}'.format(standardName(population_name), 'Daily' if metric == 'daily' else 'Cumulative')

                print('\t{}'.format(fancy_name))

                # store the data temporarily
                data_dict = {
                    'Timestep' : all_dates,
                    'Variable' : fancy_name,
                    'Value' : the_data,
                    'Jurisdiction' : row.LUT,
                    'TransformerID' : 'modelKarlenPypm_D_getData'
                }

                # print progress
                print('\tADDED')

                # fill the age information of the data set
                if age_dict != {}:

                    if age_dict['lower'] not in [0, None]:
                        data_dict['AgeMin'] = age_dict['lower']
                        print('\tlower: {}'.format(data_dict['AgeMin']))
                    if age_dict['upper'] != None:
                        data_dict['AgeMax'] = age_dict['upper']
                        print('\tupper: {}'.format(data_dict['AgeMax']))

                # filling the sex columns of the datasheet
                if row.Region.lower() == 'male':
                    data_dict['Sex'] = 0
                    print('\tSex: Male')
                elif row.Region.lower() == 'female':
                    data_dict['Sex'] = 1
                    print('\tSex: Female')

                # pull together the data from this source
                data_here = pandas.DataFrame.from_dict(data_dict)

                '''
                    since we're pulling together multiple data sets, it's possible for some data sets to be duplicated. for example, BC CDC data may
                    appear multiple times, or be combined with UofT API data. this chunk recognises when duplicate data is about to be added and
                    skips the writing step.

                    we create a signature row (a one line table with all the constant values - age, sex, jurisdiction, etc) and check to see whether
                    there is some such row already in total_data by merging the two and seeing if the row is common to both

                    dropping duplicates gets rid of the same data set added multiple time, whereas this chunk prevents including conflicting data sets,
                    preference given to the first one in
                '''
                # only make a comparison of the data set isn't empty
                if not total_data.empty:
                    # a short signature of the data set can be created by having only the static columns (so we take out the dynamic ones)
                    temp_data_descrip = data_here.drop(columns=['Value', 'Timestep']).drop_duplicates()
                    # print the signature
                    print(temp_data_descrip)
                    print()

                    # a list of the columns
                    cols = list(temp_data_descrip.columns)

                    # if the data from this loop has columns that total_data doesn't have as yet (age, gender, etc) then there's no need to check
                    if set(cols).issubset(total_data.columns):
                        # merge the signature of the current data with all the signatures in total_data, with an indicator
                        merged = pandas.merge(total_data[cols].drop_duplicates(), temp_data_descrip, on=cols, how='outer', indicator=True)
                        # if it's unique,then _merge should only say "left_join". else, the signature is not unique
                        if not merged[merged._merge=="both"].empty:
                            print('\t*** DATA SET DUPLICATED ***\n')

                            # collect a list of duplicated data sets for review
                            temp_data_descrip['country'] = row.Country
                            temp_data_descrip['region'] = row.Region
                            duplicates = pandas.concat([duplicates, temp_data_descrip])
                            continue

                # incorporate the data
                total_data = pandas.concat([ total_data, data_here ])

                print('\n\n')

# the "Value"  column of epi_DataSummary can't have NaNs
total_data = total_data[total_data.Value.notnull()] # .drop_duplicates()

# if there's age information, AgeMax and AgeMin need to be integer values
if ('AgeMin' in total_data.columns) or ('AgeMax' in total_data.columns):

    # convert to integers
    total_data.AgeMin = total_data.AgeMin.astype('Int32')
    total_data.AgeMax = total_data.AgeMax.astype('Int32')

# it there's sex information, Sex needs to be integer values
if 'Sex' in total_data.columns:

    # convert to integers
    total_data.Sex = total_data.Sex.astype('Int32')

# write only new jurisdictions to epi_Jurisdiction
epiJurisdiction = datasheet(myScenario, "epi_Jurisdiction")
tempJuris = datasheet(myScenario, "epi_Jurisdiction", empty=True).drop(columns='JurisdictionID')
for dataJuris in set(total_data.Jurisdiction):
    if dataJuris not in set(epiJurisdiction.Name):
        tempJuris = tempJuris.append({'Name' : dataJuris, 'Description' : ''}, ignore_index=True)

if not tempJuris.empty:
    saveDatasheet(myScenario, tempJuris, "epi_Jurisdiction")

# write only new variable names to epi_Variable
epiVariable = datasheet(myScenario, "epi_Variable").drop(columns=['VariableID'])
weNeedToAdd = {}; counter = 0
for name in set(total_data.Variable.values):
    if name not in list(epiVariable.Name):
        weNeedToAdd[counter] = {'Name' : name, 'Description' : ''}
        counter += 1
addThisDict = pandas.DataFrame.from_dict(weNeedToAdd, orient='index')

if not addThisDict.empty:
    saveDatasheet(myScenario, addThisDict.drop_duplicates(), "epi_Variable")

if data_choices.DisaggregateSex == 'No':
    total_data = total_data[total_data.Sex.isna()]

saveDatasheet(myScenario, total_data, "epi_DataSummary")
