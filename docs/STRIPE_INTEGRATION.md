# 🔷 Stripe Integration Guide for inframe

## Overview
This guide explains how to integrate Stripe Metered Billing into inframe to charge companies based on the number of employees they track.

---

## 📊 Your Stripe Configuration

Add these environment variables to **Render** (NOT in code):

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | From Stripe Dashboard → Developers → API Keys |
| `STRIPE_PRICE_ID_BASIC` | Basic plan price ID (starts with `price_`) |
| `STRIPE_PRICE_ID_PRO` | Pro plan price ID (starts with `price_`) |
| `STRIPE_WEBHOOK_SECRET` | From Stripe Webhooks (starts with `whsec_`) |

> ⚠️ **NEVER commit API keys to Git!** Always use environment variables.

---

## 🔗 Webhook Setup

1. Go to [Stripe Dashboard → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click **+ Add endpoint**
3. Enter: `https://employee-tracker-up30.onrender.com/api/stripe/webhook`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
5. Copy the **Signing Secret** and add to Render as `STRIPE_WEBHOOK_SECRET`

---

## 📋 Billing Model

| Plan | Price | Max Employees |
|------|-------|---------------|
| **Free** | $0 | 5 employees |
| **Basic** | $5/user/month | Auto-Synced |
| **Pro** | $8.99/user/month | Auto-Synced |

## 🔄 Real-time Usage Sync (New!)

No manual configuration needed! The system is standard compliant:

1.  **Usage Updates**: Automatically adds/removes users from the invoice the moment you Invite/Delete an employee.
2.  **Smart IDs**: You can use either `price_...` OR `prod_...` IDs. The system auto-resolves them.
3.  **Billing Type**: Works with both **Per-seat (Licensed)** and **Metered** billing types automatically.

---

## 🧪 Test Cards

| Card Number | Result |
|-------------|--------|
| `4242 4242 4242 4242` | ✅ Success |
| `4000 0000 0000 0002` | ❌ Declined |

Use any future date for expiry and any 3 digits for CVC.
