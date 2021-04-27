#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import requests
import collections
import datetime
import pycountry

from syncro import *
import headerFile

env = ssimEnvironment()
myScenario = scenario()

# '''
#     This file
#         1) gets a list of all the models that Karlen has made available for different regions and countries
#         2) gets a list of all the data sources available

#     These are exactly the data made available through his online ipypmm interface
# '''

# foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
# countryFolders = foldersResponse.json()
# countryList = list(countryFolders.keys())

# '''
#     This loop gathers a list of all the models available.

#     1) a .pypm model object is downloaded for some region and country. since some of the models (previously, not sure if currently) didn't move, we reset each model and run for a number of time steps. If unique values make up more than some percentage of the time series of the infected population, then the model is accepted, else the loop is continued. The .pypm object is then discarded in this loop, not stored. Some of its information is stored for the PypmcaModels project-level datasheet (lut).

#     2) a crosswalk file is generated. the variable names used by Karlen (infected_v, daily deaths, etc) aren't the standard names used by Syncrosim, so the crosswalk file acts as a lut for standardised names (Reported (Variants), Deaths, etc). this is done through string parsing in the function headerFile.standardPopName, with ambiguities hard-coded. for instance, Karlen's 'reported' population is Syncrosim's 'Cases - Daily' data. this generated list is saved to the project-level PypmcaCrosswalk datasheet (lut).

#     3) each .pypm model object is stripped and 'default' parameter values taken (each model comes prefit, but in line with the online interface, the user will be offered the chance to change the parameters and refit the model to data before getting expectations and running simulations). these values (from all models) will be stored in a scenario-level ParameterValues datasheet, as a (necessary) dependency for the getExpectations transformer .

#     even though variable names and jurisdictions are gathered, nothing is added to those datasheets at this stage, to avoid crowding. jurisdiction will be added on the fly as specific models are chosen by the user, and variables will be added when selected in running the getExepctations transformer
# '''

# modelsAvailable = []

# renamingMap = {}; renamingCounter = 0

# # list of some of the parameter values to be stripped from each model
# PARAMETER_ATTRIBUTES = ['name', 'description', 'initial_value', 'parameter_min', 'parameter_max']
# defaultParameters = pandas.DataFrame()


# for country in countryList:

#     # we're not interested in offering any of the reference models to the user
#     if 'ref' in country.lower():
#         continue

#     # get the name of the country for the datasheet
#     folder = countryFolders[country]
#     countryName = folder.split('/')[-1]

#     modelsResponse = requests.get('http://data.ipypm.ca/list_models/{}'.format(folder))

#     # list of available regional models for the country
#     modelFilenames = modelsResponse.json()
#     modelList = list(modelFilenames.keys())

#     print('\n{}'.format(countryName))

#     for modelName in modelList:

#         # get the filename - it gives such information as the region, model version and date published
#         modelFn = modelFilenames[modelName]
#         filename = modelFn.split('/')[-1]

#         # returns the standard name and ISO-3166 code of the region
#         completeDescrip = headerFile.regionInfo(country, filename)

#         # model stats: the ISO name for the region, ISO-3166 code, which age group the model was fit to and the version number
#         # this step previously got the publishing date of the model, but that was deemed redundant when paired with the version number
#         modelRegion = completeDescrip['name']
#         modelCode = completeDescrip['code']
#         modelAgeRange = headerFile.ageRangeModel(filename)
#         modelVersionNum = headerFile.modelVersion(filename)

#         # # age-specific models were not being included in the demonstration
#         # if modelAgeRange != '':
#         #     continue

#         # (try to) download the model object
#         modelURL = 'http://data.ipypm.ca/get_pypm/{}'.format(modelFn)
#         try:
#             theModel = headerFile.downloadModel(modelURL)
#         except:
#             continue

#         # reset the populations to zero before testing the model
#         theModel.reset()

#         # (try to) generate data for the first 300 time steps
#         try:
#             theModel.generate_data(300)
#         except AttributeError:
#             continue

#         # time series of the numbers of daily infections.
#         somePredictions = theModel.populations['infected'].history
#         # if unique values make up less than 20% of the length of the time series, the model is dropped
#         if not headerFile.movementThreshold(somePredictions, 0.2):
#             continue

#         '''
#             the country names Karlen uses aren't always countries, they're levels. for example, if the model is for BC, then the country is 'Canada' and the region is 'BC'. however, if the model is of a health authority in BC, then the country will be 'BC' and the region will be 'Fraser', say. this chuck of code corrects this so we can get correct jurisdiction names for a tree view in the charting window, for example.
#         '''
#         if countryName == 'BC':
#             countryName = 'Canada'
#         elif country == 'EU':
#             countryName = completeDescrip['name']
#         elif countryName == 'California':
#             countryName = 'USA'

#         # proper name - for example, 'Canada - British Columbia - Vancouver Coastal', to be written to epi-Jurisdiction later, should this model be chosen
#         fullJurisdiction = '{} - {}'.format(countryName, modelRegion)

#         # name displayed to the user in the drop-down menu in the later transformers
#         fullModelDisplayName = (
#             '{} ({}, ver. {})'.format(fullJurisdiction, modelAgeRange, modelVersionNum)
#             if modelAgeRange != ''
#             else '{} (ver. {})'.format(fullJurisdiction, modelVersionNum)
#         )

#         '''
#             all the model information needed to be written to the PypmcaModels datasheet
#             the column 'LUT' is what the user sees (and chooses) in future transformer inputs. when a choice is made, the corresponding row in this table will given all the information necessary fill the model region entry in epi_Jurisdiction and model download information
#         '''
#         modelsAvailable.append({
#             'LUT' : fullModelDisplayName,
#             'Code' : modelCode,
#             'Country' : countryName,
#             'Region' : modelRegion,
#             'Version' : modelVersionNum,
#             'AgeRange': modelAgeRange,
#             'Date' : headerFile.modelDate(filename),
#             'FileName': filename,
#             'URL' : modelURL,
#             'Jurisdiction' : fullJurisdiction
#         })

#         print('\t{}'.format(fullModelDisplayName))

#         # get all the population names (infected, removed, in_icu, etc) in the model, so to make a crosswalk lut
#         for pop in theModel.populations.values():

#             if 'frac' in pop.name.lower():
#                 continue
#             '''
#                 (unique) Stock - Karlen's name, for example: infected_v
#                 (unique) Standard: SSim name, for example, Infected (Variants)
#                 Description: description of the requisite population (wither hard-coded here or provided by Karlen)
#             '''
#             renamingMap[renamingCounter] = {
#                 'Stock' : pop.name,
#                 'Standard' : headerFile.standardPopName(pop),
#                 'Description' : pop.description.capitalize()
#             }; renamingCounter += 1

#         # dictionary to store default parameter names and values
#         paramDict = dict()

#         for key in PARAMETER_ATTRIBUTES:
#             paramDict[key] = []

#         paramDict['prior_function'] = []
#         paramDict['prior_mean'] = []
#         paramDict['prior_second'] = []
#         paramDict['status'] = []

#         for param in theModel.parameters.values():

#             # model name, as we formatted it above
#             paramDict['model'] = fullModelDisplayName

#             # parameter name, description, initial value, min and max parameter values
#             for attrName in PARAMETER_ATTRIBUTES:
#                 paramDict[attrName].append( getattr(param, attrName) )

#             # prior functions for the parameters to be fit to data
#             paramDict['prior_function'].append( headerFile.tablePriorDist(param.prior_function) )

#             # some variables are fixed (and so have no supplied priors). others are variable, with either normal or uniform priors
#             if param.prior_function == None:
#                 paramDict['prior_mean'].append('')
#                 paramDict['prior_second'].append('')
#             else:
#                 paramDict['prior_mean'].append(param.prior_parameters['mean'])
#                 paramDict['prior_second'].append(list(param.prior_parameters.values())[1])

#             # each parameter has either 'fixed' or 'variable' status, determines if the parameter is one fit to data, or not
#             paramDict['status'].append( headerFile.tableStatus(param.get_status()) )

#         defaultParameters = pandas.concat([
#             defaultParameters,
#             pandas.DataFrame(paramDict)
#         ])

# modelsAvail = pandas.DataFrame(modelsAvailable).drop_duplicates()

# # get the project-level datasheet for the models available and add only the ones that weren't there before
# pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels").drop(columns="PypmcaModelsID")
# addThese = modelsAvail[-modelsAvail.LUT.isin(pypmcaModels.LUT)]
# addThese = addThese.sort_values('Date').drop_duplicates('LUT', keep='last')
# saveDatasheet(myScenario, addThese, "modelKarlenPypm_PypmcaModels")

# # save the default parameters for each model
# defaultParameters.columns = list(map(headerFile.camelify, defaultParameters.columns))
# saveDatasheet(myScenario, defaultParameters, "modelKarlenPypm_ParameterValues")

# '''
#     here we create the crosswalk file and datasheet. the parsed variable names gathered before are combined with new hard-coded names
# '''
# renamingTable = pandas.DataFrame.from_dict(renamingMap, orient='index')

# # we've added each variable to the dictionary for all models, so there is massive duplication in the table
# renamingTable = renamingTable.drop_duplicates(subset=['Stock'], keep='first').reset_index(drop=True).sort_values('Stock')

# '''
#     Karlen's models make many populations available, but not all of the populations have both daily and cumulative corresponding series. so, through a diff function - 'delta' here, we can create daily time series for some of the cumulative series given
# '''
# addedOnes = pandas.DataFrame([
#     ['daily infected', headerFile.getFancyName('daily infected'), 'number of new infections per day'],
#     ['daily deaths',  headerFile.getFancyName('daily deaths'), 'number of new deaths per day'],
#     ['daily recovered',  headerFile.getFancyName('daily recovered'), 'number of recoveries per day'],
#     ['daily symptomatic',  headerFile.getFancyName('daily symptomatic'), 'number of people who have shown symptoms per day'],
#     ['daily infected_v',  headerFile.getFancyName('daily infected_v'), 'daily number of people infected with variant'],
#     ['daily reported',  headerFile.getFancyName('daily reported'), 'cases reported per day'],
#     ['daily reported_v',  headerFile.getFancyName('daily reported_v'), 'variant cases reported per day'],
#     ['daily removed',  headerFile.getFancyName('daily removed'), 'people removed from the contagious population per day'],
#     ['daily removed_v',  headerFile.getFancyName('daily removed_v'), 'people removed from the variant contagious population per day'],
#     ], columns=['Stock', 'Standard', 'Description']
# )
# renamingTable = pandas.concat([renamingTable, addedOnes]).dropna().drop_duplicates(subset=['Stock'], keep='first')
# renamingTable = renamingTable.sort_values('Stock').reset_index(drop=True)

# # save the crosswalk datasheet
# pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
# addThese = renamingTable[-renamingTable.Stock.isin(pypmcaCrosswalk.Stock)]
# saveDatasheet(myScenario, addThese, "modelKarlenPypm_PypmcaCrosswalk")

# # agreement that every crosswalk file will given the name of the package as well (future-proofing)
# renamingTable['PackageName'] = 'modelKarlenPypm'

# crosswalkFilename = '{}\\StockToStandard.csv'.format(env.TransferDirectory)
# renamingTable.to_csv(crosswalkFilename, index=False)

# '''
#     crosswalk file also saved to CSV. if there are any errors, the programmer can change the entries and upload the file to any future
#     transformers. it'll be given preference over the PypmcaCrosswalk datasheet
# '''
# crosswalkFile = datasheet(myScenario, 'modelKarlenPypm_CrosswalkFile', empty=True)
# crosswalkFile.File = [crosswalkFilename]
# crosswalkFile.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
# saveDatasheet(myScenario, crosswalkFile, 'modelKarlenPypm_CrosswalkFile')


'''
    making a list of the data sets available from Karlen's repositories. some of the data sets are country-level data, while some sources
    are province/state- and region-level, with some age and gender stratification. generally, they're sorted by country and region,, but
    where city/age/gender level data is given, then that description becomes the 'region' and the 'country' is either the country or the
    broader state/province.

    For example, Schleswig-Holstein (Germany) would be described as: country - Germany, region - Schleswig-Holstein
    However, if this data was age stratified, then it may be described as: country - Germany, region - sh_a0

    Sources stratified by age/sex are grouped together into one option, with the getData transformer filling the AgeMin/AgeMax and Sex
    fields of epi_DataSummary with the requisite information. Data stratified by health region is given as a set of options, since Karlen
    also provides aggregate data for entire cities/countries where appropriate.
'''

print('\n\n')

allSources = pandas.DataFrame()

# the repository that all data descriptions and files are stored in
karlenSources = requests.get('http://data.ipypm.ca/list_data_folders/covid19').json()

# reminder that 'karlenCountry' may be a province or state if it's data is stratified
for karlenCountry in karlenSources.keys():

    # folder giving information for that city
    data_folder = karlenSources[karlenCountry]
    success = True

    '''
        the data description gives the names of the variables for which data is available, column headers (since they're in short form in the CSV)
        and data file names
    '''
    try:

        data_url = 'http://data.ipypm.ca/get_data_desc/{}'.format(data_folder)
        data_desc_resp = requests.get(data_url)
    except requests.exceptions.RequestException as error:
        print(error)
        success = False

    if not success:
        continue

    # the description object
    dataDescription = data_desc_resp.json()

    '''
        fancy* denotes the version of a Karlen variable that will be used for printing to the datasheet, rather than the raw names supplied (since
        they're not always intuitive, as stated above). 'fancyCountry' is the fancy name for the karlenCountry. for example, if the karlenCountry
        is given as "california", the fancy name is: fancyCountry = "USA: California"

        <fancyCountry> - <fancyRegion> is what appears in the drop-down menu for the getExpectations transformer. this is done through a combination of
        pycountry lookups and hard-coding. all this is done to make sure that the data source names match the .pypm model names (as the user sees them)
    '''
    fancyCountry = karlenCountry

    # hard-coded for simplicity, in line with KISS. more can be added later, in the case that he changes the names
    if fancyCountry == 'Germany_age':
        fancyCountry = 'Germany'
    elif fancyCountry == 'California':
        fancyCountry = 'USA - California'
    elif fancyCountry == 'BC':
        fancyCountry = 'Canada - British Columbia'

    # progress message
    print('\n{}'.format(fancyCountry))

    # for each region
    for karlenRegion in dataDescription['regional_data'].keys():

        # reminder: fancyRegion is the corrected version of karlenRegion that will be shown in the drop-down menu for the getExpectations transformer
        fancyRegion = karlenRegion

        # retrieves any age information in the karlenRegion name (ex. "<10", "30-39", "under 40", etc)
        ageDict = headerFile.ageRangeString(karlenRegion)

        '''
            for the data set "Germany_age", the regions are stratified by age, and so the names of the regions take the form '[a-zA-Z]{2}_a[0-5]*',
            where the first two letters before the underscore give the ISO 3166-2 codes for the state, the "a" after the underscore represents "age",
            with the number following "a" giving the Robert-Koch Institut (RKI) age class (described in headerFile.ageRangeString).

            for instance, "bw-a2" denotes the data for RKI age class 2 (15-34) for the German state Baden-Wu:rttemburg. if the ISO 3-66 code is 'de',
            then that's just Germany total, so fancyRegion is set to None.
        '''
        if karlenCountry == 'Germany_age':

            # for this data set, get the coded karlenRegion name and age class
            code = fancyRegion.split('_')[0]
            # 'de' is the ISO 3166 code for Germany, so this is country-level data rather that regional
            if code == 'de':
                fancyRegion = None
            else:
                # if valid ISO 3166-2 code, do pycountry lookup to find the region information
                pyDivision = pycountry.subdivisions.get(code='DE-{}'.format(code.upper()))
                # get the fancy name of the region (includes diacritics)
                fancyRegion = pyDivision.name

        '''
            if fancyRegion is set to None, this means that the karlenRegion name contained only age/sex information and will not be used, since
            the subregion name must be given in the karlenCountry variable in that case. for example, the descriptions

                "karlenCountry - BC, karlenRegion - Male"
                "karlenCountry - BC, karlenRegion - Unknown"
                "karlenCountry - BC, karlenRegion - 20-50"

            will all get the fancyRegion None, so that the fancy name of the regions would be multiple copies of "Canada - British Columbia" (the karlenCountry variable
            gave us the name of the state/province, and it's easy to find the country)
        '''

        # if the region variable gives gender information, set the fancyRegion to None
        if fancyRegion in ['All', 'Male', 'Female']:
            fancyRegion = None
        # sometimes country-level data will be denoted "Israel - Israel", for example
        if fancyRegion == fancyCountry:
            fancyRegion = None
        # EU is not a country, so set the fancyCountry as the region name and mark the fancyRegion as being None
        elif karlenCountry == 'EU':
            fancyCountry = fancyRegion
            fancyRegion = None
        # hard-coded Canadian provinces
        elif fancyRegion == 'BC':
            fancyRegion = 'British Columbia'
        elif fancyRegion == 'NWT':
            fancyRegion = 'Northwest Territories'
        elif fancyRegion == 'PEI':
            fancyRegion = 'Prince Edward Island'
        # Karlen has preceded the Brazilian states by their ISO 3166-2 code, so "TO: Tocantins" becomes "Tocantins"
        elif (fancyRegion != None) and (':' in fancyRegion):
            fancyRegion = fancyRegion.split(':')[-1].strip()

        # if the karlenRegion is a description of the age range of the data, set fancyRegion to None to avoid pasting it in the fancy jurisdiction name
        else:
            # if there's age information in karlenRegion, then set the fancyRegion
            if len(ageDict) and fancyRegion!= None:
                fancyRegion = None

        # if there is a fancy region name, print it to demonstrate progress
        if fancyRegion != None:
            print('\t{}'.format(fancyRegion))

        # fullName is the name the user will see in drop-downs. for example, "Canada - British Columbia", "Germany"
        if fancyRegion == None:
            fullName = fancyCountry
          # if there is a fancy region name, paste it. for example, "Canada - British Columbia - Fraser", "Germany - Nordrhein-Westfalen"
        else:
            fullName = '{} - {}'.format(fancyCountry, fancyRegion.replace('-', '_'))

        '''
            these regions may be repeated. since the Region column is supposed to have unique entries (project-level datasheets can't have duplicate
            value members), just tack on the country name and remove it in the getData transformer
        '''
        if karlenRegion in ['Germany', 'All', 'Unknown']:
            karlenRegion = '{} {}'.format(karlenRegion, karlenCountry)

        # finally, write to the table
        allSources = allSources.append({
            'LUT' : fullName,
            'Country' :karlenCountry,
            'Region' : karlenRegion,
            'FancyCountry' : fancyCountry,
            'FancyRegion' : fancyRegion
        }, ignore_index=True)

# add the complete list of models (duplicates included) to a visible datasheet
pypmcaData = datasheet(myScenario, "modelKarlenPypm_PypmcaData").drop(columns=['PypmcaDataID'])
allSources = allSources[-allSources.Region.isin(pypmcaData.Region)]
if not allSources.empty:
    saveDatasheet(myScenario, allSources, 'modelKarlenPypm_PypmcaData')

# to create a drop-down for the getData transformer, we take all the fancy jurisdictions and remove the duplicates
dataAvail = allSources[['LUT']].drop_duplicates().rename(columns={'LUT': 'Name'})

# write to a table that will create the drop-down option menu
dropdown = datasheet(myScenario, "modelKarlenPypm_DataDropdown").drop(columns=['DataDropdownID'])
dataAvail = dataAvail[-dataAvail.Name.isin(dropdown.Name)]
if not dataAvail.empty:
    saveDatasheet(myScenario, dataAvail, "modelKarlenPypm_DataDropdown")
