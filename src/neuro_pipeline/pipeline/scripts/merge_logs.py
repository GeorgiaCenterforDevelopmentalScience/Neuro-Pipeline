# import sys
# import os
# from pathlib import Path

# # Get parameters from environment
# work_dir = os.environ.get('WORK_DIR')
# db_path = os.environ.get('DB_PATH')
# job_ids_str = os.environ.get('JOB_IDS', '')

# if not work_dir or not db_path:
#     print("Error: WORK_DIR or DB_PATH not set", file=sys.stderr)
#     sys.exit(1)

# print(f"Work dir: {work_dir}")
# print(f"Database: {db_path}")

# # Parse job_ids
# job_ids = [j.strip() for j in job_ids_str.split(',') if j.strip()]
# if job_ids:
#     print(f"Target job IDs: {len(job_ids)} jobs")
# else:
#     print("No job IDs specified, will process all JSON files")

# # Add package root to path
# script_dir = Path(__file__).resolve().parent  # scripts/
# pipeline_dir = script_dir.parent              # pipeline/
# package_root = pipeline_dir.parent.parent     # neuro_pipeline_db/src/
# sys.path.insert(0, str(package_root))

# # Import after path setup
# from neuro_pipeline.pipeline.utils.merge_logs_create_db import merge_json_to_db

# # JSON files location
# json_base_dir = os.path.dirname(db_path)
# json_dir = os.path.join(json_base_dir, 'json')

# if not os.path.exists(json_dir):
#     print(f"Warning: JSON directory not found: {json_dir}")
#     print("No logs to merge")
#     sys.exit(0)

# print(f"JSON directory: {json_dir}")

# # Perform merge with job_ids filter
# try:
#     count = merge_json_to_db(json_dir, db_path, job_ids=job_ids if job_ids else None)
#     print(f"Merge completed: {count} files processed")
# except Exception as e:
#     print(f"Error during merge: {e}", file=sys.stderr)
#     import traceback
#     traceback.print_exc()
#     sys.exit(1)