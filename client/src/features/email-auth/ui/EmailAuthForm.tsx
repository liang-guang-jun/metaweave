import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { PrimaryButton } from "@/shared/ui/Button";
import { Field } from "@/shared/ui/Field";
import { emailAuthSchema, registerSchema } from "@/shared/lib/validation";
import type { AuthPageMode } from "../model/types";
import { getApiError, loginUser, registerUser } from "../model/api";
import styled, { keyframes } from "styled-components";

const enter = keyframes`from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); }`;
const Form = styled.form`
  width: 100%;
  animation: ${enter} ${({ theme }) => theme.motion.normal} ease both;
`;

type EmailAuthFormProps = {
  mode: AuthPageMode;
  tenantId?: string;
  onSuccess: (mode: AuthPageMode) => void;
};

export function EmailAuthForm({
  mode,
  tenantId,
  onSuccess,
}: EmailAuthFormProps) {
  const [loading, setLoading] = useState(false);
  const isRegister = mode === "register";

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const schema = isRegister ? registerSchema : emailAuthSchema;
    const result = schema.safeParse(
      Object.fromEntries(new FormData(event.currentTarget)),
    );
    if (!result.success) {
      toast.error(
        result.error.issues[0]?.message ?? "Please check your details.",
      );
      return;
    }
    setLoading(true);
    const { email, password } = result.data;
    const request = isRegister
      ? registerUser(email, password)
      : loginUser(email, password, tenantId);
    request
      .then(() => {
        if (isRegister)
          toast.success(
            "Account created. Verification is required before sign-in.",
          );
        onSuccess(mode);
      })
      .catch((error: unknown) => {
        toast.error(
          getApiError(
            error,
            isRegister
              ? "Unable to create your account."
              : "Unable to sign in.",
          ),
        );
      })
      .finally(() => setLoading(false));
  };

  return (
    <Form onSubmit={submit} noValidate>
      <Field $index={0}>
        <input name="email" type="email" autoComplete="email" placeholder=" " />
        <span>Email</span>
      </Field>
      <Field $index={1}>
        <input
          name="password"
          type="password"
          autoComplete={isRegister ? "new-password" : "current-password"}
          placeholder=" "
        />
        <span>Password</span>
      </Field>
      {isRegister && (
        <Field $index={2}>
          <input
            name="confirmPassword"
            type="password"
            autoComplete="new-password"
            placeholder=" "
          />
          <span>Confirm password</span>
        </Field>
      )}
      <PrimaryButton disabled={loading} type="submit">
        {loading ? "Continuing…" : isRegister ? "Create account" : "Sign in"}
      </PrimaryButton>
    </Form>
  );
}
