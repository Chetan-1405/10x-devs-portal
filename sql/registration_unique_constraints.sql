-- Run once in Supabase SQL Editor before opening registration.
-- These indexes prevent duplicate accounts during simultaneous submissions.

create unique index if not exists registrations_registration_number_unique
on public.registrations (lower(trim(registration_number)));

create unique index if not exists registrations_email_unique
on public.registrations (lower(trim(email)));

create unique index if not exists registrations_mobile_number_unique
on public.registrations (trim(mobile_number))
where mobile_number is not null and trim(mobile_number) <> '';

create unique index if not exists registrations_application_reference_unique
on public.registrations (application_reference)
where application_reference is not null;
