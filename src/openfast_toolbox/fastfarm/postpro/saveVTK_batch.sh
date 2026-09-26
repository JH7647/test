#!/bin/bash

# ******************************************** USER INPUT ******************************************** #
jobname_suffix='tte_box'

# NetCDF specification
# highfile='box_hr36962.nc'
# lowfile='box_lr36962.nc'
# Native specification
hightag='box_hr'
lowtag='box_lr'
terrain='False'

numT=76
highboxes=()
for (( i=1; i<=numT; i++ )); do highboxes+=("HighT${i}_inflow0deg"); done
lowbox='Low'

offsetz=0  # see windtools/amr/postprocessing.py:to_vtk docstrings

# Optional inputs (requires a priori knowledge of how many boxes are there in total)
# To know amount of boxes: 
#     python ~/utilities/postprocess_amr_boxes2vtk.py -p . -f $highfile -g $highboxes
#     python ~/utilities/postprocess_amr_boxes2vtk.py -p . -f $lowfile  -g $lowbox
nNodes_low=2 # 260
nNodes_high=2 # 10  # Number of nodes per high box
ncores_low=8
ncores_high=24
# Initial and final AMR-Wind time indexes. The ftime is usually period_of_saved_boxes/temporal_res + 1.
itimeind_low=22536
ftimeind_low=24088
itimeind_high=22536
ftimeind_high=24088


# Optionals for controlling the filename output of the vtks (set them to None to disable)
# Either give t0 and dt, or vtkstartind. Not both.
use_sampling_info='True'
t0='None'
dt_low='None' #0.4
dt_high='None' #0.1
vtkstartind='None'
#t0='None'
#dt_low='None'
#dt_high='None'
#vtkstartind=10

# SLURM options
account='awaken'
jobtime='1:00:00'
extra='' ##extra='--partition=debug --qos=standby'

# **************************************************************************************************** #

# Determine if netcdf or native depending on inputs and check inputs
if [ ! -z $highfile ]; then
    echo "Reading NetCDF format"
    format='netcdf'
    if [ ! -z $hightag ]; then
        echo "Error. highfile and hightag have been specified. You cannot specify both. Stopping."
        exit 1
    fi
elif [ ! -z $hightag ]; then
    echo "Reading native format"
    format='native'
else
    echo "Error. For the high box, wither highfile (netcdf) or hightag (native) need to be specified."
    exit 1
fi
if [ ! -z $lowfile ]; then
    format='netcdf'
    if [ ! -z $lowtag ]; then
        echo "Error. lowhfile and lowtag have been specified. You cannot specify both. Stopping."
        exit 1
    fi
elif [ ! -z $lowtag ]; then
    format='native'
else
    echo "Error. For the low box, wither lowfile (netcdf) or lowtag (native) need to be specified."
    exit 1
fi

# Determine increments given number of nodes (already integers)
increment_low=$(((ftimeind_low-itimeind_low)/nNodes_low))
increment_high=$(((ftimeind_high-itimeind_high)/nNodes_high))   

# Make symlink if it doesn't exist
if ! [ -L postprocess_amr_boxes2vtk.py ]; then
    ln -s /home/rthedin/repos/openfast_toolbox/openfast_toolbox/fastfarm/postpro/postprocess_amr_boxes2vtk.py
fi

# Get the current path. This script _needs_ to be launched from the case directory of interest
path=$(pwd -P)

echo -e "Current \$path is $path"

# Launch the high-res boxes on multiple nodes
for currgroup in ${highboxes[@]}; do
    curr_ftimeind=$itimeind_high

    for ((node=1;node<=nNodes_high;node++)); do
        # Get this node's starting and end time
        curr_itimeind=$curr_ftimeind
        curr_ftimeind=$((curr_itimeind+increment_high))
        # Special case for last chunk
        if [[ "$node" == "$nNodes_high" ]]; then
           curr_ftimeind=$ftimeind_high
        fi

        jobname=${jobname_suffix}${currgroup}_node${node}_ti${curr_itimeind}_tf${curr_ftimeind}
        sbatch_call="-J $jobname -A $account -t $jobtime $extra postprocess_amr_boxes2vtk.py -p $path -g $currgroup -offsetz $offsetz -itime $curr_itimeind -ftime $curr_ftimeind -t0 $t0 -dt $dt_high -vtkstartind $vtkstartind -ncores $ncores_high --use_samplinginfo $use_sampling_info -terrain $terrain"
        if [[ "$format" == "netcdf" ]]; then
            sbatch_call+=" -f $highfile"
        else
            sbatch_call+=" -tag $hightag"
        fi
        echo -e "\nCalling sbatch $sbatch_call"
        sbatch $sbatch_call
    done
done


# Launch the low-res box on multiple nodes
curr_ftimeind=$itimeind_low
for ((node=1;node<=nNodes_low;node++)); do
    # Get this node's starting and end time
    curr_itimeind=$curr_ftimeind
    curr_ftimeind=$((curr_itimeind+increment_low))
    # Special case for last chunk
    if [[ "$node" == "$nNodes_low" ]]; then
        curr_ftimeind=$ftimeind_low
    fi

    jobname=${jobname_suffix}${lowbox}_node${node}_ti${curr_itimeind}_tf${curr_ftimeind}
    sbatch_call="-J $jobname -A $account -t $jobtime $extra postprocess_amr_boxes2vtk.py -p $path -g $lowbox -offsetz $offsetz -itime $curr_itimeind -ftime $curr_ftimeind -t0 $t0 -dt $dt_low -vtkstartind $vtkstartind -ncores $ncores_low --use_samplinginfo $use_sampling_info -terrain $terrain"
    if [[ "$format" == "netcdf" ]]; then
        sbatch_call+=" -f $lowfile"
    else
        sbatch_call+=" -tag $lowtag"
    fi
    echo -e "\nCalling sbatch $sbatch_call"
    sbatch $sbatch_call
done

