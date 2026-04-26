#!/bin/bash

echo "Input directory: $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"

# GroupA_IDS=(
#     001 002 003
# )

# GroupB_IDS=(
#     004 005 006
# )

# CONTRASTS=("Pos-Neut" "Neg-Neut" "Pos-Neg" "PosNeg-Neut")


# MASTER_FILE="${INPUT_DIR}/sub-1128/ses-${SESSION}/kidvid/sub-1128.results/stats.sub-1128_REML+tlrc"
# ALL_IDS=("${GroupA_IDS[@]}" "${GroupB_IDS[@]}")

# for sub in "${ALL_IDS[@]}"; do
#     orig_file="${INPUT_DIR}/sub-${sub}/ses-${SESSION}/kidvid/sub-${sub}.results/stats.sub-${sub}_REML+tlrc"
#     resamp_file="${RESAMPLE_DIR}/stats.sub-${sub}_REML+tlrc"

#     if [ ! -f "${orig_file}.HEAD" ]; then 
#         echo "  [missing source, skipping]: sub-${sub}"
#         continue
#     fi
#     if [ ! -f "${resamp_file}.HEAD" ]; then
#         echo "  resampling: sub-${sub} ..."
#         3dresample -master "$MASTER_FILE" -prefix "$resamp_file" -inset "$orig_file" >/dev/null 2>&1
#     fi
# done
# echo "resampling done"

# # build_set <id_array_name> <contrast> -> sets args array and count in caller
# build_set() {
#     local -n _ids=$1
#     local contrast=$2
#     args=()
#     count=0
#     for sub in "${_ids[@]}"; do
#         f="${RESAMPLE_DIR}/stats.sub-${sub}_REML+tlrc"
#         if [ -f "${f}.HEAD" ]; then
#             args+=( "sub-${sub}" "${f}[${contrast}#0_Coef]" )
#             ((count++))
#         fi
#     done
# }

# for contrast in "${CONTRASTS[@]}"; do
#     out_file="$OUTPUT_DIR/Stats_GroupA_vs_GroupB_${contrast}.nii.gz"
#     afni_head="$OUTPUT_DIR/Stats_GroupA_vs_GroupB_${contrast}+tlrc.HEAD"

#     echo "processing: ${contrast}"

#     if [ -f "$out_file" ] && [ -f "$afni_head" ]; then
#         echo "  [skip]"
#         continue
#     fi

#     build_set GroupA_IDS "$contrast"; setA_args=("${args[@]}"); count_a=$count
#     build_set GroupB_IDS "$contrast"; setB_args=("${args[@]}"); count_b=$count

#     echo "  GroupA args: ${setA_args[@]}"
#     echo "  GroupB args: ${setB_args[@]}"

#     if [ ! -f "$out_file" ]; then
#         ( cd "$OUTPUT_DIR" || exit
#           3dttest++                                                    \
#             -prefix  "Stats_GroupA_vs_GroupB_${contrast}.nii.gz"     \
#             -AminusB                                                   \
#             -setA GroupA "${setA_args[@]}"                            \
#             -setB GroupB "${setB_args[@]}"                            \
#             -Clustsim 20
#         )
#     fi

#     if [ ! -f "$afni_head" ]; then
#         ( cd "$OUTPUT_DIR" || exit
#           3dcopy "Stats_GroupA_vs_GroupB_${contrast}.nii.gz" "Stats_GroupA_vs_GroupB_${contrast}+tlrc" >/dev/null 2>&1
#         )
#     fi

#     echo "  done (GroupA: $count_a, GroupB: $count_b)"
# done
