#!/bin/bash
 
# --------------------------------------------------------------------------------------
# Author: Qiuyu Yu
#  
# Description: 
# Preprocessing step by using AFNI before doing ICA.
# 
# Note:
# Currently, there is no standardized preprocessing method. In general, scale is not recommended.
# Here, `despike` is used instead of traditional fMRI data preprocessing. 
# Since AFNI generates files for each step, if you only want the blur files, 
# then find the last pb* file and convert it to a NIFTI file. 
# If you want to obtain files thant apply high-pass band or head motion parameter regression, 
# find the errt* file.
# 
# Other parameters to consider:
# -regress_apply_mot_types  demean deriv \ # Include both de-meaned and derivatives of motion parameters in the regression.
# -regress_bandpass 0.01 999 \ # highpass band filter
# 
# Usage: Use it with slurm script.
# --------------------------------------------------------------------------------------

subject="$1"
subj="${prefix}${subject}"

t1_dir="$base_dir/AFNI_derivatives/$subj/ses-01/sswarp2/T1_results"
func_dir="$base_dir/BIDS/$subj/ses-01/func"
output_dir="/scratch/qy49547/MDD/ICA/AFNI_6/$subj"

mkdir -p ${output_dir}
cd ${output_dir}

afni_proc.py \
-subj_id $subj \
-script ${output_dir}/proc."${subj}" -scr_overwrite \
-out_dir ${output_dir}/"${subj}.results" \
-copy_anat "${t1_dir}"/anatSS."${subj}".nii \
-anat_has_skull no \
-dsets "${func_dir}"/*rest*nii* \
-blocks despike tshift align tlrc volreg blur mask regress \
-radial_correlate_blocks tcat volreg regress \
-tcat_remove_first_trs 6 \
-align_unifize_epi local \
-align_opts_aea -cost lpc+ZZ -giant_move -check_flip \
-tlrc_base /work/cglab/resources/atlases/MNI152_2009_template_SSW.nii.gz \
-tlrc_NL_warp \
-tlrc_NL_warped_dsets \
	"${t1_dir}"/anatQQ."${subj}".nii \
	"${t1_dir}"/anatQQ."${subj}".aff12.1D \
	"${t1_dir}"/anatQQ."${subj}"_WARP.nii \
-volreg_align_to MIN_OUTLIER \
-volreg_align_e2a \
-volreg_tlrc_warp \
-volreg_compute_tsnr yes \
-mask_epi_anat yes \
-blur_size 6.0 \
-regress_apply_mot_types  demean deriv \
-regress_motion_per_run \
-regress_censor_motion 0.2 \
-regress_censor_outliers 0.05 \
-regress_bandpass 0.01 999 \
-regress_est_blur_epits \
-regress_est_blur_errts \
-regress_run_clustsim no \
-html_review_style pythonic \
-execute \