#!/usr/bin/env python3

"""exstract_entire_lib.py: Exstracts xs vs energy data from h5 based library"""

__author__      = "Jonathan Shimwell"

import argparse
import os
from pathlib import Path
import h5py
import matplotlib.pyplot as plt
import numpy as np
# import openmc.data
from tqdm import tqdm

import openmc
from openmc.data import *

from data_formatting_tools import *
from database_tools import *

parser = argparse.ArgumentParser()
parser.add_argument('-l', '--library',
                    help='the name of the lirary for example fendl 3.1d endf B-VII.1')                    
parser.add_argument('-d', '--dir_hdf5',
                    default = None,
                    help='directory containing hdf5 files"'),
parser.add_argument('-j', '--dir_json',
                    default = None,
                    help='directory containing json files"'),   
parser.add_argument('-i', '--ignore',
                    nargs = '*',
                    default = [],
                    help='hdf5 files that are not added to the database"') 
parser.add_argument('-c', '--commit',
                   choices = ['yes','no'],
                   default = 'yes',
                   help = 'Adds the nuclear data to the mongo database')

args = parser.parse_args()


library=args.library
files_to_ignore = args.ignore
datapath = args.dir_hdf5
if args.dir_json == None:
    json_datapath = args.dir_hdf5
else:
    json_datapath = args.dir_json

Path(json_datapath).mkdir(parents=True, exist_ok=True)

print('ignoring ',files_to_ignore)
list_of_json_objects = []
# os.system('mongod --bind_ip_all &')

# should be added to openmc data?
ELEMENT_NAME = {0: 'neutron', 1: 'Hydrogen', 2: 'Helium', 3: 'Lithium',
                 4: 'Beryllium', 5: 'Boron', 6: 'Carbon', 7: 'Nitrogen',
                 8: 'Oxygen', 9: 'Fluorine', 10: 'Neon', 11: 'Sodium',
                 12: 'Magnesium', 13: 'Aluminium', 14: 'Silicon',
                 15: 'Phosphorus', 16: 'Sulfur', 17: 'Chlorine',
                 18: 'Argon', 19: 'Potassium', 20: 'Calcium',
                 21: 'Scandium', 22: 'Titanium', 23: 'Vanadium',
                 24: 'Chromium', 25: 'Manganese', 26: 'Iron',
                 27: 'Cobalt', 28: 'Nickel', 29: 'Copper', 30: 'Zinc',
                 31: 'Gallium', 32: 'Germanium', 33: 'Arsenic',
                 34: 'Selenium', 35: 'Bromine', 36: 'Krypton',
                 37: 'Rubidium', 38: 'Strontium', 39: 'Yttrium',
                 40: 'Zirconium', 41: 'Niobium', 42: 'Molybdenum',
                 43: 'Technetium', 44: 'Ruthenium', 45: 'Rhodium',
                 46: 'Palladium', 47: 'Silver', 48: 'Cadmium', 49: 'Indium',
                 50: 'Tin', 51: 'Antimony', 52: 'Tellurium', 53: 'Iodine',
                 54: 'Xenon', 55: 'Caesium', 56: 'Barium', 57: 'Lanthanum',
                 58: 'Cerium', 59: 'Praseodymium', 60: 'Neodymium',
                 61: 'Promethium', 62: 'Samarium', 63: 'Europium', 
                 64: 'Gadolinium', 65: 'Terbium', 66: 'Dysprosium',
                 67: 'Holmium', 68: 'Erbium', 69: 'Thulium',
                 70: 'Ytterbium', 71: 'Lutetium', 72: 'Hafnium',
                 73: 'Tantalum', 74: 'Tungsten', 75: 'Rhenium',
                 76: 'Osmium', 77: 'Iridium', 78: 'Platinum',
                 79: 'Gold', 80: 'Mercury', 81: 'Thallium',
                 82: 'Lead', 83: 'Bismuth', 84: 'Polonium',
                 85: 'Astatine', 86: 'Radon', 87: 'Francium',
                 88: 'Radium', 89: 'Actinium', 90: 'Thorium',
                 91: 'Protactinium', 92: 'Uranium', 93: 'Neptunium',
                 94: 'Plutonium', 95: 'Americium', 96: 'Curium',
                 97: 'Berkelium', 98: 'Californium', 99: 'Einsteinium',
                 100: 'Fermium', 101: 'Mendelevium', 102: 'Nobelium',
                 103: 'Lawrencium', 104: 'Rutherfordium', 105: 'Dubnium',
                 106: 'Seaborgium', 107: 'Bohrium', 108: 'Hassium',
                 109: 'Meitnerium', 110: 'Darmstadtium', 111: 'Roentgenium',
                 112: 'Copernicium', 113: 'Nihonium', 114: 'Flerovium',
                 115: 'Moscovium', 116: 'Livermorium', 117: 'Tennessine',
                 118: 'Oganesson'}


#from openmc reactions

def find_REACTION_NAME(incident_particle_symbol, keynumber):
    REACTION_NAME = {1: '('+incident_particle_symbol+',total)', 
                    2: '('+incident_particle_symbol+',elastic)', 
                    4: '('+incident_particle_symbol+',level)',
                    5: '('+incident_particle_symbol+',misc)', 
                    11: '('+incident_particle_symbol+',2nd)', 
                    16: '('+incident_particle_symbol+',2n)', 
                    17: '('+incident_particle_symbol+',3n)',
                    18: '('+incident_particle_symbol+',fission)', 
                    19: '('+incident_particle_symbol+',f)', 
                    20: '('+incident_particle_symbol+',nf)', 
                    21: '('+incident_particle_symbol+',2nf)',
                    22: '('+incident_particle_symbol+',na)', 
                    23: '('+incident_particle_symbol+',n3a)', 
                    24: '('+incident_particle_symbol+',2na)', 
                    25: '('+incident_particle_symbol+',3na)',
                    27: '('+incident_particle_symbol+',absorption)', 
                    28: '('+incident_particle_symbol+',np)', 
                    29: '('+incident_particle_symbol+',n2a)',
                    30: '('+incident_particle_symbol+',2n2a)', 
                    32: '('+incident_particle_symbol+',nd)', 
                    33: '('+incident_particle_symbol+',nt)', 
                    34: '('+incident_particle_symbol+',nHe-3)',
                    35: '('+incident_particle_symbol+',nd2a)', 
                    36: '('+incident_particle_symbol+',nt2a)', 
                    37: '('+incident_particle_symbol+',4n)', 
                    38: '('+incident_particle_symbol+',3nf)',
                    41: '('+incident_particle_symbol+',2np)', 
                    42: '('+incident_particle_symbol+',3np)', 
                    44: '('+incident_particle_symbol+',n2p)', 
                    45: '('+incident_particle_symbol+',npa)',
                    91: '('+incident_particle_symbol+',nc)', 
                    101: '('+incident_particle_symbol+',disappear)', 
                    102: '('+incident_particle_symbol+',gamma)',
                    103: '('+incident_particle_symbol+',p)', 
                    104: '('+incident_particle_symbol+',d)', 
                    105: '('+incident_particle_symbol+',t)', 
                    106: '('+incident_particle_symbol+',3He)',
                    107: '('+incident_particle_symbol+',a)', 
                    108: '('+incident_particle_symbol+',2a)', 
                    109: '('+incident_particle_symbol+',3a)', 
                    111: '('+incident_particle_symbol+',2p)',
                    112: '('+incident_particle_symbol+',pa)', 
                    113: '('+incident_particle_symbol+',t2a)', 
                    114: '('+incident_particle_symbol+',d2a)', 
                    115: '('+incident_particle_symbol+',pd)',
                    116: '('+incident_particle_symbol+',pt)', 
                    117: '('+incident_particle_symbol+',da)', 
                    152: '('+incident_particle_symbol+',5n)', 
                    153: '('+incident_particle_symbol+',6n)',
                    154: '('+incident_particle_symbol+',2nt)', 
                    155: '('+incident_particle_symbol+',ta)', 
                    156: '('+incident_particle_symbol+',4np)', 
                    157: '('+incident_particle_symbol+',3nd)',
                    158: '('+incident_particle_symbol+',nda)', 
                    159: '('+incident_particle_symbol+',2npa)', 
                    160: '('+incident_particle_symbol+',7n)', 
                    161: '('+incident_particle_symbol+',8n)',
                    162: '('+incident_particle_symbol+',5np)', 
                    163: '('+incident_particle_symbol+',6np)', 
                    164: '('+incident_particle_symbol+',7np)', 
                    165: '('+incident_particle_symbol+',4na)',
                    166: '('+incident_particle_symbol+',5na)', 
                    167: '('+incident_particle_symbol+',6na)', 
                    168: '('+incident_particle_symbol+',7na)', 
                    169: '('+incident_particle_symbol+',4nd)',
                    170: '('+incident_particle_symbol+',5nd)', 
                    171: '('+incident_particle_symbol+',6nd)', 
                    172: '('+incident_particle_symbol+',3nt)', 
                    173: '('+incident_particle_symbol+',4nt)',
                    174: '('+incident_particle_symbol+',5nt)', 
                    175: '('+incident_particle_symbol+',6nt)', 
                    176: '('+incident_particle_symbol+',2n3He)',
                    177: '('+incident_particle_symbol+',3n3He)', 
                    178: '('+incident_particle_symbol+',4n3He)', 
                    179: '('+incident_particle_symbol+',3n2p)',
                    180: '('+incident_particle_symbol+',3n3a)', 
                    181: '('+incident_particle_symbol+',3npa)', 
                    182: '('+incident_particle_symbol+',dt)',
                    183: '('+incident_particle_symbol+',npd)', 
                    184: '('+incident_particle_symbol+',npt)', 
                    185: '('+incident_particle_symbol+',ndt)',
                    186: '('+incident_particle_symbol+',np3He)', 
                    187: '('+incident_particle_symbol+',nd3He)', 
                    188: '('+incident_particle_symbol+',nt3He)',
                    189: '('+incident_particle_symbol+',nta)', 
                    190: '('+incident_particle_symbol+',2n2p)', 
                    191: '('+incident_particle_symbol+',p3He)',
                    192: '('+incident_particle_symbol+',d3He)', 
                    193: '('+incident_particle_symbol+',3Hea)', 
                    194: '('+incident_particle_symbol+',4n2p)',
                    195: '('+incident_particle_symbol+',4n2a)', 
                    196: '('+incident_particle_symbol+',4npa)', 
                    197: '('+incident_particle_symbol+',3p)',
                    198: '('+incident_particle_symbol+',n3p)', 
                    199: '('+incident_particle_symbol+',3n2pa)', 
                    200: '('+incident_particle_symbol+',5n2p)', 
                    444: '('+incident_particle_symbol+',damage)',
                    649: '('+incident_particle_symbol+',pc)', 
                    699: '('+incident_particle_symbol+',dc)', 
                    749: '('+incident_particle_symbol+',tc)', 
                    799: '('+incident_particle_symbol+',3Hec)',
                    849: '('+incident_particle_symbol+',ac)', 
                    891: '('+incident_particle_symbol+',2nc)'}
    REACTION_NAME.update({i: '('+incident_particle_symbol+',n{})'.format(i - 50) for i in range(50, 91)})
    REACTION_NAME.update({i: '('+incident_particle_symbol+',p{})'.format(i - 600) for i in range(600, 649)})
    REACTION_NAME.update({i: '('+incident_particle_symbol+',d{})'.format(i - 650) for i in range(650, 699)})
    REACTION_NAME.update({i: '('+incident_particle_symbol+',t{})'.format(i - 700) for i in range(700, 749)})
    REACTION_NAME.update({i: '('+incident_particle_symbol+',3He{})'.format(i - 750) for i in range(750, 799)})
    REACTION_NAME.update({i: '('+incident_particle_symbol+',a{})'.format(i - 800) for i in range(800, 849)})
    REACTION_NAME.update({i: '('+incident_particle_symbol+',2n{})'.format(i - 875) for i in range(875, 891)})

    REACTION_NAME[3]='('+incident_particle_symbol+',nonelastic)'
    REACTION_NAME[203]='('+incident_particle_symbol+',Xp)'
    REACTION_NAME[204]='('+incident_particle_symbol+',Xd)'
    REACTION_NAME[205]='('+incident_particle_symbol+',Xt)'
    REACTION_NAME[206]='('+incident_particle_symbol+',3He)'
    REACTION_NAME[207]='('+incident_particle_symbol+',Xa)'
    REACTION_NAME[301]='('+incident_particle_symbol+',heat)'
    REACTION_NAME[901]='('+incident_particle_symbol+',displacement NRT)'

    # for reaction in REACTION_NAME: 
    #     REACTION_NAME[reaction] = REACTION_NAME[reaction][3:-1]

    return REACTION_NAME[keynumber]

number_of_entries_added_to_db = 0

for file in tqdm(os.listdir(datapath)):
    if file.endswith(".h5") and file not in files_to_ignore:
        
        print('trying ',os.path.join(datapath, file))

        with h5py.File(os.path.join(datapath, file)) as h5file:
            filetype = h5file.attrs['filetype'].decode()[5:] #same method as library.py

        if filetype != 'thermal' and filetype != 'photon':

            if filetype == 'neutron':
                incident_particle_symbol = 'n'
                isotope_object = openmc.data.IncidentNeutron.from_hdf5(os.path.join(datapath, file))
            if filetype == 'photon':
                incident_particle_symbol = 'p'
                isotope_object = openmc.data.IncidentPhoton.from_hdf5(os.path.join(datapath, file))

            reactions = isotope_object.reactions

            temperatures = isotope_object.energy.keys()

            for reaction in reactions:
                temperatures = isotope_object[reaction].xs.keys()
                for temperature in temperatures:
                    energy = isotope_object.energy[temperature]
                    cross_section = isotope_object[reaction].xs[temperature](energy)

                    shorter_cross_section = np.trim_zeros(cross_section, 'f')

                    ofset = len(cross_section) - len(shorter_cross_section)

                    shorter_energy= energy[ofset:]

                    if int(isotope_object._mass_number)!=0: #this prevents natural (e.g. Carbon)

                        neutron_number = int(isotope_object._mass_number-isotope_object._atomic_number)
                        mass_number = int(isotope_object._mass_number)

                        # print('creating json object for ',isotope_object.name, 'MT',reaction, temperature)

                        uuid = '_'.join([isotope_object.atomic_symbol, str(mass_number), library, incident_particle_symbol, str(int(reaction)), str(temperature)])

                        # json_obj = {
                        #     'Mass number':mass_number,
                        #     'Proton number':int(isotope_object._atomic_number),
                        #     'Neutron number':neutron_number,
                        #     'Element':ELEMENT_NAME[int(isotope_object._atomic_number)],
                        #     'Atomic symbol':isotope_object.atomic_symbol,
                        #     'Temperature':temperature,
                        #     'Incident particle':'neutron',
                        #     'Reaction products':REACTION_NAME[int(reaction)],
                        #     'MT reaction number':int(reaction), # mt number
                        #     'Library':library,
                        #     'cross section':shorter_cross_section.tolist(),
                        #     'energy':shorter_energy.tolist(),
                        # }

                        json_obj = {
                            'Proton number / element':str(int(isotope_object._atomic_number)) +' '+isotope_object.atomic_symbol + ' '  + ELEMENT_NAME[int(isotope_object._atomic_number)],
                            'Mass number':mass_number,
                            'Neutron number':neutron_number,
                            'MT number / reaction products':str(int(reaction)) + ' ' +find_REACTION_NAME(incident_particle_symbol,int(reaction)),
                            'Library':library,
                            # 'Temperature':temperature,
                            'cross section':shorter_cross_section.tolist(),
                            'energy':shorter_energy.tolist(),
                        }                        


                        # list_of_json_objects.append(json_obj)
                        print(uuid)
                        with open(os.path.join(json_datapath,uuid+'.json'), 'w') as fout:
                            json.dump(json_obj, fout)#, indent = 4)
                        if args.commit == 'yes':
                            print('mongoimport --collection collection_one --db my_database --file '+os.path.join(json_datapath,uuid+'.json'))
                            os.system('mongoimport --collection collection_one --db my_database --file '+os.path.join(json_datapath,uuid+'.json'))
                            number_of_entries_added_to_db=number_of_entries_added_to_db+1

                    #os.system('rm '+os.path.join(datapath,'temp_json.json'))
                
        # except:
        #     print('failed ',os.path.join(datapath, file))

# save_json_objs_to_files(list_of_json_objects,datapath

# with open(os.path.join(folder,filename), 'w') as fout:
    #json.dump(list_of_data, fout, encoding='utf-8', indent = 4) #python 2
    
# os.system('mongod --bind_ip_all &')
# collection, client, db = connect_to_docker_database()
# # delete_database(client)
# # collection.insert_many(list_of_json_objects)
# # upload_json_objects_to_database(list_of_json_objects, collection)

# all_database_fields = get_database_fields(collection)

# print('all_database_fields',all_database_fields)

# entrys_in_field_1 = get_entries_in_field(collection,all_database_fields[0])

# print('entrys_in_field',all_database_fields[0], entrys_in_field_1)
# print(collection.find_one({}))
# print(list_of_xs)

        #new_xs = {'temperature'}
#             energy = isotope_object.energy['293K'] # 294K is the temperature for tendl this is 293K
#             cross_section = isotope_object[MT_number].xs['293K'](energy)

if args.commit == 'yes':
    print('number_of_entries_added_to_db', number_of_entries_added_to_db)