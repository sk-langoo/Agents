import "dotenv/config";
import { z } from "zod";

const schema = z.object({
  GOOGLE_CLIENT_ID: z.string().min(1).optional(),
  GOOGLE_CLIENT_SECRET: z.string().min(1).optional(),
  GOOGLE_REDIRECT_URI: z.string().url().default("http://localhost:3000/oauth2/callback"),
  OPENAI_API_KEY: z.string().min(1).optional(),
  OPENAI_MODEL: z.string().default("gpt-4.1-mini"),
  PORT: z.coerce.number().int().positive().default(3000),
  CALENDAR_TIME_ZONE: z.string().default("America/New_York")
});

export const config = schema.parse(process.env);

export function requireGoogleConfig() {
  if (!config.GOOGLE_CLIENT_ID || !config.GOOGLE_CLIENT_SECRET) {
    throw new Error("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET. See .env.example.");
  }
}
