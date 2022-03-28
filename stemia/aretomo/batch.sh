#!/bin/bash

# DESC
# Run AreTomo on a full directory.

for ts in *.st; do
    base="${ts%.mrc.st}"
    tlt="${base}.mrc.rawtlt"
    out="${base}_recon.mrc"
    AreTomo -InMrc $ts -OutMrc $out -AngFile $tlt -VolZ 1500 -OutBin 4 -TiltCor 1 -TiltAxis 86.62 -Patch 4 4 -Wbp 1 -PixSize 4.346 -Kv 300 -ImgDose 3 -Cs 0.7 -Defoc 3500 -FlipVol 1
done
