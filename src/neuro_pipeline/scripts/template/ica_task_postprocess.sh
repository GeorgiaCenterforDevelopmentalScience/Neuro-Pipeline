#!/bin/bash


# ── Paths ────────────────────────────────────────────────────
base_in="/work/cglab/projects/BRANCH/all_data/for_AFNI/BIDS/branch/AFNI_derivatives"

base_out="/scratch/qy49547/branch_ICA/data/B"

mkdir -p "${base_out}"


subjects=(
	070 104 107 110 111 128 182 184 189 192 195 
	211 215 244 246 248 249 253 256 266 273
)


# ── Main loop ────────────────────────────────────────────────
for subj in "${subjects[@]}"; do
    in_dir="${base_in}/sub-${subj}/ses-01/kidvid_output/sub-${subj}.results"
    in_dset="${in_dir}/pb03.sub-${subj}.r01.blur+tlrc"

    out_dir="${base_out}/sub-${subj}"
    bold_gz="${out_dir}/sub-${subj}_preproc.nii.gz"   # AFNI intermediate
    bold_nii="${out_dir}/sub-${subj}_preproc.nii"     # final output

    mkdir -p "${out_dir}"

    # ── Step 1: AFNI → .nii.gz ───────────────────────────────
    if [[ ! -f "${in_dset}.HEAD" || ! -f "${in_dset}.BRIK.gz" ]]; then
        echo "[MISSING] sub-${subj}: ${in_dset}.HEAD/.BRIK.gz — skipping."
        continue
    fi

    echo "[$(date +%T)] Converting sub-${subj} ..."
    3dAFNItoNIFTI -prefix "${bold_gz}" "${in_dset}"

    if [[ ! -f "${bold_gz}" ]]; then
        echo "[ERROR]   sub-${subj}: 3dAFNItoNIFTI failed — skipping."
        continue
    fi

# ── Step 2: FSL decompress .nii.gz → .nii ────────────────
    echo "[$(date +%T)] Decompressing sub-${subj} ..."
    env -u PYTHONPATH fslchfiletype NIFTI "${bold_gz}"
    # fslchfiletype NIFTI "${bold_gz}" "${bold_nii}"

    if [[ ! -f "${bold_nii}" ]]; then
        echo "[ERROR]   sub-${subj}: fslchfiletype failed — skipping."
        continue
    fi

    echo "[OK]      sub-${subj} → ${bold_nii}"
done

echo "Done."