#!/usr/bin/env python3

import argparse
import glob
import os
import sys
import tarfile
from multiprocessing import Pool
import re
import shutil
#import subprocess

from libraryUQ import *

import openmc.data


description = '''
This scripts generates random (gaussian) evaluations of a nuclear data file following 
its covariance matrix using SANDY, and converts them to HDF5 for use in OpenMC. Script
generates a cross_sections.xml file with the standard library plus the sampled evaluations.
'''


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-n', '--nuclides', nargs='+',
                    default='Fe56', help="The nuclide(s) to be sampled")

parser.add_argument('-d', '--destination', default=None,
                    help='Desitination of the endf library')

parser.add_argument('-o', '--outdir', default=None,
                    help='Directory to create new library in')

parser.add_argument('-s', '--samples',  default=200,		
                     help='Number of samples per nuclide')

parser.add_argument('-p', '--processes',  default=1,		
                     help='number of worker processes (default = 1)')

parser.add_argument('-f', '--formatOnly',  default=False,		
                     help='Only format previously sampled files to hdf5')

args = parser.parse_args()
scriptDir = os.getcwd()

outdir = args.outdir
if outdir == None:
    outdir = os.path.abspath(os.getcwd() + '/' + 'sandy_rand')
else: 
    outdir = os.path.abspath(outdir)

outdirEndf = outdir + '/' + 'endf'
outdirHdf5 = outdir + '/' + 'hdf5'

libdir = args.destination
if libdir == None:
    libdir = os.getenv('NUCLEAR_DATA_DIR') + '/nndc-b7.1-endf'
else:
    libdir = os.path.abspath(libdir)

nucs = args.nuclides

# ==============================================================================
# CHECK IF REQUEST IS VALID AND IF ENDF FILES EXIST

prefix = 'n-'
suffix = '.endf'

atomicDict = openmc.data.ATOMIC_NUMBER
nucDict = {}

for nuc in nucs:
    massNum   = int(re.findall("(\d+)", nuc)[0])
    atomicSym = ''.join([i for i in nuc if not i.isdigit()])
    if atomicSym not in atomicDict.keys():
        print('Entered nuclide {} does not have a valid atomic symbol'.format(nuc))
        sys.exit()
    atomicNum = atomicDict[atomicSym]

    if massNum < 10:
        fileMass = '00' + str(massNum)
    elif massNum < 100:
        fileMass = '0' + str(massNum)

    if atomicNum < 10:
        fileAtomic = '00' + str(atomicNum)
    elif atomicNum < 100:
        fileAtomic = '0' + str(atomicNum)

    fileName = prefix + fileAtomic + '_' + atomicSym + '_' + fileMass + suffix

    if not os.path.isfile(libdir+'/'+'neutron'+'/'+fileName):
        print('File {} does not exist'.format(libdir+'/'+'neutron'+'/'+fileName))
        sys.exit()
    nucDict[nuc] = {'sym' : atomicSym, 'massNum': massNum, 'atomicNum' : atomicNum, 'fileName': fileName}

# ==============================================================================
# GENERATE RANDOM EVALUATIONS OF NUCLEAR DATA USING SANDY

if not os.path.exists(outdir):
    os.mkdir(outdir)

if not os.path.exists(outdirEndf):
    os.mkdir(outdirEndf)

for nuc in nucs:
    nucDirEndf = outdirEndf + '/' + nuc
    if not os.path.exists(nucDirEndf):
        os.mkdir(nucDirEndf)
    shutil.copyfile(libdir+'/'+'neutron'+'/'+nucDict[nuc]['fileName'], nucDirEndf  + '/'+nucDict[nuc]['fileName'])
    #os.chdir(nucDirEndf)
    #subprocess.call("cp {} .".format(libdir+'/'+nucDict[nuc]['fileName']))
    os.chdir(nucDirEndf+'/')
    sandyCommand = 'sandy {} --samples {} --outname {} --processes {}'.format(nucDict[nuc]['fileName'], args.samples, nuc, args.processes)
    #print(sandyCommand)
    os.system(sandyCommand)


# ==============================================================================
# CONVERT RANDOM EVALUATIONS TO HDF5

def process_neutron_random(nuc, i, outDir, inDir, fileNum): # Need to add temperatures
    """Process ENDF neutron sublibrary file into HDF5 and write into a
    specified output directory."""
    
    fileIn  = inDir  + '/' + nuc + '-' + str(i)
    fileOut = outDir + '/' + nuc + '-' + str(i) + '.h5'

    data = openmc.data.IncidentNeutron.from_njoy(fileIn)#, temperatures=293.6)
    data.name = nuc + '-' + str(i)
    data.export_to_hdf5(fileOut, 'w')
    if i % 40 == 0: 
        print('Nuclide ' + nuc+ ' ' + str(i+1) + '/'+str(fileNum) + ' finished')

print('Beginning njoy processing')
with Pool() as pool:
    results = []
    fileNum = int(args.samples)
    for nuc in nucs:

        inDir  = outdirEndf + '/' + nuc
        outDir = outdirHdf5 + '/' + nuc

        if not os.path.exists(outdirHdf5):
            os.mkdir(outdirHdf5)
        if not os.path.exists(outDir):
            os.mkdir(outDir)

        print('Beginning nuclide '+ nuc + ' ...')
        for i in range(1, fileNum+1):
            func_args = (nuc,i, outDir, inDir, fileNum)
            r = pool.apply_async(process_neutron_random, func_args)
            results.append(r)
        
    for r in results:
        r.wait()


# ==============================================================================
# Create xml library

lib = DataLibraryUQ()
lib = lib.from_xml(os.getenv('OPENMC_CROSS_SECTIONS'))        #Gets current

for nuc in nucs:
    outDir = outdirHdf5 + '/' + nuc
    #fileNum = int(args.samples)
    for i in range(1,fileNum+1):
        fileOut = outDir + '/' + nuc + '-' + str(i) + '.h5'
        lib.register_file(fileOut,nuc + '-' + str(i))

pre = outdir + '/cross_sections_Pre.xml'
post = outdir + '/cross_sections_Sandy.xml'

lib.export_to_xml(pre)
if os.path.exists(post):
    command = "python combine_librariesUQ.py -l {} {} -o {}".format(pre, post, post)
    os.system(command)
else:
    lib.export_to_xml(post)

os.remove(pre)