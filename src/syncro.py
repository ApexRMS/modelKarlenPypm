for i in list(globals().keys()):
    if(i[0] != '_'):
        exec('del {}'.format(i))

import subprocess as sp
import pandas as pd
import numpy as np
import io
import re
import tempfile
import shutil
import logging

class Syncro:

    __consolePath = ''
    __theConsole = ''
    __libraryPath = ''
    __projects = {}
    __scenarios = {}

    def __init__(self, ConsolePath, LibraryPath):

        self.__consolePath = ConsolePath
        self.__libraryPath = LibraryPath
        self.__theConsole = '{}\\SyncroSim.Console.exe'.format(self.__consolePath)

        self.__terminalOutput = ''

        for projectName in self.getProjects():
            projNumber = self.getProjectID(projectName)
            self.__projects[projNumber] = projectName

        for scenarioName in self.getProjects():
            projNumber = self.getProjectID(projectName)
            self.__projects[projNumber] = projectName

    ##################### FUNCTIONAL #################

    def __parseOutputAsTable(self, stringCommand:str):
        terminalOutput = str(sp.check_output(stringCommand), 'utf-8')
        commaSeparated1 = terminalOutput.replace(',', '*')
        commaSeparated2 = commaSeparated1.replace('\r', '')
        commaSeparated3 = re.sub('{}+'.format(2*' '), ',', commaSeparated2)
        commaSeparated4 = commaSeparated3.replace(',\n', '\n')
        commaSeparated5 = commaSeparated4.replace(' ', '')
        asTable = pd.read_csv(io.StringIO(commaSeparated5))
        return asTable

    def getOutput(self):
        return self.__terminalOutput

    def newProject(self, newProjectName:str):
        if newProjectName in self.getProjects():
            return self.getProjectID(newProjectName)
        cmdLine = '{} --lib={} --create --project --name={}'.format(self.__theConsole, self.__libraryPath, newProjectName)
        terminalOutput = str(sp.check_output(cmdLine), 'utf-8')
        newProjectNumber = int(terminalOutput.split(' ')[-1].replace('\r\n', ''))
        self.__projects[newProjectNumber] = newProjectName
        return newProjectNumber

    # assuming that all scenario names in the same project are unique
    def newScenario(self, newScenarioName:str, secondParameter):
        parentProjectNumber = None
        if isinstance(secondParameter, str):
            parentProjectNumber = self.getProjectID(secondParameter)
        elif isinstance(secondParameter, int) or isinstance(secondParameter, np.int64):
            parentProjectNumber = secondParameter
        if newScenarioName in self.getScenarios(parentProjectNumber):
            return self.getScenarioID(newScenarioName, parentProjectNumber )
        cmdLine = '{} --lib={} --create --scenario --tpid={} --name={}'.format(self.__theConsole, self.__libraryPath, parentProjectNumber, newScenarioName)
        terminalOutput = str(sp.check_output(cmdLine), 'utf-8')
        newScenarioNumber = int(terminalOutput.split(' ')[-1].replace('\r\n', ''))
        self.__scenarios[newScenarioNumber] = newScenarioName
        return newScenarioNumber

    def getConsolePath(self):
        return self.__consolePath

    def getLibraryPath(self):
        return self.__libraryPath

    def getConsoles(self):
        cmdLine = '{} --lib={} --list --consoles'.format(self.__theConsole, self.__libraryPath)
        asTable = self.__parseOutputAsTable(cmdLine)
        return list(asTable.Name)

    def getProjects(self, fullTable:bool=False):
        cmdLine = '{} --lib={} --list --projects'.format(self.__theConsole, self.__libraryPath)
        # print(cmdLine)
        asTable = self.__parseOutputAsTable(cmdLine)
        if fullTable:
            return asTable
        else:
            return list(set(asTable.Name))

    # assumes that all project names in the same library are unique - this is clearly a bad assumption
    def getProjectID(self, name:str):
        All = self.getProjects(True)
        for index in range(0, All.shape[0]):
            if All.Name[index]==name:
                return(All.ID[index])
        return None

    def getProjectName(self, projID:int):
        All = self.getProjects(True)
        for index in range(0, All.shape[0]):
            if All.ID[index]==projID:
                return(All.Name[index])
        return None

    def getDataProviders(self):
        cmdLine = '{} --lib={} --list --dataproviders'.format(self.__theConsole, self.__libraryPath)
        asTable = self.__parseOutputAsTable(cmdLine)
        return dict(zip(asTable.Name, asTable.DisplayName))

    def getScenarios(self, projectID:int, fullTable:bool=False):
        tempDir = tempfile.mkdtemp()
        exportFilename = '{}\\export.csv'.format(tempDir)
        cmdLine = '{} --lib={} --file={} --list --scenarios --csv'.format(self.__theConsole, self.__libraryPath, exportFilename)
        sp.call(cmdLine)
        theExport = pd.read_csv(exportFilename)
        theExport.columns = [x.replace(' ', '_') for x in theExport.columns]
        shutil.rmtree(tempDir)
        theExport = theExport[theExport.Project_ID==projectID]
        if fullTable:
            return theExport
        else:
            return list(theExport.Scenario_ID)

    def getScenarioID(self, scenarioName:str, projectID:int):
        allScenarios = self.getScenarios(projectID, True)
        if scenarioName in list(allScenarios.Name):
            return allScenarios[allScenarios['Name']==scenarioName].Scenario_ID[0]
        else:
            return None

    def getDatasheet(self, scenarioID:int=None, datasheetName:str=None, projectID:int=None, empty:bool=False):
        if datasheetName == None:
            cmdLine = '{} --lib={} --list --datasheets'.format(self.__theConsole, self.__libraryPath)
            sp.call(cmdLine)
        else:
            tempDir = tempfile.mkdtemp()
            exportFilename = '{}\\export.csv'.format(tempDir)
            cmdLine = '{} --lib={} --sheet={} --file={} --export --includepk'.format(self.__theConsole, self.__libraryPath, datasheetName, exportFilename)
            if projectID != None:
                cmdLine += ' --pid={0}'.format(projectID)
            if scenarioID != None:
                cmdLine += ' --sid={0}'.format(scenarioID)
            sp.call(cmdLine)
            theTable = pd.read_csv(exportFilename)
            shutil.rmtree(tempDir)
            if empty:
                return theTable[0:0]
            else:
                return theTable

    ##################### BROKEN #################

    def getDatafeeds(self):
        cmdLine = '{} --lib={} --list --datafeeds'.format(self.__theConsole, self.__libraryPath)
        print(cmdLine)
        sp.call(cmdLine)


    def getModels(self):
        cmdLine = '{} --lib={} --list --models'.format(self.__theConsole, self.__libraryPath)
        print(cmdLine)
        sp.call(cmdLine)


    def getLibrary(self):
        cmdLine = '{} --lib={} --list --library'.format(self.__theConsole, self.__libraryPath)
        sp.call(cmdLine)
        asTable = self.__parseOutputAsTable(cmdLine)
        return asTable

    def saveDatasheet(self, scenarioID:int, dataSheet:pd.core.frame.DataFrame, sheetGivenName:str):
        if dataSheet.shape[0] == 0:
            return None
        tempDir = tempfile.mkdtemp()
        exportFilename = '{}\\export.csv'.format(tempDir)
        dataSheet.to_csv(exportFilename, index=False)
        cmdLine = '{} --lib={} --sid={} --sheet={} --file={} --import'.format(self.__theConsole, self.__libraryPath, scenarioID, sheetGivenName, exportFilename)
        # print(cmdLine)
        sp.call(cmdLine)
        shutil.rmtree(tempDir)
        return None

console_path = 'C:\\Program Files\\SyncroSim'
library_path = 'C:\\Users\\User\\Documents\\SyncroSim\\Libraries\\modelKarlenPypm.ssim'
theConsole = '{}\\SyncroSim.Console.exe'.format(console_path)

ss = Syncro(console_path, library_path)
hereProj = ss.newProject('Definitions')
myScenario = ss.newScenario('myScenario', hereProj)


# paramValues = ss.getDatasheet(scen_number, "modelKarlenPypm_ParameterValues", empty=True)
# new_row = pd.Series({'Name':'lolsjhsiodfghojsa', 'Description':'foosadjfklas;jnkdfcvl', 'Type':'int', 'Initial':2, 'Min':1, 'Max':3 , 'Status':'variable', 'PriorDist':'norm', 'PriorMean':2, 'PriorSecond':1, 'MCMCStep':0.03})
# paramValues = paramValues.append(new_row, ignore_index=True)
# # parameterValues["ScenarioID"] = [scen_number]

# paramValues.to_csv("export.csv", index=False)


# ss.saveDatasheet(scen_number, paramValues, "modelKarlenPypm_ParameterValues")

# # paramValues['ScenarioID'] = [scen_number]

# ss.saveDatasheet(scen_number, paramValues, "modelKarlenPypm_ParameterValues")


# cmdLine = '{} --lib={} --file={} --list --scenarios --csv'.format(theConsole, library_path, "C:\\Users\\User\\Documents\\GitHub\\modelKarlenPypm\\export.csv")


# terminalOutput = str(sp.check_output(cmdLine), 'utf-8')
# commaSeparated1 = terminalOutput.replace(',', '*')
# commaSeparated2 = commaSeparated1.replace('\r', '')
# commaSeparated3 = re.sub('{}+'.format(3*' '), ',', commaSeparated2)
# commaSeparated4 = commaSeparated3.replace(',\n', '\n')
# asTable = pd.read_csv(io.StringIO(commaSeparated4))
#
# text_file = open("C:\\Users\\User\\Documents\\Github\\modelKarlenPypm\\foobar.txt", "w")
# text_file.write(commaSeparated3)
# text_file.close()

# lols = sp.check_output(cmdLine)
