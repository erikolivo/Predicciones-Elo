-- Ejecuta este SQL una sola vez en Supabase > SQL Editor.
-- Crea una fila de datos independiente para cada usuario autenticado.

create table if not exists public.user_app_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.user_app_state enable row level security;

drop policy if exists "users can read own state" on public.user_app_state;
drop policy if exists "users can insert own state" on public.user_app_state;
drop policy if exists "users can update own state" on public.user_app_state;

create policy "users can read own state"
on public.user_app_state
for select
using (auth.uid() = user_id);

create policy "users can insert own state"
on public.user_app_state
for insert
with check (auth.uid() = user_id);

create policy "users can update own state"
on public.user_app_state
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);
