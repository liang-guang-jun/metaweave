import { z } from "zod";

/**
 * Password rules advertised by the backend through `/healthz`. Field names match
 * the `password_policy` configuration section so both sides share one vocabulary.
 */
export type PasswordPolicy = {
  min_length: number;
  require_upper: boolean;
  require_digit: boolean;
  require_symbol: boolean;
};

const email = z.string().email("Enter a valid email address.");

/**
 * Sign-in only checks that a password was entered. Current policy rules must not
 * gate accounts created under older rules; the backend remains the authority.
 */
export const loginSchema = z.object({
  email,
  password: z.string().min(1, "Enter your password."),
});

/**
 * Build the register schema from the live backend policy so the form rejects
 * exactly what `POST /iam/users` would reject.
 */
export function createRegisterSchema(policy: PasswordPolicy) {
  let password = z
    .string()
    .min(
      policy.min_length,
      `Password must contain at least ${policy.min_length} characters.`,
    );
  if (policy.require_upper) {
    password = password.regex(
      /[A-Z]/,
      "Password must contain an uppercase letter.",
    );
  }
  if (policy.require_digit) {
    password = password.regex(/[0-9]/, "Password must contain a number.");
  }
  if (policy.require_symbol) {
    password = password.regex(
      /[^A-Za-z0-9]/,
      "Password must contain a symbol.",
    );
  }
  return z
    .object({
      email,
      password,
      // Only require the field to be filled in; the comparison is handled by the
      // refine below so an identical-but-short password is never described as
      // "please confirm your password".
      confirmPassword: z.string().min(1, "Please confirm your password."),
    })
    .refine((values) => values.password === values.confirmPassword, {
      message: "Passwords do not match.",
      path: ["confirmPassword"],
    });
}
