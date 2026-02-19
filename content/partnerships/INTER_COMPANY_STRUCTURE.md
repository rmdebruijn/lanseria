# Inter-Company Entity Structure

**Document Date:** 2026-02-18
**Status:** Working draft — ownership percentages to be confirmed in shareholders agreements

---

## 1. Entity Hierarchy

```
Smart City Lanseria DevCo (Pty) Ltd  ("DevCo")
│
├── Shareholders:
│   ├── Anduza [Siza's company]        — controlling shareholder
│   ├── NexusNovus Capital B.V.        — holds Mark + Rutger interest
│   └── (Shareholders Agreement required)
│
├── 100%  ──►  Catalytic Assets (Pty) Ltd  ("CA")
│              │
│              ├── 90%  NWL (Pty) Ltd
│              │        (Siza sells 90% to CA, 10% to CrossPoint)
│              │
│              ├── 100% LanRED (Pty) Ltd
│              │
│              ├── 5%   Timberworx (Pty) Ltd
│              │
│              └── 80%  Cradle Cloud [SPV]
│
└── LLC interest (via DevCo):
    └── DevCo holds the combined R+M+S shares in LLC (75%)
        (Rutger, Mark, Siza moved their LLC stakes to DevCo)

LLC (Lanseria Landowners Consortium)
├── 25%  Eckhardt  (direct — personal, split from VanSquare 50%)
├── 75%  DevCo     (combined R+M+S shares)
└── Note: M+E currently hold 50% via VanSquare — needs split
          so E holds his 25% personally for LLC
```

---

## 2. LLC Ownership Detail

| Shareholder | Original % | Restructured Holding | Vehicle |
|---|---|---|---|
| Rutger | 25% | Moved to DevCo | NexusNovus Capital B.V. → DevCo → LLC |
| Mark | 25% | Moved to DevCo | NexusNovus Capital B.V. → DevCo → LLC |
| Siza | 25% | Moved to DevCo | Anduza [entity] → DevCo → LLC |
| Eckhardt | 25% | **Remains direct** | Personal (split from VanSquare 50%) |

**Note:** M+E currently hold 50% via VanSquare. Needs to be split so Eckhardt holds his 25% personally for LLC purposes. Mark's share routes through NexusNovus → DevCo.

---

## 3. NWL Ownership Mechanics

| Party | Stake | Source |
|---|---|---|
| Catalytic Assets | 90% | Siza sells her 90% to CA (per JDA Annexure A-2) |
| CrossPoint | 10% | Siza sells remaining 10% to CrossPoint |

---

## 4. Catalytic Assets — Portfolio

| Project Vehicle | CA Stake | Notes |
|---|---|---|
| NWL (Pty) Ltd | 90% | Water treatment — Lanseria |
| LanRED (Pty) Ltd | 100% | Renewable energy — Lanseria |
| Timberworx (Pty) Ltd | 5% | Timber / construction |
| Cradle Cloud [SPV] | 80% | Sovereign AI data centre |

---

## 5. Agreements Required

| # | Agreement | Parties | Purpose | Status |
|---|---|---|---|---|
| 1 | **DevCo Shareholders Agreement** | Anduza (Siza), NexusNovus (Mark + Rutger) | Govern DevCo — voting, board, distributions, deadlock | **Not yet drafted** |
| 2 | **CA Share Purchase — NWL 90%** | CA (buyer), Siza (seller) | Siza sells 90% NWL to CA | **Linked to JDA A-2** |
| 3 | **CrossPoint Sale — NWL 10%** | Siza (seller), CrossPoint (buyer) | Siza sells 10% NWL to CrossPoint | **Not yet drafted** |
| 4 | **LLC Cession / Transfer** | R, M, S → DevCo | Transfer of R+M+S LLC shares to DevCo | **Not yet drafted** |
| 5 | **CA Subscription — Cradle Cloud** | CA (subscriber), Cradle Cloud SPV | CA takes 80% equity in Cradle Cloud | **Not yet drafted** |
| 6 | **VanSquare Split — LLC** | Eckhardt, Mark | Split VanSquare 50% into E personal 25% + M via DevCo 25% | **Not yet drafted** |

---

## 6. Key Dependencies

- DevCo Shareholders Agreement must be in place before LLC cession can execute
- NWL share purchase from Siza is governed by JDA Annexure A-2 terms
- VanSquare 50% must be split so Eckhardt holds his 25% LLC personally
- CA's Cradle Cloud 80% stake linked to Cradle Cloud SPV formation
