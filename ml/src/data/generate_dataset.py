"""
BhoomiRakshak — synthetic dataset generator (rev 2)

Fixes the five defects found in the 2026-08-23 audit of land_acquisition_dataset.csv:
  1. no leakage column exposed to the model (`latent_risk` is dropped from the feature set)
  2. coordinates are drawn from real district centroids + jitter
  3. every documented delay driver carries real signal (approvals, title, ownership, stage dwell,
     clearances, compensation gap) so SHAP surfaces what the problem statement names
  4. companion tables generated: risk_history, status_log, officers
  5. label means "will become overdue": closed projects are labelled and used for training,
     ongoing projects are unlabelled and are what the system scores

Outputs (ml/data/):
    projects.csv        900 rows  (600 closed = training, 300 ongoing = scoring)
    risk_history.csv    5 snapshots per project
    status_log.csv      desk-level entry/exit timestamps
    officers.csv        seeded accounts
"""
from __future__ import annotations
import numpy as np, pandas as pd, datetime as dt, hashlib, pathlib

SEED = 20260823
REF_DATE = dt.date(2026, 8, 23)
N_CLOSED, N_ONGOING = 600, 300
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- reference data
# (state, district, census state code, district code, centroid lat, centroid lon)
DISTRICTS = [
    ("Chhattisgarh", "Bilaspur", "22", "014", 22.08, 82.15),
    ("Chhattisgarh", "Durg", "22", "009", 21.19, 81.28),
    ("Chhattisgarh", "Korba", "22", "018", 22.35, 82.68),
    ("Chhattisgarh", "Raipur", "22", "002", 21.25, 81.63),
    ("Karnataka", "Belagavi", "29", "022", 15.85, 74.50),
    ("Karnataka", "Bengaluru Urban", "29", "007", 12.97, 77.59),
    ("Karnataka", "Mysuru", "29", "018", 12.30, 76.64),
    ("Karnataka", "Tumakuru", "29", "009", 13.34, 77.10),
    ("Madhya Pradesh", "Bhopal", "23", "004", 23.26, 77.41),
    ("Madhya Pradesh", "Gwalior", "23", "033", 26.22, 78.18),
    ("Madhya Pradesh", "Indore", "23", "016", 22.72, 75.86),
    ("Madhya Pradesh", "Jabalpur", "23", "028", 23.18, 79.99),
    ("Maharashtra", "Mumbai Suburban", "27", "001", 19.13, 72.87),
    ("Maharashtra", "Nagpur", "27", "025", 21.15, 79.09),
    ("Maharashtra", "Nashik", "27", "037", 20.00, 73.79),
    ("Maharashtra", "Pune", "27", "013", 18.52, 73.86),
    ("Odisha", "Cuttack", "21", "012", 20.46, 85.88),
    ("Odisha", "Ganjam", "21", "019", 19.39, 84.79),
    ("Odisha", "Khordha", "21", "005", 20.18, 85.62),
    ("Odisha", "Sambalpur", "21", "026", 21.47, 83.97),
    ("Tamil Nadu", "Chennai", "33", "014", 13.08, 80.27),
    ("Tamil Nadu", "Coimbatore", "33", "023", 11.02, 76.96),
    ("Tamil Nadu", "Madurai", "33", "031", 9.93, 78.12),
    ("Tamil Nadu", "Tiruchirappalli", "33", "045", 10.79, 78.70),
    ("Telangana", "Hyderabad", "36", "003", 17.39, 78.49),
    ("Telangana", "Karimnagar", "36", "019", 18.44, 79.13),
    ("Telangana", "Nizamabad", "36", "027", 18.67, 78.09),
    ("Telangana", "Warangal", "36", "011", 17.97, 79.59),
    ("Uttar Pradesh", "Kanpur Nagar", "09", "015", 26.45, 80.33),
    ("Uttar Pradesh", "Lucknow", "09", "002", 26.85, 80.95),
    ("Uttar Pradesh", "Prayagraj", "09", "044", 25.44, 81.85),
    ("Uttar Pradesh", "Varanasi", "09", "031", 25.32, 82.97),
]
STATE_ABBR = {"Chhattisgarh": "CG", "Karnataka": "KA", "Madhya Pradesh": "MP",
              "Maharashtra": "MH", "Odisha": "OD", "Tamil Nadu": "TN",
              "Telangana": "TG", "Uttar Pradesh": "UP"}

PROJECT_TYPES = ["National Highway", "State Highway", "Railway Line", "Urban Metro",
                 "Irrigation Canal", "Power Transmission", "Industrial Corridor",
                 "Airport Expansion"]
AGENCY_FOR = {"National Highway": "NHAI", "State Highway": "State PWD",
              "Railway Line": "Indian Railways", "Urban Metro": "Metro Rail Corp",
              "Irrigation Canal": "State Irrigation Dept", "Power Transmission": "POWERGRID",
              "Industrial Corridor": "State Industrial Corp",
              "Airport Expansion": "Airports Authority of India"}
# projects that are structurally harder to acquire land for (linear, multi-village, urban)
TYPE_FRICTION = {"National Highway": 0.55, "State Highway": 0.40, "Railway Line": 0.60,
                 "Urban Metro": 0.70, "Irrigation Canal": 0.50, "Power Transmission": 0.30,
                 "Industrial Corridor": 0.65, "Airport Expansion": 0.75}

STAGES = ["SIA Completed", "Section 11 Notification Issued", "Award Declared",
          "Compensation Disbursement", "R&R Implementation", "Possession Taken"]
# how much friction is still ahead of you at each stage
STAGE_EXPOSURE = {"SIA Completed": 0.85, "Section 11 Notification Issued": 0.75,
                  "Award Declared": 0.55, "Compensation Disbursement": 0.45,
                  "R&R Implementation": 0.30, "Possession Taken": 0.10}
TITLE_RISK = {"Clear": 0.0, "Partial": 0.45, "Disputed": 1.0}
CLEARANCE = ["Not Required", "Obtained", "Applied", "Pending"]
CLEARANCE_RISK = {"Not Required": 0.0, "Obtained": 0.0, "Applied": 0.45, "Pending": 1.0}
DISPUTE_STAGE_RISK = {"None": 0.0, "Resolved": 0.15, "Filed": 0.55,
                      "Under Hearing": 0.80, "Stayed by Court": 1.0}
# circle rate per acre in lakhs, by district tier
URBAN = {"Bengaluru Urban", "Chennai", "Hyderabad", "Mumbai Suburban", "Pune",
         "Lucknow", "Bhopal", "Indore", "Nagpur", "Raipur"}

TALUK_SUFFIX = ["North", "South", "East", "West"]
VILLAGE_STEM = ["Rampur", "Kothapalli", "Ganeshpura", "Bhimnagar", "Sultanpur", "Devgaon",
                "Chandrapalli", "Narsapur", "Basavanahalli", "Mallapuram", "Amrapur", "Jaitpur",
                "Kesarpur", "Lakshmipura", "Madhavgarh", "Nandgaon", "Peddapalli", "Raghunathpur",
                "Shivnagar", "Tarapur", "Uttanahalli", "Veerapuram", "Yellapur", "Zamania"]
TALUKS_PER_DISTRICT, VILLAGES_PER_TALUK = 4, 6


def build_admin_units() -> pd.DataFrame:
    """State -> District -> Taluk -> Village, with the counts the statistics panel needs."""
    rows = []
    for state, district, sc, dc, clat, clon in DISTRICTS:
        n = 0
        for t in range(TALUKS_PER_DISTRICT):
            taluk = f"{district} {TALUK_SUFFIX[t]}"
            for v in range(VILLAGES_PER_TALUK):
                n += 1
                urban = district in URBAN
                plots = int(rng.integers(1800, 9000) if urban else rng.integers(400, 3200))
                rows.append({
                    "state": state, "state_code": sc,
                    "district": district, "district_code": dc,
                    "taluk": taluk, "taluk_code": f"{t + 1:02d}",
                    "village": f"{VILLAGE_STEM[(t * VILLAGES_PER_TALUK + v) % len(VILLAGE_STEM)]}"
                               f"{'' if v < len(VILLAGE_STEM) else v}",
                    "village_code": f"{n:03d}",
                    "latitude": round(float(clat + rng.normal(0, 0.09)), 5),
                    "longitude": round(float(clon + rng.normal(0, 0.09)), 5),
                    "no_plots": plots,
                    "no_khatiyans": int(plots * rng.uniform(0.55, 0.85)),
                    "no_tenants": int(plots * rng.uniform(0.10, 0.40)),
                    "ri_circle": f"{district} RI Circle {((n - 1) // 3) + 1}",
                    "revenue_inspector": f"RI-{sc}{dc}-{((n - 1) // 3) + 1:02d}",
                })
    df = pd.DataFrame(rows)
    # one Tehsildar per taluk; RI circles grouped ~3 villages each
    df["tehsildar"] = df.apply(lambda r: f"Tehsildar {r.taluk}", axis=1)
    return df


def ulpin(state_code: str, district_code: str, village_code: str) -> str:
    """14-digit DILRMP-style id: state(2)-district(3)-village(3)-parcel(6)."""
    return f"{state_code}-{district_code}-{village_code}-{rng.integers(1, 999999):06d}"


def rand_date(lo: dt.date, hi: dt.date) -> dt.date:
    return lo + dt.timedelta(days=int(rng.integers(0, (hi - lo).days)))


# ---------------------------------------------------------------- officers
def build_officers() -> pd.DataFrame:
    rows = []
    for state, district, *_ in DISTRICTS:
        ab = STATE_ABBR[state]
        yr = int(rng.integers(2021, 2026))
        rows.append({
            "officer_id": f"{ab}-LAO-{yr}-{rng.integers(100, 999):04d}",
            "full_name": f"LAO {district}", "role": "officer",
            "state": state, "district": district,
            "designation": "Land Acquisition Officer / SDM",
        })
    for state in sorted(STATE_ABBR):
        ab = STATE_ABBR[state]
        rows.append({
            "officer_id": f"{ab}-DC-{int(rng.integers(2018, 2024))}-{rng.integers(10, 99):04d}",
            "full_name": f"Collector {state}", "role": "admin",
            "state": state, "district": "ALL", "designation": "District Collector",
        })
    rows.append({"officer_id": "IN-NDC-2020-0001", "full_name": "National Nodal Officer",
                 "role": "admin", "state": "ALL", "district": "ALL",
                 "designation": "State Nodal Officer (MoRD)"})
    df = pd.DataFrame(rows)
    # demo password is the officer_id lowercased; replace with bcrypt at seed time
    df["password_seed"] = df.officer_id.str.lower()
    df["password_sha256_demo"] = df.password_seed.map(
        lambda p: hashlib.sha256(p.encode()).hexdigest())
    return df


# ---------------------------------------------------------------- projects
def build_projects(officers: pd.DataFrame, admin: pd.DataFrame) -> pd.DataFrame:
    lao = officers[officers.role == "officer"].set_index("district").officer_id.to_dict()
    villages = {d: g.reset_index(drop=True) for d, g in admin.groupby("district")}
    rows = []
    for i in range(N_CLOSED + N_ONGOING):
        closed = i < N_CLOSED
        state, district, sc, dc, clat, clon = DISTRICTS[int(rng.integers(len(DISTRICTS)))]
        ptype = PROJECT_TYPES[int(rng.integers(len(PROJECT_TYPES)))]

        # ---- geography: real village coordinates, so pins sit inside their own district ----
        vg = villages[district]
        vrow = vg.iloc[int(rng.integers(len(vg)))]
        taluk, village, village_code = vrow.taluk, vrow.village, vrow.village_code
        lat = round(float(vrow.latitude + rng.normal(0, 0.012)), 5)
        lon = round(float(vrow.longitude + rng.normal(0, 0.012)), 5)

        land_area = round(float(np.clip(rng.lognormal(3.6, 0.8), 4, 900)), 1)
        landowners = int(np.clip(rng.poisson(land_area * 1.4) + 3, 3, 2600))
        families = int(np.clip(landowners * rng.uniform(0.9, 1.9), 3, 4200))
        # fragmentation: owners per acre — the litigation-propensity driver
        fragmentation = round(landowners / max(land_area, 1.0), 3)

        title = str(rng.choice(["Clear", "Partial", "Disputed"], p=[0.55, 0.31, 0.14]))
        own_disputes = int(rng.poisson(0.4 + 3.2 * TITLE_RISK[title] + fragmentation * 0.25))
        own_flag = own_disputes > 0

        stage = STAGES[int(rng.integers(len(STAGES)))]
        days_in_stage = int(np.clip(rng.exponential(70) * (1 + STAGE_EXPOSURE[stage]), 3, 1400))
        pending_clearances = int(rng.poisson(1.1 + 2.0 * STAGE_EXPOSURE[stage]))
        env = str(rng.choice(CLEARANCE, p=[0.22, 0.34, 0.24, 0.20]))
        forest = str(rng.choice(CLEARANCE, p=[0.46, 0.26, 0.16, 0.12]))

        # ---- compensation, with a real circle-rate benchmark (defect 4) ----
        base_rate = (rng.uniform(38, 95) if district in URBAN else rng.uniform(6, 32))
        circle_rate = round(float(base_rate), 2)                       # lakhs/acre
        multiplier = 2.0 if district in URBAN else 4.0                 # LARR Sch. I factor
        fair_value = circle_rate * multiplier * land_area
        # what was actually sanctioned may fall short of the fair benchmark
        adequacy = float(np.clip(rng.beta(6, 2.2), 0.35, 1.15))
        sanctioned = round(fair_value * adequacy, 2)
        comp_gap_pct = round(max(0.0, (fair_value - sanctioned) / fair_value) * 100, 2)

        disbursed_pct = round(float(np.clip(rng.beta(2.1, 2.0) * 100, 0, 100)), 1)
        disbursed = round(sanctioned * disbursed_pct / 100, 2)
        # a wide gap drives appeals and refusals
        appeals = int(rng.poisson(0.2 + comp_gap_pct / 14))
        comp_dispute = appeals > 0

        legal_disputes = int(rng.poisson(0.25 + 1.9 * TITLE_RISK[title]
                                         + comp_gap_pct / 30 + own_disputes * 0.22))
        if legal_disputes:
            dstage = str(rng.choice(["Filed", "Under Hearing", "Stayed by Court", "Resolved"],
                                    p=[0.30, 0.34, 0.22, 0.14]))
            days_since = int(np.clip(rng.exponential(220), 5, 1800))
        else:
            dstage, days_since = "None", 0
        stay = dstage == "Stayed by Court"

        rehab_approved = bool(rng.random() < 0.72)
        rehab_pct = round(float(np.clip(rng.beta(2.0, 2.2) * 100 * (1.0 if rehab_approved else 0.45),
                                        0, 100)), 1)
        site_ready = bool(rng.random() < 0.30 + rehab_pct / 220)
        resettled = int(families * rehab_pct / 100 * rng.uniform(0.7, 1.0))

        # ---- latent risk: every documented driver contributes (defect 3) ----
        latent = (
            0.20 * (1 - disbursed_pct / 100)                       # compensation lag
            + 0.14 * (comp_gap_pct / 60)                           # compensation ADEQUACY gap
            + 0.15 * min(legal_disputes / 4, 1.0)                  # litigation volume
            + 0.09 * DISPUTE_STAGE_RISK[dstage]                    # litigation severity
            + 0.09 * (1 - rehab_pct / 100)                         # R&R friction
            + 0.07 * TITLE_RISK[title]                             # title clarity
            + 0.06 * min(own_disputes / 4, 1.0)                    # ownership fragmentation
            + 0.06 * min(pending_clearances / 5, 1.0)              # administrative bottleneck
            + 0.05 * min(days_in_stage / 500, 1.0)                 # stage dwell / stuck file
            + 0.04 * max(CLEARANCE_RISK[env], CLEARANCE_RISK[forest])
            + 0.03 * STAGE_EXPOSURE[stage]
            + 0.02 * TYPE_FRICTION[ptype]
        )
        latent = float(np.clip(latent + rng.normal(0, 0.045), 0, 1))

        # normalised driver intensities (0-1 each) so no driver is structurally favoured
        intensity = {
            "Compensation Disbursal": 0.5 * (1 - disbursed_pct / 100) + 0.5 * min(comp_gap_pct / 45, 1.0),
            "Legal Dispute": 0.5 * min(legal_disputes / 4, 1.0) + 0.5 * DISPUTE_STAGE_RISK[dstage],
            "Rehabilitation (R&R)": 0.88 * (1 - rehab_pct / 100),
            "Ownership / Title": 0.5 * TITLE_RISK[title] + 0.5 * min(own_disputes / 4, 1.0),
            "Administrative Approval": 1.30 * (0.4 * min(pending_clearances / 5, 1.0)
            + 0.3 * max(CLEARANCE_RISK[env], CLEARANCE_RISK[forest])
            + 0.3 * min(days_in_stage / 500, 1.0)),
        }
        top_driver = max(intensity, key=lambda k: intensity[k] + rng.normal(0, 0.04))

        if closed:
            notif = rand_date(dt.date(2019, 1, 1), dt.date(2023, 12, 31))
            planned = int(rng.integers(420, 1000))
            expected = notif + dt.timedelta(days=planned)
            slip = None          # assigned in the second pass, once latent is calibrated
            actual = None
            is_delayed = delay_stage = hist_days = act_str = None
        else:
            notif = rand_date(dt.date(2024, 6, 1), REF_DATE)
            planned = int(rng.integers(420, 1000))
            expected = notif + dt.timedelta(days=planned)
            if expected <= REF_DATE:                    # ongoing must complete in the future
                expected = REF_DATE + dt.timedelta(days=int(rng.integers(45, 900)))
            is_delayed = delay_stage = hist_days = act_str = slip = None
            expected = expected  # kept future by the guard above

        rows.append({
            "ulpin": ulpin(sc, dc, village_code),
            "project_name": f"{ptype} - {district} Stretch {int(rng.integers(1, 9))}",
            "project_type": ptype, "implementing_agency": AGENCY_FOR[ptype],
            "state": state, "district": district, "taluk": taluk, "village": village,
            "latitude": lat, "longitude": lon,
            "notification_date": notif.isoformat(),
            "expected_completion_date": expected.isoformat(),
            "actual_completion_date": act_str,
            "land_area_acres": land_area, "no_affected_families": families,
            "no_landowners": landowners, "ownership_fragmentation_index": fragmentation,
            "ownership_dispute_flag": own_flag, "no_ownership_disputes": own_disputes,
            "title_clarity_status": title,
            "circle_rate_per_acre_lakhs": circle_rate,
            "compensation_fair_value_lakhs": round(fair_value, 2),
            "compensation_amount_sanctioned_lakhs": sanctioned,
            "compensation_amount_disbursed_lakhs": disbursed,
            "compensation_disbursed_pct": disbursed_pct,
            "compensation_gap_pct": comp_gap_pct,
            "compensation_dispute_flag": comp_dispute,
            "no_compensation_appeals": appeals,
            "no_legal_disputes": legal_disputes, "legal_dispute_stage": dstage,
            "court_stay_flag": stay, "days_since_dispute_filed": days_since,
            "rehab_plan_approved_flag": rehab_approved, "rehab_progress_pct": rehab_pct,
            "resettlement_site_ready_flag": site_ready, "no_families_resettled": resettled,
            "approval_stage": stage, "days_in_current_stage": days_in_stage,
            "no_pending_clearances": pending_clearances,
            "environmental_clearance_status": env, "forest_clearance_status": forest,
            "is_closed_project": closed,
            "historical_delay_days": hist_days,
            "is_delayed": is_delayed, "delay_stage": delay_stage,
            "assigned_field_officer_id": lao[district],
            "latent_risk_audit": round(latent, 4),   # NEVER a model feature — audit/debug only
            "planned_duration_days": planned,
            "top_driver_audit": top_driver,
        })
    df = pd.DataFrame(rows)
    return calibrate_labels(df)


def calibrate_labels(df: pd.DataFrame, target_delayed: float = 0.52) -> pd.DataFrame:
    """Turn latent risk into a slip in days, centred so ~half of closed projects overrun."""
    cut = df.loc[df.is_closed_project, "latent_risk_audit"].quantile(1 - target_delayed)
    m = df.is_closed_project
    slip = ((df.loc[m, "latent_risk_audit"] - cut) * 1400
            + rng.normal(0, 55, m.sum())).round().astype(int).clip(lower=0)
    df.loc[m, "historical_delay_days"] = slip
    df.loc[m, "is_delayed"] = slip > 30
    df.loc[m, "delay_stage"] = np.where(slip > 30, df.loc[m, "top_driver_audit"], "Not Applicable")
    df.loc[m, "actual_completion_date"] = [
        (dt.date.fromisoformat(e) + dt.timedelta(days=int(s))).isoformat()
        for e, s in zip(df.loc[m, "expected_completion_date"], slip)]
    return df


# ---------------------------------------------------------------- companion tables
def build_risk_history(projects: pd.DataFrame, n_snap: int = 5) -> pd.DataFrame:
    rows = []
    for r in projects.itertuples():
        end = REF_DATE if not r.is_closed_project else dt.date.fromisoformat(
            r.actual_completion_date)
        trend = rng.normal(0, 0.055)      # some projects improve, some deteriorate
        for k in range(n_snap):
            back = (n_snap - 1 - k) * 30
            score = float(np.clip(r.latent_risk_audit - trend * (n_snap - 1 - k)
                                  + rng.normal(0, 0.02), 0.01, 0.99))
            rows.append({
                "ulpin": r.ulpin,
                "snapshot_date": (end - dt.timedelta(days=back)).isoformat(),
                "risk_score": round(score, 4),
                "compensation_disbursed_pct": round(max(0.0, r.compensation_disbursed_pct
                                                        - back * 0.045), 1),
                "rehab_progress_pct": round(max(0.0, r.rehab_progress_pct - back * 0.035), 1),
                "days_in_current_stage": max(1, r.days_in_current_stage - back),
            })
    return pd.DataFrame(rows)


DESKS = ["Tehsildar", "Land Acquisition Officer", "Revenue Divisional Officer",
         "District Collector", "Legal Cell", "Treasury / PFMS", "R&R Cell"]


def build_status_log(projects: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in projects.itertuples():
        cursor = dt.date.fromisoformat(r.notification_date)
        n = int(rng.integers(3, len(DESKS) + 1))
        picked = list(rng.choice(DESKS, size=n, replace=False))
        for j, desk in enumerate(picked):
            last = j == n - 1
            dwell = (r.days_in_current_stage if last
                     else int(np.clip(rng.exponential(38) * (1 + r.latent_risk_audit),
                                      2, 400)))
            entered = cursor
            exited = None if last else cursor + dt.timedelta(days=dwell)
            rows.append({
                "ulpin": r.ulpin, "desk": desk, "stage": r.approval_stage,
                "entered_on": entered.isoformat(),
                "exited_on": exited.isoformat() if exited else None,
                "days_at_desk": dwell, "is_current": last,
            })
            if exited:
                cursor = exited
    return pd.DataFrame(rows)


RELATIONS = ["Son", "Daughter", "Widow", "Brother", "Sister", "Grandson",
             "Adopted Son", "Nephew", "Step-son"]
PROOF = ["Documented", "Undocumented", "Contested"]
PROOF_DOCS = {
    "Documented": ["Registered Will", "Mutation Entry (RoR)", "Legal Heir Certificate",
                   "Succession Certificate", "Partition Deed"],
    "Undocumented": ["Oral claim only", "Panchayat attestation", "Affidavit, unverified"],
    "Contested": ["Competing Will produced", "Disputed mutation", "Civil suit pending"],
}
VERIFY = {"Documented": "Verified", "Undocumented": "Pending Verification",
          "Contested": "Referred to Revenue Court"}


def build_succession_claims(projects: pd.DataFrame) -> pd.DataFrame:
    """Bloodline / heirship register.

    This is an APPLICATION feature, not a model input: officers record who claims to be the
    owner, their blood relation, and whether the claim carries proof. The risk flag below is
    RULE-BASED and deterministic — it is never trained, and none of these columns is fed to
    XGBoost. Rows here are demo seed data for the Project Detail succession panel.
    """
    rows = []
    for r in projects.itertuples():
        # succession only arises on a subset of parcels
        if rng.random() > (0.28 + 0.30 * (r.title_clarity_status != "Clear")):
            continue
        n_claims = int(rng.integers(1, 5))
        share_left = 100.0
        for k in range(n_claims):
            proof = str(rng.choice(PROOF, p=[0.52, 0.31, 0.17]))
            share = round(share_left / (n_claims - k) * float(rng.uniform(0.6, 1.4)), 1)
            share = float(min(share, share_left)); share_left -= share
            rows.append({
                "claim_id": f"SC-{r.ulpin}-{k + 1}",
                "ulpin": r.ulpin,
                "claimant_name": f"Claimant {k + 1}",
                "relation_to_recorded_owner": str(rng.choice(RELATIONS)),
                "blood_relation": bool(rng.random() < 0.82),
                "proof_status": proof,
                "proof_document": str(rng.choice(PROOF_DOCS[proof])),
                "claimed_share_pct": share,
                "verification_status": VERIFY[proof],
                "claim_filed_on": r.notification_date,
            })
    df = pd.DataFrame(rows)
    return df


def succession_risk(claims: pd.DataFrame, projects: pd.DataFrame) -> pd.DataFrame:
    """Deterministic RULE, not a model. Mirrors what the backend service will compute."""
    if claims.empty:
        return pd.DataFrame(columns=["ulpin", "heir_claim_count", "undocumented_claims",
                                     "contested_claims", "share_total_pct",
                                     "succession_risk_band", "succession_reason"])
    g = claims.groupby("ulpin")
    out = pd.DataFrame({
        "heir_claim_count": g.size(),
        "undocumented_claims": g.proof_status.apply(lambda s: (s == "Undocumented").sum()),
        "contested_claims": g.proof_status.apply(lambda s: (s == "Contested").sum()),
        "share_total_pct": g.claimed_share_pct.sum().round(1),
    }).reset_index()

    def band(r):
        if r.contested_claims > 0 or r.share_total_pct > 105:
            return "High", ("Competing heirship claims over the same parcel"
                            if r.contested_claims else
                            f"Claimed shares total {r.share_total_pct}% — exceeds the parcel")
        if r.undocumented_claims > 0:
            return "Medium", (f"{r.undocumented_claims} heir claim(s) without documentary proof "
                              "— mutation not established")
        if r.heir_claim_count > 2:
            return "Medium", f"{r.heir_claim_count} heirs on one parcel — consent risk at award"
        return "Low", "All heirship claims documented"

    b = out.apply(band, axis=1, result_type="expand")
    out["succession_risk_band"], out["succession_reason"] = b[0], b[1]
    return out


# ---------------------------------------------------------------- project dependencies
def build_dependencies(projects: pd.DataFrame) -> pd.DataFrame:
    """Edges for cascading-impact awareness. Synthetic by construction — label it as such."""
    rows = []
    for (state, ptype), g in projects.groupby(["state", "project_type"]):
        ids = list(g.ulpin)
        rng.shuffle(ids)
        for a, b in zip(ids, ids[1:]):
            if rng.random() < 0.45:
                rows.append({"upstream_ulpin": a, "downstream_ulpin": b,
                             "dependency_type": "Contiguous stretch",
                             "note": f"{ptype} alignment continues into the next stretch"})
    # cross-type feeders: a corridor feeds the highways around it
    corr = projects[projects.project_type == "Industrial Corridor"]
    hw = projects[projects.project_type.isin(["National Highway", "State Highway"])]
    for r in corr.itertuples():
        peers = hw[hw.district == r.district]
        for q in peers.head(2).itertuples():
            rows.append({"upstream_ulpin": r.ulpin, "downstream_ulpin": q.ulpin,
                         "dependency_type": "Feeder connectivity",
                         "note": "Corridor access depends on this road stretch"})
    return pd.DataFrame(rows).drop_duplicates(subset=["upstream_ulpin", "downstream_ulpin"])


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    out = pathlib.Path(__file__).resolve().parents[3] / "ml" / "data"
    out.mkdir(parents=True, exist_ok=True)
    admin = build_admin_units()
    officers = build_officers()
    projects = build_projects(officers, admin)
    history = build_risk_history(projects)
    status = build_status_log(projects)
    claims = build_succession_claims(projects)
    srisk = succession_risk(claims, projects)
    deps = build_dependencies(projects)

    admin.to_csv(out / "admin_units.csv", index=False)
    officers.to_csv(out / "officers.csv", index=False)
    projects.to_csv(out / "projects.csv", index=False)
    history.to_csv(out / "risk_history.csv", index=False)
    status.to_csv(out / "status_log.csv", index=False)
    claims.to_csv(out / "succession_claims.csv", index=False)
    srisk.to_csv(out / "succession_risk.csv", index=False)
    deps.to_csv(out / "project_dependencies.csv", index=False)
    print(f"admin_units  {len(admin):5d}")
    print(f"claims       {len(claims):5d}  ({srisk.succession_risk_band.value_counts().to_dict() if len(srisk) else {}})")
    print(f"dependencies {len(deps):5d}")

    closed = projects[projects.is_closed_project]
    print(f"officers     {len(officers):5d}")
    print(f"projects     {len(projects):5d}  ({len(closed)} closed / "
          f"{len(projects) - len(closed)} ongoing)")
    print(f"risk_history {len(history):5d}")
    print(f"status_log   {len(status):5d}")
    print("\ndelayed rate (closed only):",
          round(closed.is_delayed.astype(bool).mean(), 3))
    print(closed[closed.is_delayed.astype(bool)].delay_stage.value_counts().to_string())
