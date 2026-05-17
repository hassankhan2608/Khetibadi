import { useMutation } from "@tanstack/react-query";
import { Link, useRouter } from "@tanstack/react-router";
import type { FormEvent, ReactNode } from "react";
import { useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from "@khetibadi/ui";

import { authApi } from "../lib/api";
import { setAuth } from "../store/auth-store";

export function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: async (session) => {
      setAuth(session);
      await router.navigate({ to: "/dashboard" });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    mutation.mutate({ email, password });
  }

  return (
    <AuthShell eyebrow="Welcome back" title="Sign in" subtitle="Continue to your farm workspace through the Khetibadi gateway.">
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Email">
          <Input
            autoComplete="email"
            placeholder="you@example.com"
            type="email"
            value={email}
            onChange={(event) => { setEmail(event.target.value); }}
            required
          />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            value={password}
            onChange={(event) => { setPassword(event.target.value); }}
            required
          />
        </Field>
        {mutation.error ? <p className="text-sm font-semibold text-[#8a2f22]">Invalid email or password.</p> : null}
        <Button className="w-full" loading={mutation.isPending} type="submit">
          Sign in
        </Button>
      </form>
        <p className="mt-6 text-center text-sm text-[#7a6548]">
        New here? <Link className="font-bold text-[#2f5d3a]" to="/register">Create account</Link>
      </p>
    </AuthShell>
  );
}

export function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: authApi.register,
    onSuccess: async (session) => {
      setAuth(session);
      await router.navigate({ to: "/dashboard" });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    mutation.mutate({ name, email, password });
  }

  return (
    <AuthShell eyebrow="Namaste" title="Create account" subtitle="Set up your farmer workspace for farms, prices, scans, and advisory.">
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Name">
          <Input
            autoComplete="name"
            placeholder="Your name"
            value={name}
            onChange={(event) => { setName(event.target.value); }}
            required
          />
        </Field>
        <Field label="Email">
          <Input
            autoComplete="email"
            placeholder="you@example.com"
            type="email"
            value={email}
            onChange={(event) => { setEmail(event.target.value); }}
            required
          />
        </Field>
        <Field label="Password">
          <Input
            minLength={8}
            type="password"
            autoComplete="new-password"
            placeholder="At least 8 chars, one uppercase, one digit"
            value={password}
            onChange={(event) => { setPassword(event.target.value); }}
            required
          />
        </Field>
        {mutation.error ? <p className="text-sm font-semibold text-[#8a2f22]">Unable to create account.</p> : null}
        <Button className="w-full" loading={mutation.isPending} type="submit">
          Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-[#7a6548]">
        Already registered? <Link className="font-bold text-[#2f5d3a]" to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}

function AuthShell({
  children,
  eyebrow,
  title,
  subtitle,
}: {
  children: ReactNode;
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden p-6">
      <div className="absolute left-8 top-8 hidden rounded-full border border-[#d8c4a5] bg-[#fffaf0]/70 px-5 py-2 text-sm font-bold text-[#2f5d3a] shadow-sm md:block">
        Khetibadi
      </div>
      <div className="absolute bottom-10 right-10 hidden max-w-xs rounded-[2rem] border border-[#d8c4a5] bg-[#2f5d3a] p-5 text-[#fffaf0] shadow-2xl md:block">
        <p className="text-sm font-bold text-[#f3dfb4]">Soft Craft dashboard</p>
        <p className="mt-2 text-sm text-[#efe3d1]">Dusty mitti tones, field green surfaces, and farmer-first workflows.</p>
      </div>
      <Card className="relative w-full max-w-md overflow-hidden">
        <div className="h-2 bg-gradient-to-r from-[#2f5d3a] via-[#b87924] to-[#7a4e2d]" />
        <CardHeader className="space-y-2">
          <p className="text-sm font-extrabold uppercase tracking-[0.22em] text-[#b87924]">{eyebrow}</p>
          <CardTitle className="text-3xl">{title}</CardTitle>
          <p className="text-sm leading-6 text-[#6d5a40]">{subtitle}</p>
        </CardHeader>
        <CardContent>{children}</CardContent>
      </Card>
    </div>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
