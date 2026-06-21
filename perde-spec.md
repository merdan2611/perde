# Perde — Collaborative Story Writing App
## Product Specification & Design Guide

---

## 1. Overview

**Perde** is a minimalist web app for two or more people to write stories together. Users take turns editing a shared story document. Every save is recorded as a commit with author and timestamp. Contributors get an email notification when someone edits their story.

**Target users:** 2–3 people, letter-pen / pen-pal style collaborative writing.

**Core principle:** Simple enough that the writing stays the focus — not the tool.

---

## 2. Features

### Auth
- Register with email + password (no email verification required)
- Login / logout
- Password stored hashed (bcrypt)

### Stories
- Create a new story (title required)
- View a list of your stories (stories you created or were added to as contributor)
- Open a story to read or edit

### Editor
- Plain textarea — no rich text, no markdown rendering
- Save button commits the current content
- On save: if another user edited after your last load, show a **conflict warning** (do not overwrite, let user copy their text and reload)
- "Add contributor" — enter email of registered user to add them to the story

### Commit history
- Every save is stored as a commit: `author`, `timestamp`, `content snapshot`
- History tab inside the story shows all commits in reverse chronological order
- Each commit shows: author name, relative time, first ~80 chars of content as preview

### Email notifications
- When a user saves a commit, all other contributors of that story receive a short email
- Email content: story title, who edited it, timestamp, a short preview of the new text
- No email sent to the person who made the edit

---

## 3. Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | FastAPI (Python) | Lightweight, easy to deploy, async support |
| Database | SQLite | No setup needed, sufficient for 2–3 users |
| Frontend | Plain HTML + CSS + JS | No build step, simple to maintain |
| Email | Resend API | Free tier: 3,000 emails/month, simple REST API |
| Hosting | Render.com | Free tier supports FastAPI, persistent disk for SQLite |
| Storage | Local filesystem on Render | SQLite file on persistent disk |

---

## 4. Database Schema

```sql
-- Users
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Stories
CREATE TABLE stories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  created_by INTEGER REFERENCES users(id),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Story contributors (many-to-many)
CREATE TABLE story_contributors (
  story_id INTEGER REFERENCES stories(id),
  user_id INTEGER REFERENCES users(id),
  added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (story_id, user_id)
);

-- Commits (every save)
CREATE TABLE commits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  story_id INTEGER REFERENCES stories(id),
  author_id INTEGER REFERENCES users(id),
  content TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Active edit lock (conflict detection)
CREATE TABLE edit_locks (
  story_id INTEGER PRIMARY KEY REFERENCES stories(id),
  user_id INTEGER REFERENCES users(id),
  locked_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. API Endpoints

```
POST   /auth/register           body: { email, password, display_name }
POST   /auth/login              body: { email, password } → returns JWT token
POST   /auth/logout

GET    /stories                 returns stories for current user
POST   /stories                 body: { title } → creates new story
GET    /stories/{id}            story detail + latest content + contributors
DELETE /stories/{id}

GET    /stories/{id}/commits    list of all commits (reverse chrono)
POST   /stories/{id}/commits    body: { content, base_commit_id } → saves new commit
                                returns 409 Conflict if base_commit_id is outdated

POST   /stories/{id}/contributors   body: { email } → add contributor by email
DELETE /stories/{id}/contributors/{user_id}

GET    /stories/{id}/lock       check if story is being edited
POST   /stories/{id}/lock       acquire edit lock
DELETE /stories/{id}/lock       release edit lock
```

### Conflict detection logic
1. When user opens editor, frontend records the `latest_commit_id`
2. On save, frontend sends `base_commit_id` = that recorded id
3. Backend checks: if the story's current latest commit id ≠ `base_commit_id`, return `409 Conflict`
4. Frontend shows conflict warning — user must copy their text, reload, and re-apply

---

## 6. File Structure

```
perde/
├── backend/
│   ├── main.py              # FastAPI app, routes
│   ├── models.py            # SQLite models / queries
│   ├── auth.py              # JWT, password hashing
│   ├── email_service.py     # Resend API integration
│   ├── database.py          # DB connection, init
│   └── requirements.txt
├── frontend/
│   ├── index.html           # Login / register page
│   ├── home.html            # Story list page
│   ├── editor.html          # Story editor page
│   ├── style.css            # Shared styles
│   └── app.js               # API calls, page logic
└── render.yaml              # Render.com deploy config
```

---

## 7. Design System

### Philosophy
Clean, editorial, distraction-free. The writing is the product — the UI should disappear behind it. No gradients, no shadows, no decorative elements. Every pixel earns its place.

### Color Palette

| Token | Light mode | Dark mode | Usage |
|---|---|---|---|
| `--bg-primary` | `#FFFFFF` | `#111110` | Page background |
| `--bg-secondary` | `#F5F4F1` | `#1C1C1A` | Cards, surfaces |
| `--bg-tertiary` | `#EEEDE9` | `#252523` | Hover states, inputs |
| `--text-primary` | `#1A1A18` | `#F0EFE9` | Body text, headings |
| `--text-secondary` | `#6B6A65` | `#8A8980` | Labels, metadata |
| `--text-tertiary` | `#A8A79F` | `#5C5B55` | Placeholders, hints |
| `--border` | `rgba(0,0,0,0.10)` | `rgba(255,255,255,0.08)` | All borders |
| `--border-hover` | `rgba(0,0,0,0.20)` | `rgba(255,255,255,0.15)` | Hover borders |
| `--accent-green` | `#1D9E75` | `#2BBF8E` | "Mine" commit dot, success |
| `--accent-purple` | `#7F77DD` | `#9B94E8` | "Theirs" commit dot |
| `--warning-bg` | `#FEF3E2` | `#2A200A` | Conflict banner background |
| `--warning-text` | `#92500A` | `#F0A030` | Conflict banner text |
| `--warning-border` | `#F0A030` | `#7A5010` | Conflict banner border |

### Typography

- **Font:** System font stack — `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- No web font imports — keeps it fast and native-feeling

| Scale | Size | Weight | Usage |
|---|---|---|---|
| `--text-xl` | 20px | 500 | Page titles |
| `--text-lg` | 16px | 500 | Card titles, nav logo |
| `--text-md` | 15px | 400 | Body text, editor |
| `--text-sm` | 13px | 400 | Labels, metadata, buttons |
| `--text-xs` | 12px | 400 | Timestamps, hints |

Line height: `1.7` for body/editor. `1.3` for titles.

### Spacing

Use a base-8 scale: `4px, 8px, 12px, 16px, 20px, 24px, 32px, 48px`

- Page padding: `20px` (mobile), `24px` (desktop)
- Card padding: `16px 20px`
- Gap between cards: `12px`
- Section gap: `24px`

### Border Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | `6px` | Badges, small pills |
| `--radius-md` | `8px` | Buttons, inputs |
| `--radius-lg` | `12px` | Cards |

### Borders

All borders: `0.5px solid var(--border)` — hairline only, no heavy dividers.

### Buttons

Two types only:

**Primary** — dark fill
```css
background: var(--text-primary);
color: var(--bg-primary);
border: none;
border-radius: var(--radius-md);
padding: 7px 14px;
font-size: 13px;
```

**Default** — outlined
```css
background: transparent;
color: var(--text-primary);
border: 0.5px solid var(--border-hover);
border-radius: var(--radius-md);
padding: 7px 14px;
font-size: 13px;
```

Hover on default: `background: var(--bg-secondary)`
Active: `transform: scale(0.98)`

### Avatar / Initials Circle

```css
width: 28px;
height: 28px;
border-radius: 50%;
font-size: 11px;
font-weight: 500;
display: flex; align-items: center; justify-content: center;
```

Color assignment: first contributor → green tint (`#E1F5EE` bg / `#0F6E56` text), second → purple tint (`#EEEDFE` bg / `#534AB7` text), third and beyond → gray.

---

## 8. Pages & UI

### 8.1 Login / Register (`index.html`)

- Centered card, max-width 360px
- Logo at top: "perde" in 18px/500
- Email + password inputs
- Primary button full width
- Toggle between login and register (no page reload, just swap the form)
- No social login

### 8.2 Home — Story List (`home.html`)

**Nav bar:**
- Left: logo "perde"
- Right: user display name + logout link

**Content:**
- Heading "my stories"
- "+ new story" primary button (top right of heading row)
- Story cards in a single column list
- Each card shows: title, contributor avatars, commit count, relative time of last edit
- Click card → go to editor

**Empty state:**
- "no stories yet. create one to get started." — centered, muted text

### 8.3 Editor (`editor.html`)

**Nav bar:**
- Back arrow → home
- Story title (editable inline on click)
- "save" primary button (right)

**Below nav — two tabs:**
- **write** tab (default)
- **history** tab

**Write tab:**
- Contributor avatars row + "add contributor" small button on right
- Large textarea, full width, min-height 400px on desktop / 240px on mobile
- No toolbar, no formatting — plain text only
- Font inside textarea: `15px / 1.7` line-height, same color as body text

**History tab:**
- List of commits, newest first
- Each row: colored dot (green = me, purple = other) + avatar + author name + preview text + relative timestamp
- "no history yet" empty state if no commits

**Conflict banner** (shown above textarea when conflict detected):
```
⚠ [name] is editing this story right now. Copy your text, reload, then re-apply your changes.
```
Background: `--warning-bg`, text: `--warning-text`, border: `0.5px solid var(--warning-border)`
Save button is disabled while conflict banner is visible.

### 8.4 "Add Contributor" Modal

- Simple overlay (semi-transparent bg)
- Single input: "contributor's email"
- "add" button + "cancel" link
- Error: "no user found with that email"
- Success: closes modal, avatar appears in contributor row

---

## 9. Responsive Behavior

### Breakpoints

| Name | Width |
|---|---|
| Mobile | < 480px |
| Tablet | 480px – 768px |
| Desktop | > 768px |

### Mobile-specific rules

- Nav: logo + save button only (user name hidden)
- Editor textarea: `min-height: 55vh`
- Tabs become full-width (50/50 split)
- Cards take full viewport width, side padding 16px
- Max-width on content container: none (full bleed with padding)
- Font sizes unchanged — do not shrink text below 13px
- Touch targets minimum 44px height for all buttons and tabs

### Desktop

- Content max-width: `720px`, centered
- Nav max-width matches content

---

## 10. Email Notification

Sent via [Resend](https://resend.com) when a commit is saved.

**Subject:** `[Perde] {display_name} updated "{story_title}"`

**Body (plain text):**
```
Hi {recipient_name},

{display_name} just made an edit to "{story_title}".

---
{first 200 chars of new content}...
---

Open the story: {app_url}/editor.html?id={story_id}

— Perde
```

- HTML version optional (keep it plain, same content)
- Do not send to the user who made the edit
- Send to all other contributors of that story

---

## 11. Conflict Detection — Frontend Flow

```
1. User opens editor
   → frontend fetches story: stores latest_commit_id in memory

2. User starts typing
   → frontend POST /stories/{id}/lock  (acquire lock)

3. User clicks "save"
   → POST /stories/{id}/commits  with body: { content, base_commit_id: latest_commit_id }
   
   If 200 OK:
     → update latest_commit_id to new commit id
     → release lock (DELETE /stories/{id}/lock)
     → show "saved" toast briefly
   
   If 409 Conflict:
     → show conflict banner
     → disable save button
     → user must reload page to continue

4. User leaves page / closes tab
   → DELETE /stories/{id}/lock  (release lock)
   → use beforeunload event
```

---

## 12. Deploy — Render.com

**`render.yaml`**
```yaml
services:
  - type: web
    name: perde
    env: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    disk:
      name: sqlite-data
      mountPath: /data
      sizeGB: 1
    envVars:
      - key: DATABASE_URL
        value: /data/perde.db
      - key: RESEND_API_KEY
        sync: false
      - key: JWT_SECRET
        generateValue: true
      - key: APP_URL
        sync: false
```

- SQLite file lives at `/data/perde.db` on the persistent disk
- Set `RESEND_API_KEY` and `APP_URL` manually in Render dashboard
- Free tier is sufficient for 2–3 users

---

## 13. Out of Scope (for now)

- Real-time collaboration (WebSocket) — not needed, conflict detection is enough
- Markdown or rich text rendering
- Story visibility settings (public/private)
- User profile pages
- Mobile app
- Pagination (commit history or story list) — not needed at this scale
