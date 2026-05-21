/**
 * v2api.js — tiny shared HTTP helper for V2 customer pages.
 *
 * Centralises the base URL + bearer-token logic so every page-component
 * stays declarative. Reads the token from the LuxeAuthContext token
 * storage slots (`aurem_customer_token` → `platform_token` → `token`).
 */
import axios from 'axios';

const BACKEND =
  process.env.REACT_APP_BACKEND_URL ||
  (typeof window !== 'undefined' ? window.location.origin : '');

export const getToken = () => {
  if (typeof window === 'undefined') return '';
  return (
    window.localStorage.getItem('aurem_customer_token')
    || window.localStorage.getItem('platform_token')
    || window.localStorage.getItem('token')
    || ''
  );
};

const headers = () => {
  const t = getToken();
  return t
    ? { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
};

export const v2api = {
  get:    (path, opts = {})        => axios.get(`${BACKEND}${path}`,              { ...opts, headers: { ...headers(), ...(opts.headers || {}) } }),
  post:   (path, body, opts = {})  => axios.post(`${BACKEND}${path}`, body || {}, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } }),
  patch:  (path, body, opts = {})  => axios.patch(`${BACKEND}${path}`, body || {}, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } }),
  delete: (path, opts = {})        => axios.delete(`${BACKEND}${path}`,           { ...opts, headers: { ...headers(), ...(opts.headers || {}) } }),
};

export default v2api;
