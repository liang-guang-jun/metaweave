import { z } from "zod";

export const emailAuthSchema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z
    .string()
    .min(8, "Password must contain at least 12 characters.")
    .regex(/[A-Z]/, "Password must contain an uppercase letter.")
    .regex(/[0-9]/, "Password must contain a number.")
    .regex(/[^A-Za-z0-9]/, "Password must contain a symbol."),
});

export const registerSchema = emailAuthSchema
  .extend({
    confirmPassword: z.string().min(12, "Please confirm your password."),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: "Passwords do not match.",
    path: ["confirmPassword"],
  });
