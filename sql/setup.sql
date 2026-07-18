create extension if not exists pgcrypto;


-- ============================================================
-- REGISTRATIONS TABLE
-- ============================================================

create table if not exists public.registrations (
    id uuid primary key default gen_random_uuid(),

    full_name text not null,

    registration_number text not null unique,

    study_year text not null
        check (
            study_year in (
                '2nd Year',
                '3rd Year'
            )
        ),

    email text not null unique,

    password_hash text not null,

    club text not null
        check (
            club in (
                'Computer Vision Club',
                'Web Development Club',
                'ML Club'
            )
        ),

    application_reference text not null unique,

    candidate_number text not null unique,

    task_deadline date not null,

    email_status text not null default 'Pending'
        check (
            email_status in (
                'Pending',
                'Sent',
                'Failed'
            )
        ),

    email_error text,

    email_message_id text,

    application_status text not null default 'Registered'
        check (
            application_status in (
                'Registered',
                'Proof Submitted',
                'Under Scrutiny',
                'Shortlisted',
                'Rejected',
                'Selected'
            )
        ),

    created_at timestamptz not null default now()
);


-- Add newer columns to an existing registrations table.

alter table public.registrations
add column if not exists serial_number bigint;

alter table public.registrations
add column if not exists email_error text;

alter table public.registrations
add column if not exists email_message_id text;


-- ============================================================
-- PROOF SUBMISSIONS
-- ============================================================

create table if not exists public.proof_submissions (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid not null unique
        references public.registrations(id)
        on delete cascade,

    github_url text,

    deployment_url text,

    video_url text,

    notes text,

    proof_files jsonb not null default '[]'::jsonb,

    submitted_at timestamptz not null default now()
);


-- ============================================================
-- SEQUENTIAL REGISTRATION NUMBER
-- ============================================================

create sequence if not exists
public.registration_serial_sequence
start with 1
increment by 1
minvalue 1;


alter table public.registrations
alter column serial_number
set default nextval(
    'public.registration_serial_sequence'
);


alter sequence public.registration_serial_sequence
owned by public.registrations.serial_number;


-- Assign a serial number to old registrations.

update public.registrations
set serial_number = nextval(
    'public.registration_serial_sequence'
)
where serial_number is null;


-- Continue after the current highest value.

select setval(
    'public.registration_serial_sequence',
    coalesce(
        (
            select max(serial_number)
            from public.registrations
        ),
        0
    ) + 1,
    false
);


alter table public.registrations
alter column serial_number
set not null;


create unique index if not exists
registrations_serial_number_unique_index
on public.registrations(serial_number);


-- ============================================================
-- REFERENCE NUMBER TRIGGER
-- ============================================================

create or replace function
public.assign_registration_numbers()
returns trigger
language plpgsql
as $$
declare
    club_code text;
    year_code text;
    registration_year text;
    formatted_number text;
begin
    case new.club
        when 'Computer Vision Club' then
            club_code := 'CV';

        when 'Web Development Club' then
            club_code := 'WEB';

        when 'ML Club' then
            club_code := 'ML';

        else
            raise exception
                'Unsupported club: %',
                new.club;
    end case;


    case new.study_year
        when '2nd Year' then
            year_code := 'Y2';

        when '3rd Year' then
            year_code := 'Y3';

        else
            raise exception
                'Unsupported academic year: %',
                new.study_year;
    end case;


    if new.serial_number is null then
        new.serial_number := nextval(
            'public.registration_serial_sequence'
        );
    end if;


    registration_year := to_char(
        coalesce(new.created_at, now()),
        'YYYY'
    );


    formatted_number := lpad(
        new.serial_number::text,
        5,
        '0'
    );


    new.application_reference :=
        '10X-'
        || registration_year
        || '-'
        || formatted_number;


    new.candidate_number :=
        club_code
        || '-'
        || year_code
        || '-'
        || registration_year
        || '-'
        || formatted_number;


    return new;
end;
$$;


drop trigger if exists
assign_registration_numbers_trigger
on public.registrations;


create trigger assign_registration_numbers_trigger
before insert
on public.registrations
for each row
execute function
public.assign_registration_numbers();


-- Convert old random references to meaningful sequential references.

update public.registrations
set
    application_reference =
        '10X-'
        || to_char(created_at, 'YYYY')
        || '-'
        || lpad(serial_number::text, 5, '0'),

    candidate_number =
        case club
            when 'Computer Vision Club' then 'CV'
            when 'Web Development Club' then 'WEB'
            when 'ML Club' then 'ML'
        end
        || '-'
        || case study_year
            when '2nd Year' then 'Y2'
            when '3rd Year' then 'Y3'
        end
        || '-'
        || to_char(created_at, 'YYYY')
        || '-'
        || lpad(serial_number::text, 5, '0');


-- ============================================================
-- INDEXES
-- ============================================================

create index if not exists
registrations_club_index
on public.registrations(club);

create index if not exists
registrations_year_index
on public.registrations(study_year);

create index if not exists
registrations_status_index
on public.registrations(application_status);

create index if not exists
registrations_date_index
on public.registrations(created_at desc);

create index if not exists
submissions_date_index
on public.proof_submissions(submitted_at desc);


-- ============================================================
-- RLS
-- ============================================================

alter table public.registrations
enable row level security;

alter table public.proof_submissions
enable row level security;


-- ============================================================
-- PRIVATE STORAGE BUCKETS
-- ============================================================

insert into storage.buckets (
    id,
    name,
    public
)
values (
    'task-documents',
    'task-documents',
    false
)
on conflict (id)
do update set public = false;


insert into storage.buckets (
    id,
    name,
    public
)
values (
    'proof-submissions',
    'proof-submissions',
    false
)
on conflict (id)
do update set public = false;