#!/usr/bin/python

for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import requests
#import collections
import datetime
import pycountry
import pandas
import translate

#import sys

''' uncomment and insert these two lines into the code to halt execution at a certain point without exiting the interpreter '''
# sys.tracebacklimit = 1
# raise ValueError()

from syncro import *
import headerFile

env = ssimEnvironment()
myScenario = scenario()

'''
    This file
        1) gets a list of all the models that Karlen has made available for different regions and countries
        2) gets a list of all the data sources available

    These are exactly the data made available through his online ipypmm interface

 	Tables:

 	1) Pypmca* (the visible project-level datasheets/lookup tables):

		a) PypmcaModels - holds the list of all models available in the repository. this is also used as a look-up table
 			(lut) in future transformers, since it gives details other than the fancy Jurisdiction name to help us find
 			and name the model .pypm object

		b) PypmcaCrosswalk - in order to compare models, we have a list of standard variable/population names to be used
 			across models ('Cases - Daily', 'Deaths - Cumulative', etc). this is a lut mapping Karlen's model names (for ex.
 			'infected_v') to Ssim standard variable names ('Infected (Variants) - Daily') and vice versa.

		c) PypmcaData - a lut/complete list of all data sources available (stratified by age, sex, region), which may include
 			overlapping data sets (such as 'Canada - BC' and 'BC - All'). sometimes these overlapping sets come from different
 			sources (for ex., the UofT API and the BC CDC respectively, for the previous example). the names also will overlap,
 			but the combination of country+region will be unique. age- and sex-stratified data for the same region will be combined
 			into the same DataSummary for a given region, so fancy Jurisdiction names will not be unique.

 			for example, 'BC <10', 'BC 20-59' and 'BC Female' will all be combined into the same DataSummary, so they will all have
 			the same jurisdiction name 'Canada - British Columbia', say. in the getData transformer, when we choose to get data
 			for the 'Canada - British Columbia' region, this lut table will give all the possible data sets tied to this region
 			(Male, Female, <10, 89+, etc...).

 	2) ParameterValues - stores all the default (prior) parameter values stripped from all the models we come across, stratified
		by region. when the getExpectations transformer is run, the user will be able to choose the parameter value set for the
		desired jurisdiction and change individual parameter values before getting the expected values

 	3) CrosswalkFile - the crosswalk lut mentioned in 1b) will also be written as a CSV file that can be amended by the user, should
		there be mistakes. currently (as of 27 April 2020) the crosswalk file is auto-generated through string parsing of the Karlen
		population names, but if there are mistakes, they can be corrected, and that file can then be referenced in every future
		transformer (since the project-level datasheets can't be erased from, only appended to).

 	4) DataDropdown - 1c) mentions that, to capture the multiple data sets pertinent to a single jurisdiction), sources uniquely
		identified by their country+region pair will be given the same names. this table just takes the fancy names, removes the
		duplicate fancy jurisdiction names and saves to a project-level datasheet to create a drop-down menu with no duplicates
		can be chosen from in the getData transformer.
'''

folders_response = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
country_folders = folders_response.json()
country_list = list(country_folders.keys())

'''
    This loop gathers a list of all the models available.

    1) a .pypm model object is downloaded for some region and country. since some of the models (previously, not sure if currently) didn't move,
        we reset each model and run for a number of time steps. If unique values make up more than some percentage of the time series of the
        infected population, then the model is accepted, else the loop is continued. The .pypm object is then discarded in this loop, not stored.
        Some of its information is stored for the PypmcaModels project-level datasheet (lut).

    2) a crosswalk file is generated. the variable names used by Karlen (infected_v, daily deaths, etc) aren't the standard names used by Syncrosim,
        so the crosswalk file acts as a lut for standardised names (Reported (Variants), Deaths, etc). this is done through string parsing in the
        function headerFile.standardPopName, with ambiguities hard-coded. for instance, Karlen's 'reported' population is Syncrosim's 'Cases - Daily'
        data. this generated list is saved to the project-level PypmcaCrosswalk datasheet (lut).

    3) each .pypm model object is stripped and 'default' parameter values taken (each model comes pre-fit, but in line with the online interface, the
        user will be offered the chance to change the parameters and refit the model to data before getting expectations and running simulations).
        these values (from all models) will be stored in a scenario-level ParameterValues datasheet, as a (necessary) dependency for the getExpectations
        transformer .

    even though variable names and jurisdictions are gathered, nothing is added to those datasheets at this stage, to avoid crowding. jurisdiction will
    be added on the fly as specific models are chosen by the user, and variables will be added when selected in running the getExpectations transformer
'''

models_available = []

renaming_map = {}; renamingCounter = 0

# list of some of the parameter values to be stripped from each model
PARAMETER_ATTRIBUTES = ['name', 'description', 'initial_value', 'parameter_min', 'parameter_max']
default_parameters = pandas.DataFrame()


for country in country_list:

    # we're not interested in offering any of the reference models to the user
    if 'ref' in country.lower():
        continue

    # get the name of the country for the datasheet
    folder = country_folders[country]
    country_name = folder.split('/')[-1]

    models_response = requests.get('http://data.ipypm.ca/list_models/{}'.format(folder))

    # list of available regional models for the country
    model_filenames = models_response.json()
    model_list = list(model_filenames.keys())

    print('\n{}'.format(country_name))

    for model_name in model_list:

        # get the filename - it gives such information as the region, model version and date published
        model_fn = model_filenames[model_name]
        filename = model_fn.split('/')[-1]

        # returns the standard name and ISO-3166 code of the region
        complete_descrip = headerFile.regionInfo(country, filename)

        # model stats: the ISO name for the region, ISO-3166 code, which age group the model was fit to and the version number
        # this step previously got the publishing date of the model, but that was deemed redundant when paired with the version number
        model_region = complete_descrip['name']
        model_ISO_code = complete_descrip['code']
        model_age_range = headerFile.ageRangeModel(filename)

        model_version_number = headerFile.modelVersion(filename)

        try:
            # (try to) download the model object
            model_URL = 'http://data.ipypm.ca/get_pypm/{}'.format(model_fn)
            the_model = headerFile.downloadModel(model_URL)
        except:
            continue

        # reset the populations to zero before testing the model
        the_model.reset()

        # (try to) generate data for the first 300 time steps
        try:
            the_model.generate_data(300)
        except AttributeError:
            continue

        # time series of the numbers of daily infections.
        evolutions_for_testing = the_model.populations['infected'].history
        # if unique values make up less than 20% of the length of the time series, the model is dropped
        if not headerFile.movementThreshold(evolutions_for_testing, 0.2):
            continue

        '''
            the country names Karlen uses aren't always countries, they're levels. for example, if the model is for BC, then the country is 'Canada'
            and the region is 'BC'. however, if the model is of a health authority in BC, then the country will be 'BC' and the region will be 'Fraser',
            say. this chuck of code corrects this so we can get correct jurisdiction names for a tree view in the charting window, for example.
        '''
        if country_name == 'BC':
            country_name = 'Canada'
        elif country == 'EU':
            country_name = complete_descrip['name']
        elif country_name == 'California':
            country_name = 'USA'

        # proper name - for example, 'Canada - British Columbia - Vancouver Coastal', to be written to epi-Jurisdiction later, should this model be chosen
        fancy_jurisdiction = '{} - {}'.format(country_name, model_region)

        # name displayed to the user in the drop-down menu in the later transformers
        fancy_model_display_name = (
            '{} ({}, ver. {})'.format(fancy_jurisdiction, model_age_range, model_version_number)
            if model_age_range != ''
            else '{} (ver. {})'.format(fancy_jurisdiction, model_version_number)
        )

        '''
            all the model information needed to be written to the PypmcaModels datasheet
            the column 'LUT' is what the user sees (and chooses) in future transformer inputs. when a choice is made, the corresponding row in this table
            will given all the information necessary fill the model region entry in epi_Jurisdiction and model download information
        '''
        models_available.append({
            'LUT' : fancy_model_display_name,
            'Code' : model_ISO_code,
            'Country' : country_name,
            'Region' : model_region.replace('-', '_'),
            'Version' : model_version_number,
            'AgeRange': model_age_range,
            'Date' : headerFile.modelDate(filename),
            'FileName': filename,
            'URL' : model_URL,
            'Jurisdiction' : fancy_jurisdiction
        })

        print('\t{}'.format(fancy_model_display_name))

        # get all the population names (infected, removed, in_icu, etc) in the model, so to make a crosswalk lut
        for population in the_model.populations.values():

            if 'frac' in population.name.lower():
                continue
            '''
                (unique) Stock - Karlen's name, for example: infected_v
                (unique) Standard: Ssim name, for example, Infected (Variants)
                Description: description of the requisite population (wither hard-coded here or provided by Karlen)
            '''
            renaming_map[renamingCounter] = {
                'Stock' : population.name,
                'Standard' : headerFile.standardPopName(population),
                'Description' : population.description.capitalize()
            }
            renamingCounter += 1


        '''
 			in line with the ipypm online interface, the user will be allowed (in the getExpectations and getIterations transformers) to alter
 			the parameter values of the model before fitting and running. here, we decompose and strip each model to create a set of 'default'
 			parameter values for the user to see and adjust before the fitting step.

 			this allows the user to choose which variables to adjust during the fitting step, and which ones to hold constant during the process
		'''

        # dictionary to store default parameter names and values
        parameter_dictionary = dict()

        for key in PARAMETER_ATTRIBUTES:
            parameter_dictionary[key] = []

        parameter_dictionary['prior_function'] = []
        parameter_dictionary['prior_mean'] = []
        parameter_dictionary['prior_second'] = []
        parameter_dictionary['status'] = []

        for param in the_model.parameters.values():

            # model name, as we formatted it above
            parameter_dictionary['model'] = fancy_model_display_name

            # parameter name, description, initial value, min and max parameter values
            for attribute_name in PARAMETER_ATTRIBUTES:
                parameter_dictionary[attribute_name].append( getattr(param, attribute_name) )

            # prior functions for the parameters to be fit to data
            parameter_dictionary['prior_function'].append( headerFile.tablePriorDist(param.prior_function) )

            # some variables are fixed (and so have no supplied priors). others are variable, with either normal or uniform priors
            if param.prior_function == None:
                parameter_dictionary['prior_mean'].append('')
                parameter_dictionary['prior_second'].append('')
            else:
                parameter_dictionary['prior_mean'].append(param.prior_parameters['mean'])
                parameter_dictionary['prior_second'].append(list(param.prior_parameters.values())[1])

            # each parameter has either 'fixed' or 'variable' status, determines if the parameter is one fit to data, or not
            parameter_dictionary['status'].append( headerFile.tableStatus(param.get_status()) )

        default_parameters = pandas.concat([
            default_parameters,
            pandas.DataFrame(parameter_dictionary)
        ])

table_models_available = pandas.DataFrame(models_available).drop_duplicates()

# get the project-level datasheet for the models available and add only the ones that weren't there before
pypmcaModels = datasheet(myScenario, "modelKarlenPypm_PypmcaModels").drop(columns="PypmcaModelsID")
addThese = table_models_available[-table_models_available.LUT.isin(pypmcaModels.LUT)]
addThese = addThese.sort_values('Date').drop_duplicates('LUT', keep='last')
saveDatasheet(myScenario, addThese, "modelKarlenPypm_PypmcaModels")

# save the default parameters for each model
default_parameters.columns = list(map(headerFile.camelify, default_parameters.columns))
saveDatasheet(myScenario, default_parameters, "modelKarlenPypm_ParameterValues")

'''
    here we create the crosswalk file and datasheet. the parsed variable names gathered before are combined with new hard-coded names
'''
renaming_table = pandas.DataFrame.from_dict(renaming_map, orient='index')

# we've added each variable to the dictionary for all models, so there is massive duplication in the table
renaming_table = renaming_table.drop_duplicates(subset=['Stock'], keep='first').reset_index(drop=True).sort_values('Stock')

'''
    Karlen's models make many populations available, but not all of the populations have both daily and cumulative corresponding series.
    so, through a diff function - 'delta' here, we can create daily time series for some of the cumulative series given
'''
manually_added_populations = pandas.DataFrame([
    ['daily infected', headerFile.getFancyName('daily infected'), 'number of new infections per day'],
    ['daily deaths',  headerFile.getFancyName('daily deaths'), 'number of new deaths per day'],
    ['daily recovered',  headerFile.getFancyName('daily recovered'), 'number of recoveries per day'],
    ['daily symptomatic',  headerFile.getFancyName('daily symptomatic'), 'number of people who have shown symptoms per day'],
    ['daily infected_v',  headerFile.getFancyName('daily infected_v'), 'daily number of people infected with variant'],
    ['daily reported',  headerFile.getFancyName('daily reported'), 'cases reported per day'],
    ['daily reported_v',  headerFile.getFancyName('daily reported_v'), 'variant cases reported per day'],
    ['daily removed',  headerFile.getFancyName('daily removed'), 'people removed from the contagious population per day'],
    ['daily removed_v',  headerFile.getFancyName('daily removed_v'), 'people removed from the variant contagious population per day'],
    ], columns=['Stock', 'Standard', 'Description']
)
renaming_table = pandas.concat([renaming_table, manually_added_populations]).dropna().drop_duplicates(subset=['Stock'], keep='first')
renaming_table = renaming_table.sort_values('Stock').reset_index(drop=True)

# save the crosswalk datasheet
pypmcaCrosswalk = datasheet(myScenario, "modelKarlenPypm_PypmcaCrosswalk")
addThese = renaming_table[-renaming_table.Stock.isin(pypmcaCrosswalk.Stock)]
saveDatasheet(myScenario, addThese, "modelKarlenPypm_PypmcaCrosswalk")

# agreement that every crosswalk file will given the name of the package as well (future-proofing)
renaming_table['PackageName'] = 'modelKarlenPypm'

crosswalkFilename = '{}\\StockToStandard.csv'.format(env.TransferDirectory)
renaming_table.to_csv(crosswalkFilename, index=False)

'''
    crosswalk file also saved to CSV. if there are any errors, the programmer can change the entries and upload the file to any future
    transformers. it'll be given preference over the PypmcaCrosswalk datasheet
'''
crosswalkFile = datasheet(myScenario, 'modelKarlenPypm_CrosswalkFile', empty=True)
crosswalkFile.File = [crosswalkFilename]
crosswalkFile.DateTime = [datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')]
saveDatasheet(myScenario, crosswalkFile, 'modelKarlenPypm_CrosswalkFile')


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

all_data_sources = pandas.DataFrame()

# the repository that all data descriptions and files are stored in
karlens_sources = requests.get('http://data.ipypm.ca/list_data_folders/covid19').json()

# reminder that 'karlen_country_name' may be a province or state if it's data is stratified
for karlen_country_name in karlens_sources.keys():

    # folder giving information for that city
    data_folder = karlens_sources[karlen_country_name]
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
    data_description = data_desc_resp.json()

    '''
        fancy* denotes the version of a Karlen variable that will be used for printing to the datasheet, rather than the raw names supplied (since
        they're not always intuitive, as stated above). 'fancy_country_name' is the fancy name for the karlen_country_name. for example, if the karlen_country_name
        is given as "california", the fancy name is: fancy_country_name = "USA: California"

        <fancy_country_name> - <fancy_region_name> is what appears in the drop-down menu for the getExpectations transformer. this is done through a combination of
        pycountry lookups and hard-coding. all this is done to make sure that the data source names match the .pypm model names (as the user sees them)
    '''
    fancy_country_name = karlen_country_name

    # progress message
    print('\n{}'.format(fancy_country_name))

    # for each region
    for karlen_region_name in data_description['regional_data'].keys():

        # reminder: fancy_region_name is the corrected version of karlen_region_name that will be shown in the drop-down menu for the getExpectations transformer
        fancy_region_name = karlen_region_name

        # retrieves any age information in the karlen_region_name name (ex. "<10", "30-39", "under 40", etc)
        age_range_dict = headerFile.ageRangeString(karlen_region_name)

        print(fancy_region_name)

        ### GERMANY_AGE

        if karlen_country_name == 'Germany_age':

            '''
                for the data set "Germany_age", the regions are stratified by age, and so the names of the regions take the form '[a-zA-Z]{2}_a[0-5]*',
                where the first two letters before the underscore give the ISO 3166-2 codes for the state, the "a" after the underscore represents "age",
                with the number following "a" giving the Robert-Koch Institut (RKI) age class (described in headerFile.ageRangeString).

                for instance, "bw_a2" denotes the data for RKI age class 2 (15-34) for the German state Baden-Wu:rttemburg. if the ISO 3166 code is 'de',
                then that's just Germany total, so fancy_region_name is set to None.
            '''

            fancy_country_name = 'Germany'

            # for this data set, get the coded karlen_region_name name and age class
            code = karlen_region_name.split('_')[0]
            # 'de' is the ISO 3166 code for Germany, so this is country-level data rather that regional
            if code == 'de':
                fancy_region_name = None

            else:
                # if valid ISO 3166-2 code, do pycountry lookup to find the region information
                py_subdivision = pycountry.subdivisions.get(code='DE-{}'.format(code.upper()))
                # get the fancy name of the region (includes diacritics)
                fancy_region_name = py_subdivision.name

            # fancy_data_source_name is the name the user will see in drop-downs. for example, "Canada - British Columbia", "Germany"
            if fancy_region_name == None:
                fancy_data_source_name = fancy_country_name
            else:
                # if there is a fancy region name, paste it. for example, "Canada - British Columbia - Fraser", "Germany - Nordrhein-Westfalen"
                # change all the dashes to underscores, since dashes generate a tree view ('Nordrhein-Westfalen' -> 'Nordrhein_Westfalen')
                # since Westfalen isn't a subregion of North Rhine, as it would appear when charting
                fancy_data_source_name = '{} - {}'.format(fancy_country_name, fancy_region_name.replace('-', '_'))

            all_data_sources = all_data_sources.append({
                'LUT' : fancy_data_source_name,
                'Country' :karlen_country_name,
                'Region' : karlen_region_name,
                'FancyCountry' : fancy_country_name,
                'FancyRegion' : fancy_region_name
            }, ignore_index=True)

            continue

        ### GERMANY

        elif karlen_country_name == 'Germany':

            '''
                for Germany (and I reckon it'll be the same with other countries added later), Karlen gives English state names here, but the pycountry
                package used to generate model region information gives the state names in German. to keep the names consistent (rather than creating
                two different jurisdictions for every German region, ex. both 'Germany - Nordrhein_Westfalen' and 'Germany - North Rhine-Westphalia'
                as different jurisdictions), here we translate the English state names to German ones (for ex., 'Bavaria' -> 'Bayern')
            '''

            fancy_region_name = headerFile.germanStateName(karlen_region_name)

        ### BRAZIL

        elif karlen_country_name == 'Brazil':

            # Karlen has preceded the Brazilian states by their ISO 3166-2 code, so "TO: Tocantins" becomes "Tocantins"
            fancy_region_name = fancy_region_name.split(':')[-1].strip()

        ### UK

        elif karlen_country_name == 'UK':

            # no gotchas with the names
            pass

        ### EU

        elif karlen_country_name == 'EU':

            ''' EU is not a country, so set the fancy_country_name as the region name and mark the fancy_region_name as being None '''

            fancy_country_name = fancy_region_name
            fancy_region_name = None

        ### CANADA

        elif karlen_country_name == 'Canada':

            # hard-coded Canadian provinces
            if fancy_region_name == 'BC':
                fancy_region_name = 'British Columbia'
            elif fancy_region_name == 'NWT':
                fancy_region_name = 'Northwest Territories'
            elif fancy_region_name == 'PEI':
                fancy_region_name = 'Prince Edward Island'

        elif karlen_country_name == 'BC':

            '''
                if fancy_region_name contains age/sex information and will not be used, and set to None. for example, the descriptions

                    "karlen_country_name - BC, karlen_region_name - Male"
                    "karlen_country_name - BC, karlen_region_name - Unknown"
                    "karlen_country_name - BC, karlen_region_name - 20-50"

                will all get the fancy_region_name None, so that the fancy name of the regions would be multiple copies of "Canada - British Columbia"
                (the karlen_country_name variable gave us the name of the state/province, and it's easy to find the country)
            '''

            fancy_country_name = 'Canada - British Columbia'

        ### ISRAEL

        elif karlen_country_name == 'Israel':

            # no gotchas with the names
            pass

        ### USA

        elif karlen_country_name == 'USA':

            # no gotchas with the names
            pass

        elif karlen_country_name == 'California':

            fancy_country_name = 'USA - California'

        # end country if statements


        # if the region variable gives only age information
        if set(age_range_dict.values()) != {None}:
              fancy_region_name = None
        # if the region variable gives gender information, set the fancy_region_name to None
        elif fancy_region_name in ['All', 'Male', 'Female', 'Unknown']:
            fancy_region_name = None

        if fancy_region_name == None:
            fancy_data_source_name = fancy_country_name
        else:
            fancy_data_source_name = '{} - {}'.format(fancy_country_name, fancy_region_name.replace('-', '_'))


        '''
            this is done to make sure that the regions are unique. Karlen has two regions each with the names "All" (BC and Israel),
                "Germany" (Germany and Germany_age) and "Unknown". since the combination of country and region is unique, we just tack
                the country name to the end, and remove it in the getData transformer.
        '''
        if karlen_region_name in ['Germany', 'All', 'Unknown']:
            karlen_region_name = '{} {}'.format(karlen_region_name, karlen_country_name)

        # write to the output table
        all_data_sources = all_data_sources.append({
            'LUT' : fancy_data_source_name,
            'Country' :karlen_country_name,
            'Region' : karlen_region_name,
            'FancyCountry' : fancy_country_name,
            'FancyRegion' : fancy_region_name
        }, ignore_index=True)

# a line to display the entire table
with pandas.option_context('display.max_rows', None, 'display.max_columns', None): print(all_data_sources)

# add the complete list of models (duplicates included) to a visible datasheet
pypmcaData = datasheet(myScenario, "modelKarlenPypm_PypmcaData").drop(columns=['PypmcaDataID'])
tempSources = all_data_sources[-all_data_sources.Region.isin(pypmcaData.Region)]
if not tempSources.empty:
    saveDatasheet(myScenario, tempSources, 'modelKarlenPypm_PypmcaData')

# # to create a drop-down for the getData transformer, we take all the fancy jurisdictions and remove the duplicates
dataAvail = all_data_sources[['LUT']].drop_duplicates().rename(columns={'LUT': 'Name'})

# write to a table that will create the drop-down option menu
dropdown = datasheet(myScenario, "modelKarlenPypm_DataDropdown").drop(columns=['DataDropdownID'])
dataAvail = dataAvail[-dataAvail.Name.isin(dropdown.Name)]
if not dataAvail.empty:
    saveDatasheet(myScenario, dataAvail, "modelKarlenPypm_DataDropdown")

