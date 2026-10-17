-- Vale: one row per signed-in reader. Run this once in Supabase: SQL Editor -> New query -> Run.
create table if not exists public.vale_readers (
  user_id uuid primary key references auth.users (id) on delete cascade,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- Keep updated_at fresh on every write.
create or replace function public.vale_touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists vale_readers_touch on public.vale_readers;
create trigger vale_readers_touch before update on public.vale_readers
  for each row execute function public.vale_touch_updated_at();

-- Row Level Security on, with no policies: browsers (publishable key) can't read or write
-- this table at all. Only the Vale backend, using the secret key, can.
alter table public.vale_readers enable row level security;
