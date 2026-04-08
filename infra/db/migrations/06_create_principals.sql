-- Principal table for API authentication.
-- Stores bcrypt-hashed credentials mapped to DB roles.
-- Passwords are seeded via `make seed-principals`, not in migrations.

CREATE TABLE IF NOT EXISTS public.principal (
    principal_id uuid NOT NULL DEFAULT gen_random_uuid(),
    username text NOT NULL,
    password_hash text NOT NULL,
    role text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    PRIMARY KEY (principal_id),
    CONSTRAINT principal_username_uq UNIQUE (username)
);

CREATE INDEX IF NOT EXISTS principal_username_idx ON public.principal (username);

-- auth_reader can only SELECT from principal — nothing else
GRANT SELECT ON TABLE public.principal TO auth_reader;

-- control_plane_writer needs INSERT/UPDATE for the seed script (runs as operator DB user)
GRANT SELECT, INSERT, UPDATE ON TABLE public.principal TO control_plane_writer;
