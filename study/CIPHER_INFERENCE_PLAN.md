# Selection-robust clinical-harm bounds from the CIPHER corpus

Recorded 2026-09-20, before running the analysis. A new, additive study. It is the
first *inferential* use of the CIPHER corpus in this repository (the existing
`analyze_cipher_coverage.py` uses it only for a coverage audit) and it feeds the
clinical-impact certificate (`grrc.hospital_attack_model`) a real-data-derived
degradation input in place of an assumed one.

## Data

CIPHER v1.0.1 (`data/cipher/raw/cipher-v1.0.1.csv`, CC-BY; Straw, Tully, Dameff):
316 coded patient-harm records drawn from 36 real hospital-ransomware incident
reports, each with a clinical-impact score (1--10), a harm-onset time point, a
clinical specialty, and a technical domain. It is a **convenience sample of
publicly reported harms**, not a random or complete sample; unreported harms are
missing not at random. Naive shares are therefore biased, so we bound rather than
point-estimate.

## Method

1. Load and clean: coerce the impact score, normalise the coded time-point typo
   ("Firsy Day" -> "First Day"), and treat "All"/unspecified cells explicitly.
2. Map technical domains to the four modelled clinical services using the repo's
   existing `data/cipher/processed/domain_mapping.csv`: Health Records -> EHR,
   Laboratory Systems -> laboratory, ePrescribing -> pharmacy, Imaging -> imaging.
   All other domains (Hospital Infrastructure, Booking, Admin/Billing,
   Communications, Operating Rooms, Telemetry, "All") are kept as an explicit
   **unmodelled residual**, never dropped -- so the shares of the four services do
   not sum to one, which is the honest statement that the model omits real harm.
3. Observed quantity: among high-severity records (impact score >= tau, tau = 7),
   the share q_s of all high-severity harm attributable to service s.
4. **Partial-identification envelope** under bounded per-domain underreporting: the
   true high-severity count of any domain is at most (1 + gamma) times its observed
   count. With T the observed high-severity total,
   `q_s^hi = n_s(1+gamma) / (n_s(1+gamma) + (T - n_s))` (service s under-reported,
   others not) and `q_s^lo = n_s / (n_s + (1+gamma)(T - n_s))` (the reverse). At
   gamma = 0 both equal the observed share; the interval widens with gamma and stays
   in [0, 1]. Report the gamma-sensitivity curve (gamma in {0, 0.5, 1, 2}). This is
   the method core: an honest interval, not a point rate.
5. Integration: read each service's [q_s^lo, q_s^hi] at a chosen gamma as its
   degradation interval and re-run the clinical certificate, reporting how the
   certified minimum control portfolio changes versus the assumed intervals.

## Scope and limits

- CIPHER is reported harm, not incidence: q_s is a *relative* severity-attribution
  share among reported harms, read as a per-service degradation propensity given an
  impact-capable intrusion. It is not a probability estimated from a random sample.
- The bounded-underreporting assumption (a single gamma across domains) is a
  transparent worst-case device, not a fitted selection model; results are reported
  as a function of gamma, and gamma -> infinity is uninformative by construction.
- The domain -> service mapping is the repo's existing coverage mapping; unmodelled
  domains are retained as a residual, not discarded.
- Small counts (four services, tens of high-severity records each): the intervals
  are wide, which is the honest consequence and the point of bounding.
- Not a new theorem: partial identification is Manski's; the contribution is its
  first application to a coded cyber-incident harm corpus and the real-data
  grounding of the certificate's weakest input.

## Software and reporting

Pure-array kernel with no I/O, validated by a hand-computed oracle on a tiny
corpus, gamma-monotonicity and [0,1] containment checks, and rejection of invalid
inputs. Deterministic: re-running reproduces every CSV byte for byte. Record the
CIPHER hash and all inputs in a provenance manifest. Generate all note numbers from
the committed tables.
