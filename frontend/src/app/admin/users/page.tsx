"use client";

import { KeyRound, Power, UserPlus, Users } from "lucide-react";
import { useState } from "react";

import { AdminError, AdminShell } from "@/components/layout/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Alert, Modal, Mono, Skeleton } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import { ApiError, apiPost } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Role, User } from "@/lib/types";
import { useApiResource } from "@/lib/use-api";
import { formatDate } from "@/lib/utils";

interface PublicKey {
  key_id: string;
  algorithm: string;
  public_pem: string;
  created_at: string;
}

export default function UsersPage() {
  const { user: me } = useAuth();
  const {
    data: userList,
    error: usersError,
    reload,
  } = useApiResource<{ items: User[] }>("/users", { errorMessage: "Could not load users." });
  const { data: key } = useApiResource<PublicKey>("/verify/public-key", { auth: false });
  const [actionError, setActionError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    organization: "",
    role: "verifier" as Role,
  });

  const users = userList?.items ?? null;
  const error = usersError ?? actionError;

  async function create() {
    setBusy(true);
    try {
      await apiPost("/users", {
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        organization: form.organization.trim() || null,
        role: form.role,
      });
      setOpen(false);
      setForm({ name: "", email: "", password: "", organization: "", role: "verifier" });
      reload();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "Could not create the account.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function toggle(id: string) {
    try {
      await apiPost(`/users/${id}/toggle-active`);
      reload();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "Could not change that account.",
      );
    }
  }

  return (
    <AdminShell
      title="Users and keys"
      description="Accounts that can issue or verify, and the authority's published signing key."
      action={
        <Button size="sm" icon={<UserPlus className="size-3.5" />} onClick={() => setOpen(true)}>
          Add account
        </Button>
      }
    >
      <div className="space-y-5">
        {error ? <AdminError message={error} /> : null}

        <Card>
          <CardHeader
            title="Accounts"
            description="Admins issue and revoke documents. Verifiers can check documents and keep a history."
            icon={<Users className="size-4" />}
          />
          {!users ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 3 }, (_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Email</Th>
                  <Th>Role</Th>
                  <Th>Organisation</Th>
                  <Th>Status</Th>
                  <Th>Joined</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {!users.length ? (
                  <EmptyRow colSpan={7}>No accounts yet.</EmptyRow>
                ) : (
                  users.map((user) => (
                    <Tr key={user.id}>
                      <Td className="font-medium">{user.name}</Td>
                      <Td className="text-xs text-muted">{user.email}</Td>
                      <Td>
                        <Badge tone={user.role === "admin" ? "brand" : "neutral"}>
                          {user.role}
                        </Badge>
                      </Td>
                      <Td className="text-xs text-muted">{user.organization || "—"}</Td>
                      <Td>
                        <Badge tone={user.is_active ? "ok" : "bad"}>
                          {user.is_active ? "active" : "disabled"}
                        </Badge>
                      </Td>
                      <Td className="text-xs text-muted">{formatDate(user.created_at)}</Td>
                      <Td>
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<Power className="size-3.5" />}
                          disabled={user.id === me?.id}
                          onClick={() => toggle(user.id)}
                        >
                          {user.is_active ? "Disable" : "Enable"}
                        </Button>
                      </Td>
                    </Tr>
                  ))
                )}
              </tbody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Active signing key"
            description="Published so anyone can verify a Merkle-root signature without trusting this service."
            icon={<KeyRound className="size-4" />}
            action={key ? <Badge tone="brand">{key.algorithm}</Badge> : null}
          />
          <CardBody>
            {key ? (
              <>
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
                  <span>
                    Key ID <Mono>{key.key_id}</Mono>
                  </span>
                  <span>Created {formatDate(key.created_at)}</span>
                </div>
                <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-muted p-3 font-mono text-[10px] leading-relaxed">
                  {key.public_pem.trim()}
                </pre>
              </>
            ) : (
              <Skeleton className="h-32 w-full" />
            )}
          </CardBody>
        </Card>
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Add an account"
        description="Admins can issue documents; verifiers can only check them."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              loading={busy}
              disabled={
                !form.name.trim() || !form.email.includes("@") || form.password.length < 8
              }
              onClick={create}
            >
              Create account
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Alert tone="info">
            The person can change nothing about their role themselves — self-registration always
            creates a verifier.
          </Alert>
          <Field label="Full name" htmlFor="u-name">
            <Input
              id="u-name"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Field>
          <Field label="Email" htmlFor="u-email">
            <Input
              id="u-email"
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Role" htmlFor="u-role">
              <Select
                id="u-role"
                value={form.role}
                onChange={(event) => setForm({ ...form, role: event.target.value as Role })}
              >
                <option value="verifier">Verifier</option>
                <option value="admin">Admin (issuer)</option>
              </Select>
            </Field>
            <Field label="Organisation" htmlFor="u-org">
              <Input
                id="u-org"
                value={form.organization}
                onChange={(event) => setForm({ ...form, organization: event.target.value })}
              />
            </Field>
          </div>
          <Field label="Temporary password" hint="At least 8 characters." htmlFor="u-pass">
            <Input
              id="u-pass"
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
            />
          </Field>
        </div>
      </Modal>
    </AdminShell>
  );
}
