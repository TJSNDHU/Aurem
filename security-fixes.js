// Immediate remediation actions
module.exports = {
  secrets: {
    action: 'Rotate all keys and implement Vault',
    priority: 'critical',
    owner: 'security-team'
  },
  csp: {
    action: 'Implement strict CSP headers',
    priority: 'high', 
    owner: 'frontend-team'
  },
  xss: {
    action: 'Sanitize all user-controllable inputs',
    priority: 'high',
    owner: 'fullstack-team'
  },
  authz: {
    action: 'Implement resource-level permissions',
    priority: 'medium',
    owner: 'backend-team'
  }
};
