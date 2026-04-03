# Stability Check Report - February 21, 2026

## WebSocket & Real-Time Features Status

### ✅ Backend WebSocket Infrastructure
| Component | Status | Location |
|-----------|--------|----------|
| WebSocketConnectionManager | ✅ Working | `server.py:305-377` |
| ws_manager (global instance) | ✅ Working | `server.py:380` |
| broadcast_admin_event() | ✅ Working | `server.py:384-391` |
| /ws endpoint | ✅ Working | `server.py:3189-3245` |
| /api/admin/websocket/status | ✅ Working | `server.py:3248-3255` |

### ✅ Frontend WebSocket Integration
| Component | Status | File |
|-----------|--------|------|
| WebSocketContext | ✅ Working | `contexts/WebSocketContext.js` |
| OrderTicker | ✅ Working | `components/admin/OrderTicker.js` |
| OrderFlowDashboard | ✅ Working | `components/admin/OrderFlowDashboard.js` |
| BiomarkerBenchmarksManager | ✅ Working | Real-time CRUD events |
| ProgramsManager | ✅ Working | new_order, new_partner events |

### Events Being Broadcast
- `new_order` - When new order is placed (line 7572-7578)
- `order_shipped` - When order is shipped (line 1222-1227)
- `inventory_update` - When stock changes (line 1117-1122)
- `biomarker_created/updated/deleted` - Biomarker CRUD

## Known Considerations

### Global Dependencies (Cannot be Refactored Yet)
The following are used across multiple modules and remain in `server.py`:

1. **ws_manager** - Used by:
   - Order creation (broadcast new_order)
   - Shipping updates (broadcast order_shipped)
   - Inventory changes (broadcast inventory_update)
   - Biomarker CRUD operations

2. **db** (database connection) - Used everywhere

3. **Helper functions** - `broadcast_admin_event()`, `get_current_user()`

### Why WebSocket Stays in server.py
Moving WebSocket to a separate module would require:
- Circular import handling (ws_manager needs to be imported by many modules)
- Event bus pattern implementation
- Significant refactoring of order/shipping/inventory code

**Recommendation**: Keep WebSocket in server.py until a proper event bus is implemented.

## Test Commands

```bash
# Check WebSocket status
curl -s "$API_URL/api/admin/websocket/status" -H "Authorization: Bearer $TOKEN"

# Check if OrderTicker receives events (browser console)
localStorage.setItem('debug_websocket', 'true');
```

## Monitoring

Watch for these issues:
1. WebSocket disconnections in browser console
2. Order notifications not appearing
3. Inventory not syncing across tabs

If issues occur, check:
```bash
tail -f /var/log/supervisor/backend.err.log | grep -i websocket
```
