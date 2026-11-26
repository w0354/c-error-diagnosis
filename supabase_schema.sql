create extension if not exists pgcrypto;

create table if not exists public.records (
    id uuid primary key default gen_random_uuid(),
    owner_code text not null default 'owner',
    display_id text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    date_label text,
    chapter text,
    source text,
    compiler_error text,
    my_category text,
    ai_category text,
    knowledge text,
    redo_status text not null default '未重做',
    problem_text text,
    student_code text,
    practice_scenario text,
    practice_code text,
    practice_answer text,
    practice_correct_code text,
    correct_code text,
    explanation text,
    raw_response text,
    unique (owner_code, display_id)
);

create index if not exists records_created_at_idx
    on public.records (created_at desc);

create index if not exists records_category_idx
    on public.records (ai_category);

create index if not exists records_redo_status_idx
    on public.records (redo_status);

alter table public.records enable row level security;
