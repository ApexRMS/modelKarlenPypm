for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import os
import io
import re
import pandas
import subprocess
import tempfile
import shutil

pandas.set_option('display.max_columns', None)
pandas.set_option('display.width', 1000)

def ssimEnvironment():

    theSeries = {
        'PackageDirectory' : os.getenv('SSIM_PACKAGE_DIRECTORY'),
        'ProgramDirectory' : os.getenv('SSIM_PROGRAM_DIRECTORY'),
        'LibraryFilePath' : os.getenv('SSIM_LIBRARY_FILEPATH'),
        'ProjectId' : os.getenv('SSIM_PROJECT_ID'),
        'ScenarioId' : os.getenv('SSIM_SCENARIO_ID'),
        'InputDirectory' : os.getenv('SSIM_INPUT_DIRECTORY'),
        'OutputDirectory' : os.getenv('SSIM_OUTPUT_DIRECTORY'),
        'TempDirectory' : os.getenv('SSIM_TEMP_DIRECTORY'),
        'TransferDirectory' : os.getenv('SSIM_TRANSFER_DIRECTORY'),
        'BeforeIteration' : os.getenv('SSIM_STOCHASTIC_TIME_BEFORE_ITERATION'),
        'AfterIteration' : os.getenv('SSIM_STOCHASTIC_TIME_AFTER_ITERATION'),
        'BeforeTimestep' : os.getenv('SSIM_STOCHASTIC_TIME_BEFORE_TIMESTEP'),
        'AfterTimestep' : os.getenv('SSIM_STOCHASTIC_TIME_AFTER_TIMESTEP')
    }

    return pandas.Series(data = theSeries, index = list(theSeries.keys()))

def parseOutputAsTable(stringCommand:str):
    terminalOutput = str(subprocess.check_output(stringCommand), 'utf-8')
    commaSeparated1 = terminalOutput.replace(',', '*')
    commaSeparated2 = commaSeparated1.replace('\r', '')
    commaSeparated3 = re.sub('{}+'.format(2*' '), ',', commaSeparated2)
    commaSeparated4 = commaSeparated3.replace(',\n', '\n')
    commaSeparated5 = commaSeparated4.replace(' ', '')
    asTable = pandas.read_csv(io.StringIO(commaSeparated5))
    return asTable

class scenario:

    projectId = None
    scenarioId = None
    parentId = None
    breakpoints = []
    session = []
    filepath = ""
    datasheetNames = pandas.DataFrame()
    console = ""

    def __init__(self, env:pandas.Series=None):

        if env == None:
            env = ssimEnvironment()

        self.projectId = int(env.ProjectId)
        self.scenarioId = int(env.ScenarioId)
        self.parentId = None
        self.breakpoints = []
        self.session = [env.ProgramDirectory, False]
        self.filepath = env.LibraryFilePath
        self.console = '{}\\SyncroSim.Console.exe'.format(ssimEnvironment().ProgramDirectory)

        cmdLine = '"{}" --list --datasheets --lib={}'.format(self.console, env.LibraryFilePath)
        # print(type(parseOutputAsTable(cmdLine)))
        self.datasheetNames = parseOutputAsTable(cmdLine)

    def __str__(self):
        return "Project ID: {}\nScenario ID: {}\nDatasheets: {}".format(self.projectId, self.scenarioId, list(self.datasheetNames.Name))


def getScenarios(theScenario:scenario, fullTable:bool=False):
    tempDir = tempfile.mkdtemp()
    exportFilename = '{}\\export.csv'.format(tempDir)
    cmdLine = '{} --lib={} --file={} --list --scenarios --csv'.format(theScenario.console, theScenario.filepath, exportFilename)
    subprocess.call(cmdLine)
    theExport = pandas.read_csv(exportFilename)
    theExport.columns = [x.replace(' ', '_') for x in theExport.columns]
    print(theExport)
    shutil.rmtree(tempDir)
    theExport = theExport[theExport.Project_ID == theScenario.projectId]
    if fullTable:
        return theExport
    else:
        return list(theExport.Scenario_ID)

def datasheet(theScenario:scenario, datasheetName:str=None, empty:bool=False):

    getDatasheetsLine = '"{}" --list --datasheets --lib={}'.format(theScenario.console, theScenario.filepath)
    currentDatasheets = parseOutputAsTable(getDatasheetsLine)

    if datasheetName == None:
        return currentDatasheets
    elif datasheetName not in list(currentDatasheets.Name):
        print("ERROR: no table by that name")
        return None
    else:
        tempDir = tempfile.mkdtemp()
        exportFilename = '{}\\export.csv'.format(tempDir)
        cmdLine = '"{}" --lib={} --export --includepk --sheet={} --file={} --sid={} --pid={}'.format(
            theScenario.console, theScenario.filepath, datasheetName, exportFilename, theScenario.scenarioId, theScenario.projectId
        )
        subprocess.call(cmdLine)
        theTable = pandas.read_csv(exportFilename)
        shutil.rmtree(tempDir)
        if empty:
            return theTable[0:0]
        else:
            return theTable

def saveDatasheet(theScenario:scenario, dataSheet:pandas.core.frame.DataFrame, datasheetName:str, append:bool=False):

    getDatasheetsLine = '"{}" --list --datasheets --lib={}'.format(theScenario.console, theScenario.filepath)
    currentDatasheets = parseOutputAsTable(getDatasheetsLine)

    if datasheetName not in list(currentDatasheets.Name):
        print("ERROR: no table by that name")
        return None
    elif dataSheet.shape[0] == 0:
        print("ERROR: empty data sheet")
        return None

    tempDir = tempfile.mkdtemp()
    exportFilename = '{}\\export.csv'.format(tempDir)
    dataSheet.to_csv(exportFilename, index=False)

    if append == False:
        cmdLine = '"{}" --import --lib={} --sid={} --pid={} --sheet={} --file={}'.format(
            theScenario.console, theScenario.filepath, theScenario.scenarioId, theScenario.projectId, datasheetName, exportFilename
        )
        subprocess.call(cmdLine)
        shutil.rmtree(tempDir)

        env = ssimEnvironment()
        exportFilename2 = '{}\\SSIM_OVERWRITE-{}.csv'.format(env.TransferDirectory, datasheetName)
        dataSheet.to_csv(exportFilename2, index=False)

    else:
        cmdLine = '"{}" --import --append --lib={} --sid={} --pid={} --sheet={} --file={}'.format(
            theScenario.console, theScenario.filepath, theScenario.scenarioId, theScenario.projectId, datasheetName, exportFilename
        )
        subprocess.call(cmdLine)
        shutil.rmtree(tempDir)

        env = ssimEnvironment()
        exportFilename2 = '{}\\SSIM_APPEND-{}.csv'.format(env.TransferDirectory, datasheetName)
        dataSheet.to_csv(exportFilename2, index=False)

    return None



# myScenario = scenario()
# getScenarios(myScenario)
# print()
# datasheet(myScenario)



# import pandas as pd
# import numpy as np
# import io
# import tempfile
# import shutil
# import logging
#
# class Syncro:
#
#     __consolePath = ''
#     theConsole = ''
#     __libraryPath = ''
#     __projects = {}
#     __scenarios = {}
#
#     def __init__(self, ConsolePath, LibraryPath):
#
#         self.__consolePath = ConsolePath
#         self.__libraryPath = LibraryPath
#         self.theConsole = '{}\\SyncroSim.Console.exe'.format(self.__consolePath)
#
#         self.__terminalOutput = ''
#
#         for projectName in self.getProjects():
#             projNumber = self.getProjectID(projectName)
#             self.__projects[projNumber] = projectName
#
#         for scenarioName in self.getProjects():
#             projNumber = self.getProjectID(projectName)
#             self.__projects[projNumber] = projectName
#
#     ##################### FUNCTIONAL #################
#
#     def __parseOutputAsTable(self, stringCommand:str):
#         terminalOutput = str(subprocess.check_output(stringCommand), 'utf-8')
#         commaSeparated1 = terminalOutput.replace(',', '*')
#         commaSeparated2 = commaSeparated1.replace('\r', '')
#         commaSeparated3 = re.sub('{}+'.format(2*' '), ',', commaSeparated2)
#         commaSeparated4 = commaSeparated3.replace(',\n', '\n')
#         commaSeparated5 = commaSeparated4.replace(' ', '')
#         asTable = pandas.read_csv(io.StringIO(commaSeparated5))
#         return asTable
#
#     def getOutput(self):
#         return self.__terminalOutput
#
#     def newProject(self, newProjectName:str):
#         if newProjectName in self.getProjects():
#             return self.getProjectID(newProjectName)
#         cmdLine = '{} --lib={} --create --project --name={}'.format(self.theConsole, self.__libraryPath, newProjectName)
#         terminalOutput = str(subprocess.check_output(cmdLine), 'utf-8')
#         newProjectNumber = int(terminalOutput.split(' ')[-1].replace('\r\n', ''))
#         self.__projects[newProjectNumber] = newProjectName
#         return newProjectNumber
#
#     # assuming that all scenario names in the same project are unique
#     def newScenario(self, newScenarioName:str, secondParameter):
#         parentProjectNumber = None
#         if isinstance(secondParameter, str):
#             parentProjectNumber = self.getProjectID(secondParameter)
#         elif isinstance(secondParameter, int) or isinstance(secondParameter, numpy.int64):
#             parentProjectNumber = secondParameter
#         if newScenarioName in self.getScenarios(parentProjectNumber):
#             return self.getScenarioID(newScenarioName, parentProjectNumber )
#         cmdLine = '{} --lib={} --create --scenario --tpid={} --name={}'.format(self.theConsole, self.__libraryPath, parentProjectNumber, newScenarioName)
#         terminalOutput = str(subprocess.check_output(cmdLine), 'utf-8')
#         newScenarioNumber = int(terminalOutput.split(' ')[-1].replace('\r\n', ''))
#         self.__scenarios[newScenarioNumber] = newScenarioName
#         return newScenarioNumber
#
#     def getConsolePath(self):
#         return self.__consolePath
#
#     def getLibraryPath(self):
#         return self.__libraryPath
#
#     def getConsoles(self):
#         cmdLine = '{} --lib={} --list --consoles'.format(self.theConsole, self.__libraryPath)
#         asTable = self.__parseOutputAsTable(cmdLine)
#         return list(asTable.Name)
#
#     def getProjects(self, fullTable:bool=False):
#         cmdLine = '{} --lib={} --list --projects'.format(self.theConsole, self.__libraryPath)
#         # print(cmdLine)
#         asTable = self.__parseOutputAsTable(cmdLine)
#         if fullTable:
#             return asTable
#         else:
#             return list(set(asTable.Name))
#
#     # assumes that all project names in the same library are unique - this is clearly a bad assumption
#     def getProjectID(self, name:str):
#         All = self.getProjects(True)
#         for index in range(0, All.shape[0]):
#             if All.Name[index]==name:
#                 return(All.ID[index])
#         return None
#
#     def getProjectName(self, projID:int):
#         All = self.getProjects(True)
#         for index in range(0, All.shape[0]):
#             if All.ID[index]==projID:
#                 return(All.Name[index])
#         return None
#
#     def getDataProviders(self):
#         cmdLine = '{} --lib={} --list --dataproviders'.format(self.theConsole, self.__libraryPath)
#         asTable = self.__parseOutputAsTable(cmdLine)
#         return dict(zip(asTable.Name, asTable.DisplayName))
#
#     def getScenarios(self, projectID:int, fullTable:bool=False):
#         tempDir = tempfile.mkdtemp()
#         exportFilename = '{}\\export.csv'.format(tempDir)
#         cmdLine = '{} --lib={} --file={} --list --scenarios --csv'.format(self.theConsole, self.__libraryPath, exportFilename)
#         subprocess.call(cmdLine)
#         theExport = pandas.read_csv(exportFilename)
#         theExport.columns = [x.replace(' ', '_') for x in theExport.columns]
#         shutil.rmtree(tempDir)
#         theExport = theExport[theExport.Project_ID==projectID]
#         if fullTable:
#             return theExport
#         else:
#             return list(theExport.Scenario_ID)
#
#     def getScenarioID(self, scenarioName:str, projectID:int):
#         allScenarios = self.getScenarios(projectID, True)
#         if scenarioName in list(allScenarios.Name):
#             return allScenarios[allScenarios['Name']==scenarioName].Scenario_ID[0]
#         else:
#             return None
#
#     def getDatasheet(self, scenarioID:int=None, datasheetName:str=None, projectID:int=None, empty:bool=False):
#         if datasheetName == None:
#             cmdLine = '{} --lib={} --list --datasheets'.format(self.theConsole, self.__libraryPath)
#             subprocess.call(cmdLine)
#         else:
#             tempDir = tempfile.mkdtemp()
#             exportFilename = '{}\\export.csv'.format(tempDir)
#             cmdLine = '{} --lib={} --sheet={} --file={} --export --includepk'.format(self.theConsole, self.__libraryPath, datasheetName, exportFilename)
#             if projectID != None:
#                 cmdLine += ' --pid={0}'.format(projectID)
#             if scenarioID != None:
#                 cmdLine += ' --sid={0}'.format(scenarioID)
#             print(cmdLine)
#             subprocess.call(cmdLine)
#             theTable = pandas.read_csv(exportFilename)
#             shutil.rmtree(tempDir)
#             if empty:
#                 return theTable[0:0]
#             else:
#                 return theTable
#
#     def saveDatasheet(self, scenarioID:int, dataSheet:pandas.core.frame.DataFrame, sheetGivenName:str, projectID:int=None):
#         # if dataSheet.shape[0] == 0:
#         #     return None
#         # tempDir = tempfile.mkdtemp()
#         # exportFilename = '{}\\export.csv'.format(tempDir)
#         # dataSheet.to_csv(exportFilename, index=False)
#         # cmdLine = '{} --lib={} --sid={} --sheet={} --file={} --import'.format(self.theConsole, self.__libraryPath, scenarioID, sheetGivenName, exportFilename)
#         # if projectID != None:
#         #     cmdLine += '--pid={}'.format(projectID)
#         # # print(cmdLine)
#         # subprocess.call(cmdLine)
#         # shutil.rmtree(tempDir)
#         return None
#
#     ##################### BROKEN #################
#
#     def getDatafeeds(self):
#         cmdLine = '{} --lib={} --list --datafeeds'.format(self.theConsole, self.__libraryPath)
#         print(cmdLine)
#         subprocess.call(cmdLine)
#
#     def getModels(self):
#         cmdLine = '{} --lib={} --list --models'.format(self.theConsole, self.__libraryPath)
#         print(cmdLine)
#         subprocess.call(cmdLine)
#
#     def getLibrary(self):
#         cmdLine = '{} --lib={} --list --library'.format(self.theConsole, self.__libraryPath)
#         subprocess.call(cmdLine)
#         asTable = self.__parseOutputAsTable(cmdLine)
#         return asTable
#
# console_path = 'C:\\Program Files\\SyncroSim'
# library_path = 'C:\\Users\\User\\Documents\\SyncroSim\\Libraries\\modelKarlenPypm.ssim'
# theConsole = '{}\\SyncroSim.Console.exe'.format(console_path)
#
# ss = Syncro(console_path, library_path)
# hereProj = ss.newProject('Definitions')
# myScenario = ss.newScenario('myScenario', hereProj)
