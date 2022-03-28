#!/bin/bash

# DESC
# Prepare and unpack data from sterialEM for Warp.
# 
# You must be in a new directory for this to work; new files will be placed there
# with the same name as the original tifs.

# ARGS
# raw_data_dir: the directory containing the raw data

#Note that the use of ${@:4} requires bash instead of sh
help () {
cat 1>&2 << EOF

Usage: warp_prepare.sh raw_data_dir

You must be in a new directory for this to work; new files will be placed there
with the same name as the original tifs.
EOF
}


if [ -z $1 ] #if $1 is zero(empty)
then
   help
   exit 1
fi

if [ "$(realpath $(pwd))" = "$(realpath $1)" ]; then
    echo "You must be in a different directory, or files will be overwritten!"
    exit 1
fi

gainref=$(find $1 -name "*.dm4")
defects=$(find $1 -name "defects*.txt")
tifs=$(find $1 -name "*.tif")

echo "Preparing gain ref and defects..."
#Making the rotated gain reference file.
dm2mrc $gainref gainref_raw.mrc;
newstack -rot -90 gainref_raw.mrc gainref.mrc;
rm gainref_raw.mrc

clip defectmap -D $defects ${tifs[1]} defects.mrc

echo "Copying mdoc files..."
for mdoc in $(find $1 -name "*.mrc.mdoc")
do
    cp $mdoc .
done


echo "Unpacking tifs..."
for i in ${tifs}
do
    clip unpack -m 0 -f tif $i $(basename ${i})
done
