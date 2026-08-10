-- SmartHire2: resume metadata table (Supabase Postgres)
-- Note: this project does NOT use pgvector / Supabase for search.
-- Embeddings and similarity search live in a local ChromaDB (see app/vector_store.py).
-- This table exists only so resume metadata (who's in the system, file type,
-- when it was added) is centrally visible and survives beyond your local machine.
--
-- Safe to re-run: uses "if not exists" throughout.

create table if not exists public.resumes (
    resume_id      text primary key,          -- e.g. "RES001", matches Chroma metadata + feedback sheet
    candidate_name text not null,
    role_title     text,                       -- best-guess title from the resume, e.g. "Data Scientist"
    file_name      text not null,
    file_type      text not null check (file_type in ('pdf', 'docx', 'txt')),
    uploaded_at    timestamptz not null default now()
);

-- Row Level Security: enabled with NO public policies.
-- Only the service_role key (used exclusively by this app's backend, never a
-- browser) can read/write this table - the service_role key bypasses RLS by
-- design. The anon/public key gets zero access, which is what we want since
-- end users never query Supabase directly.
alter table public.resumes enable row level security;
