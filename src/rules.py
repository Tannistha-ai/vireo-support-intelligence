"""Free rules baseline: regexes tolerant of typos/abbreviations. First match wins (order matters)."""
import re
RULES = [
 ("double_charge", r"charged twice|twice for one|double (payment|charge)|duplicate payment|two entries|deducted twice|paid twice"),
 ("paid_no_order", r"page failed after|failed (order )?after (i )?paid|deducted without|money (was )?(cut|deducted)|nothing shows in my account|payment (went|done).{0,30}no order|amount deducted|failed order after payment|no order (id|confirm)"),
 ("coupon_failed", r"coupon|promo|discount|\d+% off|voucher|code (not|isn|invalid|doesn)|cart says full price|full price"),
 ("invoice_issue", r"invoice|\bgst|gstin|bill with"),
 ("login_otp", r"\botp\b|login code|log ?in code|locked out|lockeed|cannot log ?in|can.?t log ?in|unable to log|not able to log|log ?in to my account|login (issue|problem)|sign.?in"),
 ("address_change", r"(change|update|edit|correct|wrong).{0,25}(address|pincode|pin code)|(address|pincode).{0,25}(wrong|change|correct|update)|wrong pin"),
 ("wrong_item", r"wrong (item|product|variant|colou?r|model)|received the wrong|different (product|item)"),
 ("damaged_in_transit", r"arrived damaged|damaged (in transit|on arrival|box|package|when)|box was (crushed|damaged|broken)|came (broken|damaged)|dented|transit damage"),
 ("cancellation", r"cancel|change of mind|stop the shipment|dont want (it|this)|don.?t want"),
 ("wifi_setup", r"wi-?fi|setup fails|2\.4 ?ghz"),
 ("device_dead", r"does absolutely nothing|unit (is )?dead|(won.?t|not|doesn.?t) (turn|switch|power)( on)?|dead on arrival|\bdoa\b|no power|completely dead|pressing the button"),
 ("fw_update_stuck", r"firmware|\bfw\b|update (stuck|hang|failed|prompt|froze)|progress bar|went dark|ota|spinning circle"),
 ("app_crash", r"app (keeps )?(crash|not open|won.?t open|closes|freez)|crash(es|ing)?\b|app (is )?(not|n.t) open|keeps closing|white screen|app.{0,15}(crash|opening)"),
 ("pairing_failure", r"pair|discoverable|device list|not (detect|see|find)|doesn.?t see|won.?t connect|not connect|disconnect|drops? (the )?connection|connection (drop|keeps)|losing (my )?phone|bluetooth|connects for a second|vanish"),
 ("not_charging", r"not charging|won.?t charge|(does|do)( )?n.?t charge|no charge|plugging in|not charge|case.{0,20}(led|light|dead|charge)|charging (case|port)|left bud won|right bud won|nothing on the case"),
 ("battery_drain", r"battery|drain|charge it twice|carge|last(s|ed)? (days|only)|backup|dropped to almost"),
 ("audio_one_side", r"one side|one (of them|earbud|bud)|(left|right).{0,15}(no sound|dead|silent|not working|no audio|only)|only (left|right|one)|just decoration|no audio at all|side has no audio"),
 ("mic_problem", r"\bmic\b|microphone|callers|can.?t hear me|muffled|voice (is )?(low|soft)|repeat myself"),
 ("audio_distortion", r"crackl|static|buzz|hiss|distort|badly tuned|radio|noise|fuzzy|tinny|hum\b"),
 ("display_touch", r"screen|touch|tap ten|swipe|display|unresponsive|dead pixel|flicker"),
 ("strap_broken", r"strap|band (snapped|broke|tear)|tearing|snapped|lug"),
 ("repair_status", r"service cent|repair|warranty claim|\brma\b|claim status|sent it for"),
 ("return_pickup", r"pick ?up|pkp|reverse pickup"),
 ("refund_delay", r"refund|money for the return|where is the money|money back|not credited|credited|money (hasn.?t|has not|didn.?t) come back|amount is nowhere|amount.{0,25}(nowhere|not (in|back))|returned .{0,20}(money|amount)"),
 ("not_delivered", r"not (been )?deliver|nothing in hand|haven.?t (receive|got)|not received|(still )?waiting for (my )?(order|package|something|parcel)|shipment|delay|lost in transit|courier|where is my (order|parcel|package)|in hand|tracking|dispatch|show up|not arrived|hasn.?t arrived"),
 ("compatibility_query", r"compatib|work with|will (this|it|the).{0,25}(talk|run|work|connect)|does .{0,30} work (with|on)|can i connect two|before i buy|support (ios|android|iphone)|survive a shower|waterproof|water.?resist|sweat|swim|rain"),
]
COMPILED = [(lbl, re.compile(p, re.I)) for lbl, p in RULES]

import difflib, collections
_VOCAB = None
NORM = None
def build_normalizer(messages, min_count=25):
    """Snap rare (probably misspelt) tokens to the nearest frequent word. Learned from the corpus itself."""
    global _VOCAB, NORM
    cnt = collections.Counter(w for m in messages for w in re.findall(r"[a-z]{4,}", m.lower()))
    _VOCAB = {w for w, c in cnt.items() if c >= min_count}
    cache = {}
    def norm(text):
        def fix(mo):
            w = mo.group(0)
            if w in _VOCAB: return w
            if w not in cache:
                m = difflib.get_close_matches(w, _VOCAB, n=1, cutoff=0.82)
                cache[w] = m[0] if m else w
            return cache[w]
        return re.sub(r"[a-z]{4,}", fix, text.lower())
    NORM = norm
    return norm

_BOILER = re.compile(r"(i want )?(a )?(replacement or (a )?refund|refund or (a )?replacement)[^.!?|]*|nothing else", re.I)
_NOTE_FW = re.compile(r"update (stuck|hang|hung|fail)|fw update stuck|recovery|update completed|update failed|update hang", re.I)

def classify(message: str, note: str = ""):
    """Return (label, source). Message first; note only if message is silent."""
    message = _BOILER.sub(" ", message)
    m = NORM(message).replace("\n", " ") if NORM else message.lower().replace("\n", " ")
    for lbl, rx in COMPILED:
        if rx.search(m): return lbl, "message"
    n = NORM(note).replace("\n", " ") if NORM else note.lower().replace("\n", " ")
    for lbl, rx in COMPILED:
        if lbl == "fw_update_stuck" and not _NOTE_FW.search(n): continue   # notes mention fw as a troubleshooting step
        if rx.search(n): return lbl, "note"
    return "other_unclear", "none"