// AUREM — Cloudflare Email Worker
// ----------------------------------------------------------
// Deploy via Cloudflare → Workers & Pages → Create → Email Worker.
// Then Email Routing rule: ora@aurem.live → Send to Worker → (this).
//
// Forwards parsed email as JSON to /api/email/inbound.
// Uses postal-mime (built-in) to parse raw MIME.
// ----------------------------------------------------------

import PostalMime from "postal-mime";

const BACKEND_URL = "https://aurem.live/api/email/inbound";
// Optional: set a secret in CF Worker → Settings → Variables
//   Name: INBOUND_TOKEN   Value: <match backend EMAIL_INBOUND_TOKEN>
// Then this Worker will send it as Bearer.

export default {
  async email(message, env, ctx) {
    try {
      const raw = await new Response(message.raw).text();
      const parsed = await PostalMime.parse(raw);

      const payload = {
        from: message.from || parsed.from?.address,
        to: message.to || parsed.to?.[0]?.address,
        subject: parsed.subject || "(no subject)",
        text: parsed.text || "",
        html: parsed.html || "",
        messageId: parsed.messageId,
        inReplyTo: parsed.inReplyTo,
        headers: Object.fromEntries(
          (parsed.headers || []).map((h) => [h.key.toLowerCase(), h.value])
        ),
      };

      const headers = { "Content-Type": "application/json" };
      if (env.INBOUND_TOKEN) {
        headers["Authorization"] = `Bearer ${env.INBOUND_TOKEN}`;
      }

      const res = await fetch(BACKEND_URL, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        console.log("[aurem-email] backend error", res.status, await res.text());
      } else {
        console.log("[aurem-email] forwarded OK", message.from);
      }
    } catch (e) {
      console.log("[aurem-email] worker error", e && e.stack);
    }
  },
};
