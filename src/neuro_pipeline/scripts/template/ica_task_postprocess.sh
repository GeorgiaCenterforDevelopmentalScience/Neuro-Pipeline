#!/bin/bash

# ---------------------------------- Setup ---------------------------------------------

subject="$1"
echo "Processing subject: $subject for ICA task postprocessing"

output_dir="$OUTPUT_DIR"
prefix="$PREFIX"
session="$SESSION"

# ---------------------------------- Run Processing -------------------------------------

subj="${prefix}${subject}"

in_dir="${output_dir}/${subj}/ses-${session}/ica_task_output/${subj}.results"
in_dset="${in_dir}/${AFNI_DSET}.${subj}+tlrc"

out_dir="${output_dir}/${subj}/ses-${session}/ica_task_output"
bold_gz="${out_dir}/${subj}_preproc.nii.gz"
bold_nii="${out_dir}/${subj}_preproc.nii"

echo "Input dataset: ${in_dset}"
echo "Output: ${bold_nii}"

# ── Step 1: AFNI → .nii.gz ───────────────────────────────────────────────────────────
if [[ ! -f "${in_dset}.HEAD" || ! -f "${in_dset}.BRIK.gz" ]]; then
    echo "[MISSING] ${in_dset}.HEAD/.BRIK.gz — exiting."
    exit 1
fi

echo "[$(date +%T)] Converting ${subj} ..."
3dAFNItoNIFTI -prefix "${bold_gz}" "${in_dset}"

if [[ ! -f "${bold_gz}" ]]; then
    echo "[ERROR] 3dAFNItoNIFTI failed"
    exit 1
fi

# ── Step 2: FSL decompress .nii.gz → .nii ───────────────────────────────────────────
echo "[$(date +%T)] Decompressing ${subj} ..."
env -u PYTHONPATH fslchfiletype NIFTI "${bold_gz}"

if [[ ! -f "${bold_nii}" ]]; then
    echo "[ERROR] fslchfiletype failed"
    exit 1
fi

echo "[OK] ${subj} → ${bold_nii}"
