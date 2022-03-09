# STEMIA

**S**cripts and **T**ools for **E**lectron **M**icroscopy **I**mage **A**nalysis.

This is a simple personal collection of (sometimes...) useful scripts and tools for cryoem/cryoet.

## Installation

```bash
pip install stemia
```

## Tools

Everything is accessible through the main command line interface `stemia`. Try `stemia -h`.

### aretomo_align

```
Usage: stemia aretomo_align [OPTIONS] [WARP_DIR]

  run aretomo on a warp directory (after imod stacks were generated).
  Requires ccderaser and AreTomo.

  Assumes the default Warp directory structure with generated imod stacks

Options:
  -d, --dry-run               only print some info, without running the
                              commands

  -t, --tilt-axis FLOAT       starting tilt axis for AreTomo, if any
  -f, --overwrite             overwrite any previous existing run
  --fix / --nofix             run ccderaser to fix the stack
  --norm / --nonorm           use mrcfile to normalize the images
  --align / --noalign         run aretomo to produce an alignment
  --startfrom [raw|fix|norm]  use outputs from a previous run starting from
                              this step

  --ccderaser TEXT            command for ccderaser
  --aretomo TEXT              command for aretomo
  --help                      Show this message and exit.
```

### center_filament

```
Usage: stemia center_filament [OPTIONS] INPUT [OUTPUT]

  Center an mrc image containing filament(s). Can update particles in a
  RELION .star file accordingly.

  If OUTPUT is not given, default to INPUT_centered.mrc

Options:
  -s, --update-star FILE        a RELION .star file to update with new
                                particle positions

  -o, --star-output FILE        where to put the updated version of the star
                                file. Only used if -s is passed [default:
                                STARFILE_centered.star]

  --update-by [class|particle]  whether to update particle positions by
                                classes or 1 by 1. Only used if -s is passed
                                [default: class]

  -f, --overwrite               overwrite output if exists
  -n, --n-filaments INTEGER     number of filaments on the image  [default: 2]
  -p, --percentile INTEGER      percentile for binarisation  [default: 85]
  --help                        Show this message and exit.
```

### csplot

```
Usage: stemia csplot [OPTIONS] [CS_FILE]...

  read a cryosparc file (plus any number of passthrough files) into a pandas
  dataframe and provide a simple interface for plotting columns. Provided
  files must be compatible (have the same uid column!)

Options:
  --help  Show this message and exit.
```

### flip_z

```
Usage: stemia flip_z [OPTIONS] STAR_PATH

  STAR_PATH: star file to flip along z assume all micrographs have the same
  shape

Options:
  -o, --output FILE
  -m, --mrc_path FILE
  --star_pixel_size FLOAT
  --mrc_pixel_size FLOAT
  --z_shape INTEGER
  --help                   Show this message and exit.
```

### generate_tilt_angles

```
Usage: stemia generate_tilt_angles [OPTIONS] STAR_FILE TILT_ANGLE TILT_AXIS

  Read a Relion STAR_FILE with in-plane angles and generate priors for rot
  and tilt angles based on a TILT_ANGLE around a TILT_AXIS.

Options:
  -r, --radians           Provide angles in radians instead of degrees
  -o, --star-output FILE  where to put the updated version of the star file
                          [default: <STAR_FILE>_tilted.star]

  -f, --overwrite         overwrite output if exists
  --help                  Show this message and exit.
```

### rescale

```
Usage: stemia rescale [OPTIONS] INPUT OUTPUT TARGET_PIXEL_SIZE

  Rescale an mrc image to the specified pixel size.

  TARGET_PIXEL_SIZE: target pixel size in Angstrom

Options:
  --input-pixel-size FLOAT  force input pizel size and ignore mrc header
  -f, --overwrite           overwrite output if exists
  --help                    Show this message and exit.
```
