/**
 * useV2Toast — minimal toast helper (success/error/info).
 * Renders a sonner toast (sonner is already in the dep tree via the V2 shell).
 */
import { toast } from 'sonner';

export const useV2Toast = () => ({
  success: (msg) => toast.success(msg),
  error:   (msg) => toast.error(msg),
  info:    (msg) => toast(msg),
});

export default useV2Toast;
