import { useMutation } from "@tanstack/react-query";
import { Link, useRouter } from "@tanstack/react-router";
import type { FormEvent, ReactNode } from "react";
import { useState } from "react";

import { Button, Card, CardContent, CardHeader, CardTitle, Input, Label } from "@khetibadi/ui";

import { authApi } from "../lib/api";
import { setAuth } from "../store/auth-store";

export function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("farmer@example.com");
  const [password, setPassword] = useState("Password1");
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
    <AuthShell title="Sign in" subtitle="Use your Khetibadi account to continue.">
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Email">
          <Input type="email" value={email} onChange={(event) => { setEmail(event.target.value); }} required />
        </Field>
        <Field label="Password">
          <Input
            type="password"
            value={password}
            onChange={(event) => { setPassword(event.target.value); }}
            required
          />
        </Field>
        {mutation.error ? <p className="text-sm text-red-600">Invalid email or password.</p> : null}
        <Button className="w-full" loading={mutation.isPending} type="submit">
          Sign in
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        New here? <Link className="font-semibold text-emerald-700" to="/register">Create account</Link>
      </p>
    </AuthShell>
  );
}

export function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("Demo Farmer");
  const [email, setEmail] = useState("farmer@example.com");
  const [password, setPassword] = useState("Password1");
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
    <AuthShell title="Create account" subtitle="Start with the runnable local vertical slice.">
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Name">
          <Input value={name} onChange={(event) => { setName(event.target.value); }} required />
        </Field>
        <Field label="Email">
          <Input type="email" value={email} onChange={(event) => { setEmail(event.target.value); }} required />
        </Field>
        <Field label="Password">
          <Input
            minLength={8}
            type="password"
            value={password}
            onChange={(event) => { setPassword(event.target.value); }}
            required
          />
        </Field>
        {mutation.error ? <p className="text-sm text-red-600">Unable to create account.</p> : null}
        <Button className="w-full" loading={mutation.isPending} type="submit">
          Create account
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Already registered? <Link className="font-semibold text-emerald-700" to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}

function AuthShell({ children, title, subtitle }: { children: ReactNode; title: string; subtitle: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-emerald-50 via-white to-amber-50 p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <p className="mt-2 text-sm text-slate-500">{subtitle}</p>
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
