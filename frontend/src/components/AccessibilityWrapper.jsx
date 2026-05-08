import { useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * AccessibilityWrapper — handles ARIA landmarks, skip navigation,
 * focus management on route changes, and focus trapping for modals.
 * Wrap around app root inside BrowserRouter.
 */
export function AccessibilityWrapper({ children }) {
  const location = useLocation();
  const mainRef = useRef(null);

  // Focus management: move focus to main content on route change
  useEffect(() => {
    if (mainRef.current) {
      mainRef.current.focus({ preventScroll: true });
    }
  }, [location.pathname]);

  return (
    <>
      {/* Skip Navigation Link — first focusable element */}
      <a
        href="#main-content"
        data-testid="skip-nav-link"
        className="skip-nav-link"
      >
        Skip to main content
      </a>

      {/* Main content landmark */}
      <main
        id="main-content"
        ref={mainRef}
        role="main"
        tabIndex={-1}
        style={{ outline: 'none' }}
      >
        {children}
      </main>
    </>
  );
}

/**
 * FocusTrap — traps keyboard focus inside a container (for modals/drawers).
 * Usage: <FocusTrap active={isOpen}><Modal /></FocusTrap>
 */
export function FocusTrap({ active, children, onEscape }) {
  const trapRef = useRef(null);

  useEffect(() => {
    if (!active || !trapRef.current) return;

    // Focus the trap container
    trapRef.current.focus({ preventScroll: true });

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && onEscape) {
        onEscape();
        return;
      }

      if (e.key !== 'Tab') return;

      const focusable = trapRef.current.querySelectorAll(
        'a[href], button:not([disabled]), textarea, input:not([disabled]), select, [tabindex]:not([tabindex="-1"])'
      );

      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [active, onEscape]);

  if (!active) return children;

  return (
    <div ref={trapRef} tabIndex={-1} style={{ outline: 'none' }}>
      {children}
    </div>
  );
}

/**
 * useAnnounce — screen reader announcements for dynamic content.
 * Returns an announce function that creates a live region announcement.
 */
export function useAnnounce() {
  const announce = useCallback((message, priority = 'polite') => {
    const el = document.createElement('div');
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', priority);
    el.setAttribute('aria-atomic', 'true');
    el.className = 'sr-only';
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1000);
  }, []);

  return announce;
}
