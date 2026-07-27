# Enterprise Communication Module — Technical Architecture Documentation
**Right Ewaste ERP V5.0**

The Communication Module provides real-time team messaging, group collaboration, automated ERP system alerts, and dynamic resource sharing across the enterprise.

---

## 1. Database Schema

All database structures are designed using SQLite:

### `conversations`
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `type` (TEXT: `'DIRECT'` or `'GROUP'`)
- `name` (TEXT, name for group chats)
- `description` (TEXT)
- `created_by` (INTEGER, user reference)
- `owner_id` (INTEGER, group owner reference)
- `status` (TEXT: `'ACTIVE'`, `'ARCHIVED'`, or `'DELETED'`)

### `shared_resources` (Phase 4 Central Registry)
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `message_id` (INTEGER, foreign key to messages)
- `resource_type` (TEXT: `'DOCUMENT'`, `'TASK'`, `'PURCHASE_ORDER'`, etc.)
- `resource_id` (TEXT, unique ID within the owning module)
- `display_title` (TEXT, user-visible title on cards)
- `subtitle` (TEXT, extra description)
- `preview_metadata` (TEXT, JSON string for dynamic previews)
- `deep_link` (TEXT, redirect route)
- `shared_by` (INTEGER, user reference)
- `shared_at` (DATETIME)

### `module_registry`
- `module_name` (TEXT UNIQUE)
- `module_icon` (TEXT)
- `config_json` (TEXT)

---

## 2. Resource Reference Engine Flow

The resource reference engine avoids duplicating business records inside the chat subsystem. It works using a central dispatcher:

```
[User Clicks Card Link]
         │
         ▼
GET /api/v1/communication/resources/<ref_id>/open
         │
         ▼
[Engine evaluates permissions via module_registry]
         │
 ┌───────┴─────────────────────────────────────────┐
 ▼ (DOCUMENT type)                                 ▼ (Billing/Restricted types)
Validate EDMS shared users & folders           Check user role is ADMIN or OPERATOR
         │                                         │
 ┌───────┴───────────────┐                 ┌───────┴───────────────┐
 ▼ (Pass)                ▼ (Fail)          ▼ (Pass)                ▼ (Fail)
Redirect to EDMS        Return HTTP 403   Redirect to Deep Link   Return HTTP 403
```

---

## 3. API Catalog

### Messaging APIs
- `GET /api/v1/communication/conversations/<id>/messages`: Supports `since_id` (polling), `before_id` (cursor scroll-up pagination), and `limit`.
- `POST /api/v1/communication/conversations/<id>/messages`: Sends a message (limited to 60 messages/min in production).

### Resource Sharing APIs
- `POST /api/v1/communication/conversations/<id>/share-resource-v2`: Share generic ERP resource.
- `GET /api/v1/communication/conversations/<id>/shared-resources-v2`: Retrieve resources history categorized by type.

### Preferences & Admin Metrics
- `GET /api/v1/communication/preferences` & `POST /api/v1/communication/preferences`: Configures user alert toggles.
- `GET /api/v1/communication/admin/stats`: Super Admin monitoring stats.
