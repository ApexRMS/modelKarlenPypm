library(rsyncrosim)
library(data.table)
library(reticulate)
library(stringr)
library(RCurl)

# py_install("requests", pip=TRUE)
# py_install("pypmca", pip=TRUE)
# py_install("pandas", pip=TRUE)

env <- ssimEnvironment()
myScenario <- scenario()

source_python("fetchModels.py")

get_r_dict_from_webpage <- function(url)
{
    scenario_python_dictionary <- gsub('\\"*', "", suppressWarnings(readLines(url)))
    second_stage <- str_remove_all(scenario_python_dictionary, "[{,}]")
    third_stage <- sub("\\:.*", "", read.table(text=second_stage))
    key_list <- third_stage[seq_along(third_stage) %% 2 > 0]
    page_list <- third_stage[seq_along(third_stage) %% 2 == 0]
    dictionary <- as.list(setNames(page_list, key_list))
    return(dictionary)
}

modelsAvailable <- datasheet(myScenario, "modelKarlenPypm_ModelsAvailable", empty=TRUE)

availableRegions <- get_r_dict_from_webpage("http://data.ipypm.ca/list_model_folders/covid19")

for(regionName in names(availableRegions))
{
    availableModels <- get_r_dict_from_webpage(paste0("http://data.ipypm.ca/list_models/", availableRegions[regionName]))

    for(regionalModel in names(availableModels))
    {
        theURL <- paste0("http://data.ipypm.ca/get_pypm/", availableModels[regionalModel])
        modelFilename <- sprintf("%s\\%s.pypm", env$TempDirectory, regionalModel)

        saveModel(theURL, modelFilename)
        nameDescrip <- getModelNameDescription(modelFilename)

        modelsAvailable <- addRow(modelsAvailable, value = c(
            "Region" = regionName,
            "Name" = nameDescrip[["name"]],
            "Description" = nameDescrip[["description"]]
        ))
    }
}

saveDatasheet(myScenario, modelsAvailable, "modelKarlenPypm_ModelsAvailable")

# import requests
# import subprocess as sp
# import pandas as pd
# import syncro
# import tempfile
# import headerFile
#
# # everything in this file works
#
# consolePath = 'C:\\Program Files\\SyncroSim'
# libraryPath = 'C:\\Users\\User\\Documents\\SyncroSim\\Libraries\\epi.ssim'
# theConsole = '{}\\SyncroSim.Console.exe'.format(consolePath)
#
# ss = syncro.Syncro(consolePath, libraryPath)
# hereProj = 1 # ss.newProject('Definitions')
# myScenario = 1 # ss.newScenario('myScenario', hereProj)
#
# jurisDictionary = {}
#
# foldersResponse = requests.get('http://data.ipypm.ca/list_model_folders/covid19')
# regionModelFolders = foldersResponse.json()
# regionList = list(regionModelFolders.keys())
#
# modelsAvailable = []
#
# for region in regionList:
#
#     folder = regionModelFolders[region]
#     regionPrintName = folder.split('/')[-1]
#     modelsResponse = requests.get('http://data.ipypm.ca/list_models/' + folder)
#
#     modelFilenames = modelsResponse.json()
#     modelList = list(modelFilenames.keys())
#
#     for model in modelList:
#
#         modelFn = modelFilenames[model]
#         filename = modelFn.split('/')[-1]
#
#         modelPrintName = modelFn.split('/')[-1].replace('.pypm', '')
#         fullModelName = '{}: {}'.format(regionPrintName, modelPrintName)
#
#         pypmResponse = requests.get('http://data.ipypm.ca/get_pypm/' + modelFn, stream=True)
#
#         myPickle = pypmResponse.content
#         model = headerFile.openModel(filename, myPickle)
#
#         model.save_file('{}.temp\\{}'.format(libraryPath, filename))
#         modelDescrip = model.description.replace('\"', '').replace('\'', '')
#
#         jurisDictionary[fullModelName] = modelDescrip
#
#         modelsAvailable.append({
#             'Region':regionPrintName,
#             'Name':filename,
#             'Description':modelDescrip
#         })
#
#     break
#
# theJurisdictions = ss.getDatasheet(myScenario, 'epi_Jurisdiction', projectID=hereProj, empty=True)
# theJurisdictions = theJurisdictions.drop(columns=['JurisdictionID'])
#
# theJurisdictions.Name = pd.Series(jurisDictionary.keys())
# theJurisdictions.Description = pd.Series(jurisDictionary.values())
#
# exportFilename = "C:\\Users\\User\\Documents\\haha7.csv"
#
# theJurisdictions.to_csv(exportFilename, index=False)
# cmdLine = '"{}" --lib={} --sid={} --pid={} --sheet={} --file={} --import'.format(theConsole, libraryPath, myScenario, hereProj, "epi_Jurisdiction", exportFilename)
# print(cmdLine)
# sp.call(cmdLine)
#
# theModels = ss.getDatasheet(myScenario, "modelKarlenPypm_ModelsAvailable", empty=True)
# theModels = theModels.drop(columns=['ModelsAvailableID'])
#
# exportFilename = "C:\\Users\\User\\Documents\\haha8.csv"
#
# pd.DataFrame(modelsAvailable).to_csv(exportFilename, index=False)
# cmdLine = '"{}" --lib={} --sid={} --pid={} --sheet={} --file={} --import'.format(theConsole, libraryPath, myScenario, hereProj, "modelKarlenPypm_ModelsAvailable", exportFilename)
# print(cmdLine)
# sp.call(cmdLine)
