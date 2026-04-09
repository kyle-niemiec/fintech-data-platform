-- Role constraints for actor attribution
ALTER TABLE public.ingestion_run
    ADD CONSTRAINT ingestion_run_actor_role_chk
    CHECK (actor_role IN ('operator', 'observer', 'pipeline'));

ALTER TABLE public.artifact
    ADD CONSTRAINT artifact_actor_role_chk
    CHECK (actor_role IN ('operator', 'observer', 'pipeline'));

ALTER TABLE public.lineage_record
    ADD CONSTRAINT lineage_record_actor_role_chk
    CHECK (actor_role IN ('operator', 'observer', 'pipeline'));

-- Ensure that the input and output artifact IDs are not the same
ALTER TABLE public.lineage_record
    ADD CONSTRAINT lineage_record_distinct_artifacts_chk
    CHECK (input_artifact_id <> output_artifact_id);
