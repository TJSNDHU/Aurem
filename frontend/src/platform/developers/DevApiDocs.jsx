/**
 * /developers/docs — Swagger UI page (Auth-gated)
 * Loads Swagger UI from CDN, points at the filtered openapi schema
 * (developer routes only), pre-fills the bearer auth from localStorage.
 */
import React, { useEffect, useRef } from "react";
import DeveloperShell, { getDevJwt } from "./DeveloperShell";
import { PageHeader } from "./DevDashboard";

const API = process.env.REACT_APP_BACKEND_URL || "";
const SWAGGER_CSS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css";
const SWAGGER_JS  = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js";

export default function DevApiDocs() {
  const containerRef = useRef(null);

  useEffect(() => {
    // Load Swagger CSS once
    if (!document.querySelector('link[data-swagger-ui]')) {
      const l = document.createElement("link");
      l.rel  = "stylesheet";
      l.href = SWAGGER_CSS;
      l.setAttribute("data-swagger-ui", "1");
      document.head.appendChild(l);
    }
    // Load Swagger JS once
    function mount() {
      if (!window.SwaggerUIBundle || !containerRef.current) return;
      const jwt = getDevJwt();
      window.SwaggerUIBundle({
        url:        `${API}/api/developers/openapi.json`,
        dom_id:     "#swagger-ui-container",
        deepLinking:        true,
        docExpansion:       "list",
        defaultModelsExpandDepth: -1,
        persistAuthorization: true,
        requestInterceptor: (req) => {
          // Auto-attach the dev JWT to every "Try it out" call
          const t = getDevJwt();
          if (t && !req.headers["Authorization"]) {
            req.headers["Authorization"] = `Bearer ${t}`;
          }
          return req;
        },
        onComplete() {
          // Pre-authorize the UI so the lock icon is closed by default
          if (jwt && window.swaggerUiInstance) {
            try {
              window.swaggerUiInstance.preauthorizeApiKey("BearerAuth", jwt);
            } catch (e) { /* ignore */ }
          }
        },
      });
    }
    if (window.SwaggerUIBundle) {
      mount();
    } else {
      const s = document.createElement("script");
      s.src = SWAGGER_JS;
      s.onload = mount;
      document.body.appendChild(s);
    }
  }, []);

  return (
    <DeveloperShell requireAuth>
      <PageHeader eyebrow="API DOCS"
                  title="REST API reference"
                  sub="All developer-portal endpoints. Your JWT is pre-filled. Hit 'Try it out' to call against your own account." />

      <div data-testid="dev-api-docs"
           className="av2-card"
           style={{ padding: 0, overflow: "hidden" }}>
        <div ref={containerRef} id="swagger-ui-container"
              style={{ background: "#fff", color: "#1A1718",
                        minHeight: 600 }} />
      </div>

      <style>{`
        /* Tame Swagger UI so it doesn't blow up the AUREM cards */
        #swagger-ui-container .topbar { display: none; }
        #swagger-ui-container .information-container { padding: 24px; }
        #swagger-ui-container .swagger-ui {
          font-family: -apple-system, system-ui, sans-serif;
        }
      `}</style>
    </DeveloperShell>
  );
}
