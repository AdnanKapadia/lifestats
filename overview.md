# Food & Fitness Tracker (Personal PWA)

## Goal

Build a **personal food and fitness tracking app** that feels similar to premium apps (e.g. MyFitnessPal) but is **free for personal use**, runs **without the App Store**, and works reliably on iPhone via a web app.

The app prioritizes:

* Fast logging
* Reasonable nutrition accuracy
* Long-term data persistence (cloud)
* Minimal platform friction

---

## Platform Choice

### Frontend

* **Progressive Web App (PWA)**
* Installed via: Safari → Share → *Add to Home Screen*
* Runs full-screen like a native app
* No App Store submission
* No weekly expiration or signing

### Backend / Cloud

* **Supabase (free tier)**

  * PostgreSQL database
  * Authentication
  * API access
* Frontend hosted on **Vercel / Cloudflare Pages / Netlify**

---

## Core Features

### 1. Food Logging

* Search-based food entry using:

  * **USDA FoodData Central** (primary)
  * **Open Food Facts** (secondary, packaged foods / barcode)
* Auto-fill calories and macros
* Custom foods allowed and saved for future use

### 2. Photo-Based Portion Estimation

**Goal:** Reduce friction when logging food by estimating portions from photos.

#### Approach

* User takes a photo of their meal
* Photo is sent to a backend API
* Backend calls **GPT Vision API** to:

  * Identify foods
  * Estimate portion sizes with uncertainty
* App shows:

  * Suggested portions (grams or servings)
  * Calorie + macro range
* User confirms or adjusts via slider

#### Design Principles

* Estimates are *assistive*, not authoritative
* Always include user confirmation
* Save user corrections to improve future estimates

#### Cost Expectations

* ~4 photos/day
* Estimated cost: **<$1–$5 per month** depending on model choice

---

## Data Storage

### Cloud-First Model

* All data stored in Supabase (Postgres)
* Benefits:

  * Survives phone changes
  * Accessible from phone + laptop
  * Easy backups

### Key Tables (High Level)

* users
* foods (cached from USDA / OFF + custom)
* meals
* meal_items (food + quantity)
* workouts (optional)
* weights / body metrics (optional)

---

## Fitness Tracking (Optional / Phase 2)

* Manual workout logging
* Simple schemas (exercise, sets, reps, weight or duration)
* Trend visualization
* No HealthKit dependency

---

## Non-Goals (Intentional)

* No App Store release
* No HealthKit integration (for now)
* No offline-first complexity
* No enterprise-scale user management

---

## Tech Stack Summary

**Frontend:**

* React / Next.js (or similar)
* PWA manifest
* Camera input via browser

**Backend:**

* Lightweight API (Next.js API routes or Supabase Edge Functions)
* GPT Vision for photo understanding
* USDA + Open Food Facts APIs

**Database:**

* Supabase Postgres (free tier)

---

## Why This Approach

* Avoids Apple developer friction
* Cheap to run
* Fast to iterate
* Good enough accuracy with user-in-the-loop corrections
* Easy to evolve into native later if desired

---

## MVP Definition

The project is successful if:

* Food can be logged in under ~10 seconds
* Photo-based estimation works "well enough" for daily use
* Data persists reliably
* The app is pleasant to use on iPhone

---

## Future Extensions

* Barcode scanning
* Smarter personalization of portion estimates
* Native app wrapper if desired
* Advanced analytics and trends

---

**Status:** Ready for implementation
