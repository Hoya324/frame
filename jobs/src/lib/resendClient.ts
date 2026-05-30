import { Resend } from "resend";
import { env } from "./env";

export interface Mailer { send(to: string, subject: string, html: string): Promise<void>; }

export function makeResendMailer(): Mailer {
  const resend = new Resend(env.resendApiKey());
  const from = env.emailFrom();
  return {
    async send(to, subject, html) {
      const { error } = await resend.emails.send({ from, to, subject, html });
      if (error) throw new Error(`Resend failed for ${to}: ${error.message}`);
    },
  };
}
