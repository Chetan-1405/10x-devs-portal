-- ============================================================
-- 10X DEVS PORTAL VERSION 2 DATABASE UPGRADE
-- ============================================================
-- This migration extends the existing portal.
-- It does not delete existing registrations or submissions.
--
-- Run this complete file once in:
-- Supabase Dashboard -> SQL Editor
-- ============================================================


begin;


-- ============================================================
-- EXTENSIONS
-- ============================================================

create extension if not exists pgcrypto;


-- ============================================================
-- SHARED UPDATED-AT FUNCTION
-- ============================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;


-- ============================================================
-- EXISTING REGISTRATIONS TABLE UPGRADES
-- ============================================================

alter table public.registrations
    add column if not exists mobile_number text,
    add column if not exists profile_updated_at timestamptz,
    add column if not exists last_login_at timestamptz,
    add column if not exists is_active boolean not null default true,
    add column if not exists preferred_contact_mode text
        not null default 'Email',
    add column if not exists deadline_extended boolean
        not null default false,
    add column if not exists deadline_extension_reason text,
    add column if not exists deadline_extended_at timestamptz,
    add column if not exists deadline_extended_by text,
    add column if not exists submission_reopened boolean
        not null default false,
    add column if not exists submission_reopened_at timestamptz,
    add column if not exists submission_reopened_by text,
    add column if not exists submission_reopened_reason text,
    add column if not exists onboarding_status text
        not null default 'Not Started',
    add column if not exists interview_status text
        not null default 'Not Scheduled';


-- Existing rows may not have a mobile number.
-- New registrations will require it in the application code.

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'registrations_mobile_number_format_check'
          and conrelid = 'public.registrations'::regclass
    ) then
        alter table public.registrations
            add constraint registrations_mobile_number_format_check
            check (
                mobile_number is null
                or mobile_number ~ '^\+?[0-9]{10,15}$'
            );
    end if;
end
$$;


do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'registrations_preferred_contact_mode_check'
          and conrelid = 'public.registrations'::regclass
    ) then
        alter table public.registrations
            add constraint registrations_preferred_contact_mode_check
            check (
                preferred_contact_mode in (
                    'Email',
                    'Mobile',
                    'Both'
                )
            );
    end if;
end
$$;


do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'registrations_onboarding_status_check'
          and conrelid = 'public.registrations'::regclass
    ) then
        alter table public.registrations
            add constraint registrations_onboarding_status_check
            check (
                onboarding_status in (
                    'Not Started',
                    'Invited',
                    'Confirmed',
                    'Completed',
                    'Absent'
                )
            );
    end if;
end
$$;


do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'registrations_interview_status_check'
          and conrelid = 'public.registrations'::regclass
    ) then
        alter table public.registrations
            add constraint registrations_interview_status_check
            check (
                interview_status in (
                    'Not Scheduled',
                    'Scheduled',
                    'Completed',
                    'Cancelled',
                    'Rescheduled'
                )
            );
    end if;
end
$$;


create index if not exists registrations_mobile_number_idx
    on public.registrations (mobile_number);

create index if not exists registrations_active_idx
    on public.registrations (is_active);

create index if not exists registrations_deadline_idx
    on public.registrations (task_deadline);

create index if not exists registrations_status_club_year_idx
    on public.registrations (
        application_status,
        club,
        study_year
    );


-- ============================================================
-- EXISTING PROOF SUBMISSIONS TABLE UPGRADES
-- ============================================================

alter table public.proof_submissions
    add column if not exists submission_state text
        not null default 'Draft',
    add column if not exists draft_saved_at timestamptz,
    add column if not exists final_submitted_at timestamptz,
    add column if not exists last_edited_at timestamptz,
    add column if not exists evaluation_progress text
        not null default 'Not Reviewed',
    add column if not exists admin_private_notes text,
    add column if not exists evaluator_id uuid,
    add column if not exists reopened_at timestamptz,
    add column if not exists reopened_by text,
    add column if not exists reopened_reason text,
    add column if not exists receipt_number text,
    add column if not exists receipt_storage_path text,
    add column if not exists duplicate_source_warning boolean
        not null default false,
    add column if not exists updated_at timestamptz
        not null default now();


-- Treat old completed submissions as final.

update public.proof_submissions
set
    submission_state = 'Final',
    final_submitted_at = coalesce(
        final_submitted_at,
        submitted_at,
        now()
    ),
    draft_saved_at = coalesce(
        draft_saved_at,
        submitted_at,
        now()
    ),
    last_edited_at = coalesce(
        last_edited_at,
        submitted_at,
        now()
    )
where submitted_at is not null
  and submission_state = 'Draft';


do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'proof_submissions_submission_state_check'
          and conrelid = 'public.proof_submissions'::regclass
    ) then
        alter table public.proof_submissions
            add constraint proof_submissions_submission_state_check
            check (
                submission_state in (
                    'Draft',
                    'Final',
                    'Reopened'
                )
            );
    end if;
end
$$;


do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'proof_submissions_evaluation_progress_check'
          and conrelid = 'public.proof_submissions'::regclass
    ) then
        alter table public.proof_submissions
            add constraint proof_submissions_evaluation_progress_check
            check (
                evaluation_progress in (
                    'Not Reviewed',
                    'In Review',
                    'Completed'
                )
            );
    end if;
end
$$;


create unique index if not exists proof_submissions_receipt_number_uidx
    on public.proof_submissions (receipt_number)
    where receipt_number is not null;

create index if not exists proof_submissions_state_idx
    on public.proof_submissions (submission_state);

create index if not exists proof_submissions_evaluation_progress_idx
    on public.proof_submissions (evaluation_progress);


drop trigger if exists proof_submissions_set_updated_at
    on public.proof_submissions;

create trigger proof_submissions_set_updated_at
before update on public.proof_submissions
for each row
execute function public.set_updated_at();


-- ============================================================
-- PASSWORD RESET OTP TABLE
-- ============================================================

create table if not exists public.password_reset_otps (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid not null
        references public.registrations(id)
        on delete cascade,

    otp_hash text not null,

    expires_at timestamptz not null,

    attempt_count integer not null default 0,

    maximum_attempts integer not null default 5,

    is_used boolean not null default false,

    used_at timestamptz,

    created_at timestamptz not null default now(),

    constraint password_reset_attempt_count_check
        check (attempt_count >= 0),

    constraint password_reset_maximum_attempts_check
        check (maximum_attempts between 1 and 10)
);


create index if not exists password_reset_otps_registration_idx
    on public.password_reset_otps (
        registration_id,
        created_at desc
    );

create index if not exists password_reset_otps_expiry_idx
    on public.password_reset_otps (expires_at);

create index if not exists password_reset_otps_active_idx
    on public.password_reset_otps (
        registration_id,
        is_used,
        expires_at
    );


-- ============================================================
-- ANNOUNCEMENTS
-- ============================================================

create table if not exists public.announcements (
    id uuid primary key default gen_random_uuid(),

    title text not null,

    body text not null,

    priority text not null default 'Normal',

    target_audience text not null default 'All',

    target_year text,

    target_club text,

    is_published boolean not null default false,

    send_email boolean not null default false,

    published_at timestamptz,

    expires_at timestamptz,

    created_by text not null default 'Admin',

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint announcements_priority_check
        check (
            priority in (
                'Normal',
                'Important',
                'Urgent'
            )
        ),

    constraint announcements_audience_check
        check (
            target_audience in (
                'All',
                'Year',
                'Club',
                'Year and Club',
                'Selected Students',
                'Shortlisted Students'
            )
        ),

    constraint announcements_year_check
        check (
            target_year is null
            or target_year in (
                '2nd Year',
                '3rd Year'
            )
        ),

    constraint announcements_club_check
        check (
            target_club is null
            or target_club in (
                'Computer Vision Club',
                'Web Development Club',
                'ML Club'
            )
        )
);


create index if not exists announcements_published_idx
    on public.announcements (
        is_published,
        published_at desc
    );

create index if not exists announcements_expiry_idx
    on public.announcements (expires_at);


drop trigger if exists announcements_set_updated_at
    on public.announcements;

create trigger announcements_set_updated_at
before update on public.announcements
for each row
execute function public.set_updated_at();


-- ============================================================
-- ANNOUNCEMENT EMAIL DELIVERY LOG
-- ============================================================

create table if not exists public.announcement_email_logs (
    id uuid primary key default gen_random_uuid(),

    announcement_id uuid not null
        references public.announcements(id)
        on delete cascade,

    registration_id uuid not null
        references public.registrations(id)
        on delete cascade,

    delivery_status text not null default 'Pending',

    message_id text,

    error_message text,

    sent_at timestamptz,

    created_at timestamptz not null default now(),

    constraint announcement_email_status_check
        check (
            delivery_status in (
                'Pending',
                'Sent',
                'Failed'
            )
        ),

    constraint announcement_email_unique
        unique (
            announcement_id,
            registration_id
        )
);


create index if not exists announcement_email_logs_status_idx
    on public.announcement_email_logs (
        delivery_status,
        created_at
    );


-- ============================================================
-- CLUB PROJECT SHOWCASE
-- ============================================================

create table if not exists public.club_projects (
    id uuid primary key default gen_random_uuid(),

    club text not null,

    title text not null,

    short_description text not null,

    detailed_description text,

    technologies text[] not null default array[]::text[],

    student_names text[] not null default array[]::text[],

    academic_year text,

    github_url text,

    live_url text,

    demo_url text,

    thumbnail_storage_path text,

    project_status text not null default 'Draft',

    featured boolean not null default false,

    display_order integer not null default 0,

    created_by text not null default 'Admin',

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint club_projects_club_check
        check (
            club in (
                'Computer Vision Club',
                'Web Development Club',
                'ML Club'
            )
        ),

    constraint club_projects_status_check
        check (
            project_status in (
                'Draft',
                'Published',
                'Archived'
            )
        ),

    constraint club_projects_display_order_check
        check (display_order >= 0)
);


create index if not exists club_projects_club_status_idx
    on public.club_projects (
        club,
        project_status,
        featured desc,
        display_order
    );

create index if not exists club_projects_featured_idx
    on public.club_projects (
        featured,
        project_status
    );


drop trigger if exists club_projects_set_updated_at
    on public.club_projects;

create trigger club_projects_set_updated_at
before update on public.club_projects
for each row
execute function public.set_updated_at();


-- ============================================================
-- EVALUATOR ACCOUNTS
-- ============================================================

create table if not exists public.evaluator_accounts (
    id uuid primary key default gen_random_uuid(),

    full_name text not null,

    username text not null unique,

    email text not null unique,

    password_hash text not null,

    assigned_clubs text[] not null default array[]::text[],

    permissions jsonb not null default
        '{
            "view_submissions": true,
            "evaluate_submissions": true,
            "change_application_status": false,
            "send_emails": false,
            "manage_students": false
        }'::jsonb,

    is_active boolean not null default true,

    created_by text not null default 'Admin',

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    last_login_at timestamptz
);


create index if not exists evaluator_accounts_active_idx
    on public.evaluator_accounts (is_active);

create index if not exists evaluator_accounts_email_idx
    on public.evaluator_accounts (email);


drop trigger if exists evaluator_accounts_set_updated_at
    on public.evaluator_accounts;

create trigger evaluator_accounts_set_updated_at
before update on public.evaluator_accounts
for each row
execute function public.set_updated_at();


-- Add the evaluator foreign key after the evaluator table exists.

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'proof_submissions_evaluator_id_fkey'
          and conrelid = 'public.proof_submissions'::regclass
    ) then
        alter table public.proof_submissions
            add constraint proof_submissions_evaluator_id_fkey
            foreign key (evaluator_id)
            references public.evaluator_accounts(id)
            on delete set null;
    end if;
end
$$;


-- ============================================================
-- INTERVIEW SCHEDULING
-- ============================================================

create table if not exists public.interview_schedules (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid not null unique
        references public.registrations(id)
        on delete cascade,

    scheduled_at timestamptz not null,

    duration_minutes integer not null default 20,

    interview_mode text not null default 'Online',

    venue_or_link text,

    instructions text,

    interview_status text not null default 'Scheduled',

    scheduled_by text not null default 'Admin',

    email_status text not null default 'Not Sent',

    email_message_id text,

    email_error text,

    email_sent_at timestamptz,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint interview_duration_check
        check (
            duration_minutes between 5 and 240
        ),

    constraint interview_mode_check
        check (
            interview_mode in (
                'Online',
                'Offline',
                'Hybrid'
            )
        ),

    constraint interview_schedule_status_check
        check (
            interview_status in (
                'Scheduled',
                'Completed',
                'Cancelled',
                'Rescheduled'
            )
        ),

    constraint interview_email_status_check
        check (
            email_status in (
                'Not Sent',
                'Sent',
                'Failed'
            )
        )
);


create index if not exists interview_schedules_datetime_idx
    on public.interview_schedules (scheduled_at);

create index if not exists interview_schedules_status_idx
    on public.interview_schedules (interview_status);


drop trigger if exists interview_schedules_set_updated_at
    on public.interview_schedules;

create trigger interview_schedules_set_updated_at
before update on public.interview_schedules
for each row
execute function public.set_updated_at();


-- ============================================================
-- ONBOARDING ATTENDANCE
-- ============================================================

create table if not exists public.onboarding_attendance (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid not null unique
        references public.registrations(id)
        on delete cascade,

    attendance_status text not null default 'Pending',

    invitation_sent_at timestamptz,

    student_response_at timestamptz,

    checked_in_at timestamptz,

    notes text,

    updated_by text,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint onboarding_attendance_status_check
        check (
            attendance_status in (
                'Pending',
                'Invited',
                'Confirmed',
                'Attended',
                'Absent'
            )
        )
);


create index if not exists onboarding_attendance_status_idx
    on public.onboarding_attendance (attendance_status);


drop trigger if exists onboarding_attendance_set_updated_at
    on public.onboarding_attendance;

create trigger onboarding_attendance_set_updated_at
before update on public.onboarding_attendance
for each row
execute function public.set_updated_at();


-- ============================================================
-- APPLICATION TIMELINE
-- ============================================================

create table if not exists public.application_timeline (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid not null
        references public.registrations(id)
        on delete cascade,

    event_type text not null,

    title text not null,

    description text,

    visible_to_student boolean not null default true,

    created_by text not null default 'System',

    created_at timestamptz not null default now()
);


create index if not exists application_timeline_registration_idx
    on public.application_timeline (
        registration_id,
        created_at desc
    );

create index if not exists application_timeline_visibility_idx
    on public.application_timeline (
        visible_to_student,
        created_at desc
    );


-- Add an initial timeline event for existing students.

insert into public.application_timeline (
    registration_id,
    event_type,
    title,
    description,
    visible_to_student,
    created_by,
    created_at
)
select
    registrations.id,
    'Registration',
    'Registration completed',
    'Your 10x Devs registration was completed successfully.',
    true,
    'System',
    coalesce(registrations.created_at, now())
from public.registrations
where not exists (
    select 1
    from public.application_timeline
    where application_timeline.registration_id = registrations.id
      and application_timeline.event_type = 'Registration'
);


-- ============================================================
-- SUPPORT REQUESTS
-- ============================================================

create table if not exists public.support_requests (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid
        references public.registrations(id)
        on delete set null,

    full_name text not null,

    email text not null,

    mobile_number text,

    subject text not null,

    message text not null,

    request_status text not null default 'Open',

    admin_response text,

    assigned_to text,

    resolved_at timestamptz,

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now(),

    constraint support_request_status_check
        check (
            request_status in (
                'Open',
                'In Progress',
                'Resolved',
                'Closed'
            )
        ),

    constraint support_mobile_format_check
        check (
            mobile_number is null
            or mobile_number ~ '^\+?[0-9]{10,15}$'
        )
);


create index if not exists support_requests_status_idx
    on public.support_requests (
        request_status,
        created_at desc
    );

create index if not exists support_requests_registration_idx
    on public.support_requests (registration_id);


drop trigger if exists support_requests_set_updated_at
    on public.support_requests;

create trigger support_requests_set_updated_at
before update on public.support_requests
for each row
execute function public.set_updated_at();


-- ============================================================
-- ADMIN ACTIVITY LOG
-- ============================================================

create table if not exists public.activity_logs (
    id uuid primary key default gen_random_uuid(),

    actor_type text not null,

    actor_identifier text not null,

    action text not null,

    entity_type text not null,

    entity_id text,

    description text,

    details jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    constraint activity_actor_type_check
        check (
            actor_type in (
                'Admin',
                'Evaluator',
                'Student',
                'System'
            )
        )
);


create index if not exists activity_logs_created_idx
    on public.activity_logs (created_at desc);

create index if not exists activity_logs_actor_idx
    on public.activity_logs (
        actor_type,
        actor_identifier,
        created_at desc
    );

create index if not exists activity_logs_entity_idx
    on public.activity_logs (
        entity_type,
        entity_id,
        created_at desc
    );


-- ============================================================
-- DEADLINE REMINDER DELIVERY LOG
-- ============================================================

create table if not exists public.deadline_reminder_logs (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid not null
        references public.registrations(id)
        on delete cascade,

    deadline_date date not null,

    reminder_type text not null,

    delivery_status text not null default 'Pending',

    message_id text,

    error_message text,

    sent_at timestamptz,

    created_at timestamptz not null default now(),

    constraint deadline_reminder_type_check
        check (
            reminder_type in (
                'Three Days',
                'One Day',
                'Deadline Day',
                'Overdue'
            )
        ),

    constraint deadline_reminder_delivery_status_check
        check (
            delivery_status in (
                'Pending',
                'Sent',
                'Failed'
            )
        ),

    constraint deadline_reminder_unique
        unique (
            registration_id,
            deadline_date,
            reminder_type
        )
);


create index if not exists deadline_reminder_logs_status_idx
    on public.deadline_reminder_logs (
        delivery_status,
        created_at
    );


-- ============================================================
-- GENERATED DOCUMENT LOG
-- ============================================================

create table if not exists public.generated_documents (
    id uuid primary key default gen_random_uuid(),

    registration_id uuid
        references public.registrations(id)
        on delete cascade,

    document_type text not null,

    document_number text not null unique,

    storage_path text,

    generated_by text not null default 'Admin',

    generated_at timestamptz not null default now(),

    emailed boolean not null default false,

    emailed_at timestamptz,

    constraint generated_document_type_check
        check (
            document_type in (
                'Offer Letter',
                'Submission Receipt',
                'Selection Certificate',
                'Other'
            )
        )
);


create index if not exists generated_documents_registration_idx
    on public.generated_documents (
        registration_id,
        generated_at desc
    );


-- ============================================================
-- PORTAL SETTINGS
-- ============================================================

create table if not exists public.portal_settings (
    setting_key text primary key,

    setting_value jsonb not null,

    description text,

    updated_by text not null default 'System',

    updated_at timestamptz not null default now()
);


drop trigger if exists portal_settings_set_updated_at
    on public.portal_settings;

create trigger portal_settings_set_updated_at
before update on public.portal_settings
for each row
execute function public.set_updated_at();


insert into public.portal_settings (
    setting_key,
    setting_value,
    description,
    updated_by
)
values
    (
        'maintenance_mode',
        '{"enabled": false, "message": "The portal is temporarily under maintenance."}'::jsonb,
        'Controls whether non-admin users can access the portal.',
        'System'
    ),
    (
        'registration_settings',
        '{"open": true, "allowed_years": ["2nd Year", "3rd Year"]}'::jsonb,
        'Controls new student registration.',
        'System'
    ),
    (
        'submission_settings',
        '{"open": true, "allow_drafts": true, "enforce_deadline": true}'::jsonb,
        'Controls draft and final proof submission.',
        'System'
    ),
    (
        'deadline_settings',
        '{"default_days": 2, "reminder_days": [3, 1, 0]}'::jsonb,
        'Default deadline and reminder configuration.',
        'System'
    ),
    (
        'project_showcase_settings',
        '{"enabled": true, "show_featured_first": true, "maximum_home_projects_per_club": 6}'::jsonb,
        'Controls the public club-project showcase.',
        'System'
    ),
    (
        'support_settings',
        '{"enabled": true, "contact_email": "10xdevss@gmail.com"}'::jsonb,
        'Controls the support-request section.',
        'System'
    ),
    (
        'onboarding_settings',
        '{"confirmation_enabled": true}'::jsonb,
        'Controls onboarding confirmation and attendance.',
        'System'
    )
on conflict (setting_key) do nothing;


-- ============================================================
-- AUTOMATIC TIMELINE FUNCTION
-- ============================================================

create or replace function public.log_registration_status_change()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
    if new.application_status is distinct from old.application_status then
        insert into public.application_timeline (
            registration_id,
            event_type,
            title,
            description,
            visible_to_student,
            created_by
        )
        values (
            new.id,
            'Status Change',
            'Application status updated',
            'Your application status changed from '
                || coalesce(old.application_status, 'Not available')
                || ' to '
                || coalesce(new.application_status, 'Not available')
                || '.',
            true,
            'System'
        );
    end if;

    return new;
end;
$$;


drop trigger if exists registrations_status_timeline_trigger
    on public.registrations;

create trigger registrations_status_timeline_trigger
after update of application_status
on public.registrations
for each row
execute function public.log_registration_status_change();


-- ============================================================
-- UPDATED-AT SUPPORT FOR REGISTRATIONS
-- ============================================================

create or replace function public.set_registration_profile_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
    if
        new.full_name is distinct from old.full_name
        or new.email is distinct from old.email
        or new.mobile_number is distinct from old.mobile_number
        or new.preferred_contact_mode is distinct from old.preferred_contact_mode
    then
        new.profile_updated_at = now();
    end if;

    return new;
end;
$$;


drop trigger if exists registrations_profile_updated_trigger
    on public.registrations;

create trigger registrations_profile_updated_trigger
before update on public.registrations
for each row
execute function public.set_registration_profile_updated_at();


-- ============================================================
-- STORAGE BUCKETS
-- ============================================================

insert into storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
values
    (
        'generated-documents',
        'generated-documents',
        false,
        10485760,
        array[
            'application/pdf'
        ]
    ),
    (
        'club-project-media',
        'club-project-media',
        false,
        10485760,
        array[
            'image/png',
            'image/jpeg',
            'image/webp'
        ]
    )
on conflict (id) do update
set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;


-- Ensure existing portal buckets remain private.

update storage.buckets
set public = false
where id in (
    'task-documents',
    'proof-submissions',
    'generated-documents',
    'club-project-media'
);


-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
-- No anon/authenticated policies are created.
-- The Streamlit backend uses the service-role key.
-- ============================================================

alter table public.registrations
    enable row level security;

alter table public.proof_submissions
    enable row level security;

alter table public.password_reset_otps
    enable row level security;

alter table public.announcements
    enable row level security;

alter table public.announcement_email_logs
    enable row level security;

alter table public.club_projects
    enable row level security;

alter table public.evaluator_accounts
    enable row level security;

alter table public.interview_schedules
    enable row level security;

alter table public.onboarding_attendance
    enable row level security;

alter table public.application_timeline
    enable row level security;

alter table public.support_requests
    enable row level security;

alter table public.activity_logs
    enable row level security;

alter table public.deadline_reminder_logs
    enable row level security;

alter table public.generated_documents
    enable row level security;

alter table public.portal_settings
    enable row level security;


-- ============================================================
-- SECURITY: REMOVE DIRECT PUBLIC TABLE ACCESS
-- ============================================================

revoke all
on table public.password_reset_otps
from anon, authenticated;

revoke all
on table public.evaluator_accounts
from anon, authenticated;

revoke all
on table public.activity_logs
from anon, authenticated;

revoke all
on table public.generated_documents
from anon, authenticated;


-- ============================================================
-- FINAL DATA NORMALIZATION
-- ============================================================

update public.registrations
set
    is_active = coalesce(is_active, true),
    preferred_contact_mode = coalesce(
        preferred_contact_mode,
        'Email'
    ),
    onboarding_status = coalesce(
        onboarding_status,
        'Not Started'
    ),
    interview_status = coalesce(
        interview_status,
        'Not Scheduled'
    );


commit;


-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================
-- Run these separately after the migration if required:
--
-- select count(*) from public.registrations;
-- select count(*) from public.proof_submissions;
-- select * from public.portal_settings order by setting_key;
-- select id, name, public from storage.buckets
-- where id in (
--     'task-documents',
--     'proof-submissions',
--     'generated-documents',
--     'club-project-media'
-- );
-- ============================================================