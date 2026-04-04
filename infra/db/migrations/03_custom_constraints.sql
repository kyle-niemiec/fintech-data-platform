-- Ensure that the input and output artifact IDs are not the same
CONSTRAINT lineage_record_distinct_artifacts_chk CHECK (input_artifact_id <> output_artifact_id)
