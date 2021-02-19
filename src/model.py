#!/usr/bin/python

import requests
import os
import sys
import pickle
import pypmca

import pandas as pd

def open_model(filename, my_pickle):
    model = pickle.loads(my_pickle)
    time_step = model.get_time_step()
    if time_step > 1.001 or time_step < 0.999:
        print('Filename: ' + filename)
        print('*** Model NOT loaded ***')
        print('Currently, ipypm only supports models with time_step = 1 day.')
    return model

try:
    folders_resp = requests.get('http://data.ipypm.ca/list_model_folders/covid19');
except requests.exceptions.RequestException as error:
    print('Error retrieving model folder list over network:')
    print()
    print(error)

region_model_folders = folders_resp.json();
region_list = list(region_model_folders.keys());

# set_region = input('Models are available for the following regions: %s.\nChoose one:  ' % ', '.join(region_list));
set_region = 'Canada';

try:
    if set_region not in region_list:
        raise Halt();
except Halt as hl:
#     print(hl);
    print('Error: country not found')

folder = region_model_folders[set_region];
models_resp = requests.get('http://data.ipypm.ca/list_models/' + folder);

model_filenames = models_resp.json();
model_list = list(model_filenames.keys());

# set_model = input('\nChoose a pre-tuned model from: %s.\nChoice: ' % ', '.join(model_list));
set_model = 'bcc_2_6_1224';

model_fn = model_filenames[set_model]

try:
    pypm_resp = requests.get('http://data.ipypm.ca/get_pypm/' + model_fn, stream=True);
except requests.exceptions.RequestException as error:
    print('Error retrieving model over network:')
    print()
    print(error)

my_pickle = pypm_resp.content
filename = model_fn.split('/')[-1]
model = open_model(filename, my_pickle);

try:
    if isinstance(model, type(None)):
        raise Halt('Error: model not retrieved');
except Halt as hl:
    print(hl);

# Printing complete model information from the object downloaded
print('\nModel: {}.\n\tDescripton: {}'.format(model.name, model.description));
# printing information about the model populations
print('\n\tPopulations:');
for pop_name in model.populations:
    population = model.populations[pop_name];
    print('\t\t{:<20s}\t{}'.format(population.name, population.description));

model.save_file('{}\\downloaded_model.pypm'.format('C:\\Users\\User\\Documents\\SyncroSim\\Packages\\modelKarlenPypm'))

print('Getting the default parameters...')
import karlenDecompose

print('Rebuilding the model...')
import karlenRebuild

print('Running the simulations...')
import karlenSimulations
