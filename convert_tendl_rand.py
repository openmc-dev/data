#!/usr/bin/env python3

import argparse
import glob
import os
import sys
import tarfile

from multiprocessing import Pool
#from libraryUQ import *

import openmc.data
from utils import download

description = '''
Download random TENDL libraries from PSI and convert it to a HDF5 library for use with OpenMC. 
Only certain nuclides are available from PSI. This script generates a cross_sections_Tendl.xml 
file with random TENDL evaluations plus a standard library located in 'OPENMC_CROSS_SECTIONS'
'''


class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter,
                      argparse.RawDescriptionHelpFormatter):
    pass


#n_choices=['all', 'O16', 'Na23', 'Si28', 'Si29','Si30', 'Fe054', 'Fe056', 'Fe057', 'Fe058', 'Ge','Pu240',]
n_choices=['all', 'O16','Si28', 'Si29','Si30', 'Fe54', 'Fe56', 'Fe57', 'Fe58']

parser = argparse.ArgumentParser(
    description=description,
    formatter_class=CustomFormatter
)
parser.add_argument('-n', '--nuclides', choices=n_choices, nargs='+',
                    default='all', help="The nuclides to be downloaded. Available are: "
                    "'O16','Si28', 'Si29','Si30', 'Fe54', 'Fe56', 'Fe57', 'Fe58'. Use 'all' for all availiable")

parser.add_argument('-d', '--destination', default=None,
                    help='Directory to create new library in')

parser.add_argument('-b', '--batch', action='store_true',		
                     help='supresses standard in')

parser.add_argument('-p', '--par',  default=1,		
                     help='supresses standard in')


args = parser.parse_args()

# All availible online files from psi
    # Name                                                      Size    Num
#https://tendl.web.psi.ch/tendl_2017/tar_files/O016.random.tgz  60MB    641     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Na23.random.tgz  130MB   831     
#https://tendl.web.psi.ch/tendl_2017/tar_files/Si28.random.tgz  110MB   500     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Si29.random.tgz  100MB   500     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Si30.random.tgz  80MB    500     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Fe054.random.tgz 320MB   500     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Fe056.random.tgz 410MB   613     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Fe057.random.tgz 525MB   732     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Fe058.random.tgz 280MB   500     x
#https://tendl.web.psi.ch/tendl_2017/tar_files/Ge.random.tgz    1.3GB   ?   
#https://tendl.web.psi.ch/tendl_2017/tar_files/Pu240.random.tgz 200MB   624 
#https://tendl.web.psi.ch/tendl_2015/tar_files/Al27.random.tgz  150MB   300     
#https://tendl.web.psi.ch/tendl_2015/tar_files/Si28.random.tgz  125MB   ...     x
#https://tendl.web.psi.ch/tendl_2015/tar_files/Ti48.random.tgz  140MB    ↓
#https://tendl.web.psi.ch/tendl_2015/tar_files/Ni58.random.tgz  210MB           x
#https://tendl.web.psi.ch/tendl_2015/tar_files/Cu63.random.tgz  205MB           
#https://tendl.web.psi.ch/tendl_2015/tar_files/Cu65.random.tgz  180MB
#https://tendl.web.psi.ch/tendl_2015/tar_files/Zr90.random.tgz  150MB
#https://tendl.web.psi.ch/tendl_2015/tar_files/Zr91.random.tgz  175MB
#https://tendl.web.psi.ch/tendl_2015/tar_files/Zr92.random.tgz  170MB
#https://tendl.web.psi.ch/tendl_2015/tar_files/W180.random.tgz  210MB
#https://tendl.web.psi.ch/tendl_2015/tar_files/W182.random.tgz  215MB
#https://tendl.web.psi.ch/tendl_2015/tar_files/W183.random.tgz  215MB
#https://tendl.web.psi.ch/tendl_2015/tar_files/W184.random.tgz  250MB   ...
#https://tendl.web.psi.ch/tendl_2015/tar_files/W186.random.tgz  180MB   300

#RandomAce

#https://tendl.web.psi.ch/tendl_2015/tar_files/H1.nuss.05.10.2016.tgz   11MB    340
#https://tendl.web.psi.ch/tendl_2015/tar_files/O16.nuss.05.10.2016.tgz  570MB   340
#https://tendl.web.psi.ch/tendl_2015/tar_files/U235.nuss.10.10.2016.tgz 430MB   100
#https://tendl.web.psi.ch/tendl_2015/tar_files/U238.nuss.10.10.2016.tgz 1.5GB   100

#ParsedNuclides._get_args('nuclides')

if( 'all' in args.nuclides):
    list_= ['O16','Si28', 'Si29','Si30', 'Fe54', 'Fe56', 'Fe57', 'Fe58']
else:
    list_ = args.nuclides
scriptDir = os.getcwd()

library_name = 'tendl_rand' #this could be added as an argument to allow different libraries to be downloaded


# the destination is decided after the release is know to avoid putting the release in a folder with a misleading name
if args.destination is None:
    outputDir = os.path.abspath(os.getcwd() + '/' + library_name)
else:
    outputDir = os.path.abspath(args.destination)


endf_files_dir  = '/'.join([outputDir, 'endf'])
ace_files_dir   = '/'.join([outputDir, 'ace'])
hdf5_files_dir  = '/'.join([outputDir, 'hdf5'])

release_details = {
    'ENDF2017' : {
        'base_url': 'https://tendl.web.psi.ch/tendl_2017/tar_files/',
        'ending' : '.random.tgz',

    },
    'ENDF2015' : {
        'base_url': 'https://tendl.web.psi.ch/tendl_2015/tar_files/',
        'ending' : '.random.tgz',
    },
    'ACE2015' : {
        'base_url': 'https://tendl.web.psi.ch/tendl_2015/tar_files/',
        'ending' : '.10.2016.tgz',
    }
}

nuclide_details = {
    'O16' : {
        'release'  : 'ENDF2017',
        'filename' : 'O016',
        'webname'  : 'O016',
        'fileNum'  : 642,
        'downSize' : 60,
        'fileSize' : 244,
        'isItENDF' : True,
        'gunzip'   : False
    },
    'Si28' : {        
        'release'  : 'ENDF2017',
        'filename' : 'Si028',
        'webname'  : 'Si28',
        'fileNum'  : 600,
        'downSize' : 110,
        'fileSize' : 428,
        'isItENDF' : True,
        'gunzip'   : True
    },
    'Si29' : {
        'release'  : 'ENDF2017',
        'filename' : 'Si029',
        'webname'  : 'Si29',
        'fileNum'  : 600,
        'downSize' : 100,
        'fileSize' : 425,
        'isItENDF' : True,
        'gunzip'   : True
    },
    'Si30' : {
        'release'  : 'ENDF2017',
        'filename' : 'Si030',
        'webname'  : 'Si30',
        'fileNum'  : 600,
        'downSize' : 80,
        'fileSize' : 337,
        'isItENDF' : True,
        'gunzip'   : True
    },
    'Fe54' : {
        'release'  : 'ENDF2017',
        'filename' : 'Fe054',
        'webname'  : 'Fe054',
        'fileNum'  : 501,
        'downSize' : 320,
        'fileSize' : 1300,
        'isItENDF' : True,
        'gunzip'   : False
    },
    'Fe56' : {
        'release'  : 'ENDF2017',
        'filename' : 'Fe056',
        'webname'  : 'Fe056',
        'fileNum'  : 614,
        'downSize' : 410,
        'fileSize' : 1600,
        'isItENDF' : True,
        'gunzip'   : False
    }, 
    'Fe57' : {
        'release'  : 'ENDF2017',
        'filename' : 'Fe057',
        'webname'  : 'Fe057',
        'fileNum'  : 733,
        'downSize' : 525,
        'fileSize' : 2000,
        'isItENDF' : True,
        'gunzip'   : False
    }, 
    'Fe58' : {
        'release'  : 'ENDF2017',
        'filename' : 'Fe058',
        'webname'  : 'Fe058',
        'fileNum'  : 501,
        'downSize' : 280,
        'fileSize' : 1100,
        'isItENDF' : True,
        'gunzip'   : False
    }
}

downloadFileSize = 0
uncompressedFileSize = 0
NumOfFiles = 0

for i in list_:
    downloadFileSize += nuclide_details[i]['downSize']
    uncompressedFileSize += nuclide_details[i]['fileSize']
    NumOfFiles += nuclide_details[i]['fileNum']

downloadSize = '{} MB'.format(downloadFileSize)
uncomFileSize = '{} MB'.format(uncompressedFileSize)
if (downloadFileSize > 1000): downloadSize = '{} GB'.format(downloadFileSize/1000)
if (uncompressedFileSize > 1000): uncomFileSize = '{} GB'.format(uncompressedFileSize/1000)

    

download_warning = """
WARNING: This script will download {} of 
data, which is {} of data when processed. 
This corresponds to {} random crossections.

The nuclides to be processed are: 
{}

Are you sure you want to continue? ([y]/n)
""".format(downloadSize, uncomFileSize,
          NumOfFiles, list_)


response = input(download_warning) if not args.batch else 'y'
if response.lower().startswith('n'):
    sys.exit()

# ==============================================================================
# DOWNLOAD FILES FROM WEBSITE

files_complete = []
for nucs in list_:
    # Establish connection to URL
    url = release_details[nuclide_details[nucs]['release']]['base_url'] + nuclide_details[nucs]['webname'] + release_details[nuclide_details[nucs]['release']]['ending']
    print("Downloading {}...".format(nucs))
    downloaded_file = download(url)
    #print(url)
    #files_complete.append(downloaded_file)

# ==============================================================================
# EXTRACT FILES FROM TGZ

for nucs in list_:
    f = nuclide_details[nucs]['webname'] + '.random.tgz'
    suffix = nucs
    isItENDF = nuclide_details[nucs]['isItENDF']
    if isItENDF:
        outDir = endf_files_dir
    else:
        outDir = ace_files_dir
    
    with tarfile.open(f, 'r') as tgz:
        print('Extracting {0}...'.format(f))
        tgz.extractall(path=os.path.join(outDir, suffix))
        
# ==============================================================================
# Format file names 

for nucs in list_:
    f = nuclide_details[nucs]['webname'] + '.random.tgz'
    isItENDF = nuclide_details[nucs]['isItENDF']
    numFiles = nuclide_details[nucs]['fileNum']
    if isItENDF:
        outDir = os.path.join(endf_files_dir, nucs)
        prefix = 'n-'
        suffix = '-rand-'
        for i in range(0,numFiles):
            if i < 10:
                OldNumber = '000' + str(i)
            elif i < 100:
                OldNumber = '00' + str(i)
            elif i < 1000:
                OldNumber = '0' + str(i)

            OldFile = prefix + nuclide_details[nucs]['filename']+suffix+OldNumber
            newFile = nucs + '-' + str(i+1)
            if nuclide_details[nucs]['gunzip']:
                os.system('gunzip ' + os.path.join(outDir, OldFile) + '.gz')
            os.rename(os.path.join(outDir, OldFile),os.path.join(outDir, newFile))
    os.remove(f)

# ==============================================================================
# Convert ENDF files to HDF5 with njoy


def process_neutron_random(nuc, i, outDir, inDir, fileNum):
    """Process ENDF neutron sublibrary file into HDF5 and write into a
    specified output directory."""
    
    fileIn  = inDir  + '/' + nuc + '-' + str(i)
    fileOut = outDir + '/' + nuc + '-' + str(i) + '.h5'

    data = openmc.data.IncidentNeutron.from_njoy(fileIn)#, temperatures=293.6)
    data.name = nuc + '-' + str(i)
    data.export_to_hdf5(fileOut, 'w')
    if i % 40 == 0: 
        print('Nuclide ' + nuc+ ' ' + str(i) + '/'+str(fileNum) + ' finished')



print('Beginning njoy processing')
with Pool() as pool:
    results = []
    for nuc in list_:

        fileNum = nuclide_details[nuc]['fileNum']
        inDir  = endf_files_dir + '/' + nuc
        outDir = hdf5_files_dir + '/' + nuc

        if not os.path.exists(hdf5_files_dir):
            os.mkdir(hdf5_files_dir)
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


'''
lib = DataLibraryUQ()
lib = lib.from_xml(os.getenv('OPENMC_CROSS_SECTIONS'))        #Gets current

for nuc in list_:
    fileNum = nuclide_details[nuc]['fileNum']
    outDir = hdf5_files_dir + '/' + nuc
    for i in range(1,fileNum+1):
        fileOut = outDir + '/' + nuc + '-' + str(i) + '.h5'
        lib.register_file(fileOut,nuc + '-' + str(i))


pre = outputDir + '/cross_sections_PreT.xml'
post = outputDir + '/cross_sections_Tendl.xml'

lib.export_to_xml(pre)
if os.path.exists(post):
    command = "{}/combine_librariesUQ.py -l {} {} -o {}".format(scriptDir,pre, post, post)       # Error could not find ccombine_libs.py
    os.system(command)
else:
    lib.export_to_xml(post)

os.remove(pre)
'''