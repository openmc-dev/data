#!/bin/bash
# BASH 5.1.16 Script to Split and Format JEFF 3.3 Fission Yield Data ASC Files for OpenMC 0.13.3
# Link to Neutron Fission Yield Data File: https://www.oecd-nea.org/dbdata/jeff/jeff33/downloads/JEFF33-nfy.asc

# Set File Name
export FN=$1

# Make Folder to Contain Resulting Files
mkdir nfy

# Split File into Individual Nuclide Data Chunks using the Final Terminating Record
# Refer: https://stackoverflow.com/questions/4323703/csplit-produces-too-few-output-files-expecting-more
csplit -k $FN '/                                                                     0 0  0    0/'+1 "{*}"

# Add Leading Blank Comment to Each File Generated
# This Ensures that the OpenMC Parser Checks the Correct Line Number for the ENDF File Format
# Refer: https://unix.stackexchange.com/questions/411780/prepend-text-to-all-file-in-a-folder
for file in xx*; do
  echo -e ' $                                                                              \n'"$(cat $file)" >> $file.$$
  mv $file.$$ $file
done

# Rename Fission Yield Files According to their Content
# This uses the Nuclide Name on the 6th Line of each File
# Refer: https://stackoverflow.com/questions/83329/how-can-i-extract-a-predetermined-range-of-lines-from-a-text-file-on-unix
for file in xx*; do
  export FN_NEW=$(sed -n '6,6p;7q' $file | cut -d ' ' -f2)
  mv $file ./nfy/$FN_NEW.endf
  unset FN_NEW
done

# Cleanup Empty File and Clear Variables
rm -rf ./nfy/.endf
unset FN
