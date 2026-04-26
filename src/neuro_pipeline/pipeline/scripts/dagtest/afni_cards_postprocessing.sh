#!/bin/bash

echo "Input directory: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"

# BW_IDX=0
# BL_IDX=0

# IFS=' ' read -ra SUB_IDS <<< "$1"

# mkdir -p "$OUTPUT_DIR"

# TABLE_FILE="${OUTPUT_DIR}/lme_datatable.txt"
# echo -e "Subj\tcond\tInputFile" > "$TABLE_FILE"
# for sub in "${SUB_IDS[@]}"; do
#     bw_f="${INPUT_DIR}/${PREFIX}${sub}/ses-01/mid_output/${PREFIX}${sub}.results/stats.${PREFIX}${sub}_REML+tlrc[${BW_IDX}]"
#     bl_f="${INPUT_DIR}/${PREFIX}${sub}/ses-01/mid_output/${PREFIX}${sub}.results/stats.${PREFIX}${sub}_REML+tlrc[${BL_IDX}]"
#     echo -e "${PREFIX}${sub}\tBW\t${bw_f}"
#     echo -e "${PREFIX}${sub}\tBL\t${bl_f}"
# done >> "$TABLE_FILE"

# ( cd "$OUTPUT_DIR" || exit
#   3dLME -prefix cards_group_LME -jobs 8 \
#     -model 'cond' \
#     -ranEff '~1' \
#     -SS_type 3 \
#     -num_glt 3 \
#     -gltLabel 1 'BW'    -gltCode 1 'cond : 1*BW' \
#     -gltLabel 2 'BL'    -gltCode 2 'cond : 1*BL' \
#     -gltLabel 3 'BW-BL' -gltCode 3 'cond : 1*BW -1*BL' \
#     -dataTable @"$TABLE_FILE"
# )
